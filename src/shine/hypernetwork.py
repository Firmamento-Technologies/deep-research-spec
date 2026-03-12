"""
SHINE Hypernetwork wrapper for DRS context compression.

SHINE (Scalable Hyper In-context NEtwork) converts text chunks into LoRA
adapter weights in a single forward pass (~0.3s), replacing token-based
approved_sections_context with in-parameter knowledge.

Do NOT clone the SHINE repo. Model weights are loaded automatically from
HuggingFace via the transformers + peft stack:
  https://huggingface.co/Yewei-Liu/SHINE-ift_mqa

Backbone: Qwen/Qwen3-8B (frozen during inference)
Paper:    https://arxiv.org/abs/2602.06358
GitHub:   https://github.com/Yewei-Liu/SHINE

Performance (from paper §5):
  Adaptation latency:  ~0.3s  (single forward pass)
  F1 on MS MARCO MQA:  55.6   (vs 69.4 In-Context, 33.0 SFT)
  vs Test-Time Train:  63.6   (SHINE) vs 58.2 (SEAL n=200)
  Memory reduction:    KV-cache eliminated for verbatim sections

Limitations:
  - Max input: 1,150 tokens per chunk (use TextChunker for longer texts)
  - Backbone fixed to Qwen3-8B (cannot use with commercial APIs)
  - F1 delta vs full In-Context: -13.8 points (mitigated by hybrid strategy)
  - Meta-training required offline (pre-trained weights provided on HF)
"""
import hashlib
import logging
from pathlib import Path
from typing import Optional

import torch

logger = logging.getLogger(__name__)

SHINE_MAX_TOKENS = 1150          # hard limit per paper §5 experiments
SHINE_HF_REPO    = "Yewei-Liu/SHINE-ift_mqa"   # HuggingFace model ID
BACKBONE_MODEL   = "Qwen/Qwen3-8B"             # frozen backbone


class LoRAAdapter:
    """
    Container for a SHINE-generated LoRA adapter.

    Attributes:
        weights:     dict layer_name → (A_tensor, B_tensor)
                     where W' = W + B @ A  (standard LoRA merge)
        source_hash: SHA256[:16] of the input text used to generate this adapter
        rank:        LoRA rank r (default 8 per paper)
    """

    def __init__(self, weights: dict, source_hash: str):
        self.weights = weights
        self.source_hash = source_hash
        try:
            self.rank: int = next(iter(weights.values()))[0].shape[1]
        except (StopIteration, IndexError):
            self.rank = 0

    def to_dict(self) -> dict:
        """JSON-serializable representation for Redis/MinIO storage."""
        return {
            "source_hash": self.source_hash,
            "rank": self.rank,
            "weights": {
                k: {"A": v[0].tolist(), "B": v[1].tolist()}
                for k, v in self.weights.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LoRAAdapter":
        """Reconstruct a LoRAAdapter from a stored dict."""
        weights = {
            k: (torch.tensor(v["A"]), torch.tensor(v["B"]))
            for k, v in data["weights"].items()
        }
        return cls(weights=weights, source_hash=data["source_hash"])


class SHINEHypernetwork:
    """
    Wrapper for SHINE single-forward-pass LoRA generation.

    Instantiate once per process (model is loaded lazily on first call).
    Thread-safe for concurrent read (generate_adapter), NOT for concurrent
    load() calls — call _load() once at startup if multi-threaded.

    Usage::

        shine = SHINEHypernetwork(device="cuda")
        adapter = shine.generate_adapter(section_text)
        registry.store(doc_id, section_idx, adapter)

    For texts longer than SHINE_MAX_TOKENS, chunk first::

        chunker = TextChunker(shine.tokenizer)
        chunks  = chunker.split(long_text)
        adapters = [shine.generate_adapter(c) for c in chunks]
        merged   = shine.merge_adapters(adapters)
    """

    def __init__(
        self,
        device: str = "cuda",
        cache_dir: Optional[str] = None,
    ):
        self.device = device
        self.cache_dir = cache_dir or str(
            Path.home() / ".cache" / "drs" / "shine"
        )
        self._model = None
        self._tokenizer = None
        self._loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def tokenizer(self):
        """Lazy-loaded tokenizer. Triggers model load if needed."""
        if not self._loaded:
            self._load()
        return self._tokenizer

    def _load(self) -> None:
        """
        Lazy-load SHINE model weights from HuggingFace.

        Downloads on first call (~16GB for Qwen3-8B + SHINE weights).
        Cached to self.cache_dir on subsequent runs.

        Requirements (auto-installed via requirements-shine.txt):
            transformers>=4.45
            peft>=0.13
            torch>=2.2
            accelerate>=0.30
        """
        if self._loaded:
            return

        logger.info("[SHINE] Loading backbone %s...", BACKBONE_MODEL)
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel

        self._tokenizer = AutoTokenizer.from_pretrained(
            BACKBONE_MODEL,
            cache_dir=self.cache_dir,
            trust_remote_code=True,
        )

        base_model = AutoModelForCausalLM.from_pretrained(
            BACKBONE_MODEL,
            cache_dir=self.cache_dir,
            torch_dtype=torch.bfloat16,
            device_map=self.device,
            trust_remote_code=True,
        )

        # Load SHINE Meta LoRA + M2P Transformer weights from HuggingFace.
        # No source code download needed — weights are the only artifact.
        self._model = PeftModel.from_pretrained(
            base_model,
            SHINE_HF_REPO,
            cache_dir=self.cache_dir,
        )
        self._model.eval()
        self._loaded = True
        logger.info("[SHINE] Model loaded on device=%s", self.device)

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def generate_adapter(self, text: str) -> LoRAAdapter:
        """
        Generate a LoRA adapter from input text in a single forward pass.

        The generated LoRA encodes the semantic content of `text` into model
        weights (W' = W + B @ A). Inference on the patched model does NOT
        require `text` in the context window — knowledge is in-parameter.

        Args:
            text: Input text. MUST be <= SHINE_MAX_TOKENS after tokenization.
                  Use TextChunker.split() + merge_adapters() for longer texts.

        Returns:
            LoRAAdapter with generated weights for all attention layers.

        Raises:
            RuntimeError: CUDA unavailable when device='cuda'.
        """
        self._load()

        source_hash = self._hash(text)
        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=SHINE_MAX_TOKENS,
        ).to(self.device)

        if inputs["input_ids"].shape[1] == SHINE_MAX_TOKENS:
            logger.warning(
                "[SHINE] Text truncated to %d tokens. Use TextChunker for longer inputs.",
                SHINE_MAX_TOKENS,
            )

        with torch.no_grad():
            _ = self._model(**inputs, output_hidden_states=True, return_dict=True)

        # Extract the generated LoRA weights written by the M2P Transformer
        lora_weights: dict = {}
        for name, module in self._model.named_modules():
            if hasattr(module, "lora_A") and hasattr(module, "lora_B"):
                lora_weights[name] = (
                    module.lora_A["default"].weight.detach().cpu().clone(),
                    module.lora_B["default"].weight.detach().cpu().clone(),
                )

        return LoRAAdapter(weights=lora_weights, source_hash=source_hash)

    def merge_adapters(self, adapters: list) -> LoRAAdapter:
        """
        Merge multiple LoRA adapters via recency-weighted average.

        Used when a section exceeds SHINE_MAX_TOKENS and has been chunked
        by TextChunker. Chunks closer to the end receive higher weight
        (more recent content dominates).

        Weight for chunk i (0-indexed, n total):
            w_i = (i + 1) / sum(1..n)

        Args:
            adapters: List of LoRAAdapter, ordered oldest → newest chunk.

        Returns:
            Single merged LoRAAdapter representing the full section.
        """
        if not adapters:
            raise ValueError("Cannot merge empty adapter list")
        if len(adapters) == 1:
            return adapters[0]

        n = len(adapters)
        weights_sum = n * (n + 1) / 2
        weight_factors = [(i + 1) / weights_sum for i in range(n)]

        reference_layers = adapters[0].weights.keys()
        merged: dict = {}

        for layer in reference_layers:
            A_merged = sum(
                wf * a.weights[layer][0]
                for wf, a in zip(weight_factors, adapters)
                if layer in a.weights
            )
            B_merged = sum(
                wf * a.weights[layer][1]
                for wf, a in zip(weight_factors, adapters)
                if layer in a.weights
            )
            merged[layer] = (A_merged, B_merged)

        combined_hash = "_".join(a.source_hash for a in adapters)[:16]
        return LoRAAdapter(weights=merged, source_hash=combined_hash)
