# §30 — SHINE Integration: Context-to-Parameter Knowledge

> **Status**: Specified — implementation in `src/shine/`  
> **Depends on**: §14 (ContextCompressor), §5.7 (Writer), §19 (BudgetController)  
> **Paper**: [arXiv:2602.06358](https://arxiv.org/abs/2602.06358)  
> **Backbone weights**: [Yewei-Liu/SHINE-ift_mqa](https://huggingface.co/Yewei-Liu/SHINE-ift_mqa)

---

## §30.0 Overview

SHINE (Scalable Hyper In-context NEtwork) is a hypernetwork that converts
text into LoRA adapter weights in a **single forward pass (~0.3s)**,
eliminating the need to pass previously approved sections as raw tokens
to the Writer, Fusor, Reflector, and CoherenceGuard.

The core idea: instead of injecting 20,000 tokens of approved context into
every LLM call, the context is **compressed into model parameters** (LoRA A, B
matrices). The target model "knows" the prior sections without seeing them.

```
PREVIOUSLY (pure token context):                   NOW (SHINE hybrid):

Writer input:                                      Writer input:
  ├── outline (1K)              ✅ unchanged         ├── outline (1K)              ✅
  ├── compressed_corpus (5K)    ✅ unchanged         ├── compressed_corpus (5K)    ✅
  ├── citation_map (1K)         ✅ unchanged         ├── citation_map (1K)         ✅
  ├── approved_sections (20K)   ❌ token cost        ├── LBC claims only (0.5K)    ✅ -97%
  └── reflector_feedback (1K)   ✅ unchanged         ├── reflector_feedback (1K)   ✅
                                                     └── [LoRA adapter injected]    ✅ zero tokens
Total input: ~28K tokens                           Total input: ~9K tokens
```

---

## §30.1 Architecture

### Two-Pass Pipeline

```
Approved Section (text)
        │
        ▼
┌────────────────────────────────────┐
│  Pass 1 — Memory Extraction        │  Qwen3-8B + Meta LoRA (frozen)
│                                    │
│  [X; M₀] ──► LLM layers ──► Mᵢ   │  Mᵢ = hidden states of memory tokens
│                                    │  M = Stack([M₁...Mₗ]) ∈ ℝᴸˣᴹˣᴴ
└─────────────────┬──────────────────┘
                  │
                  ▼
┌────────────────────────────────────┐
│  Pass 2 — M2P Transformer          │  Lightweight (4-layer, sparse attention)
│                                    │
│  M ──► column attn + row attn     │  O((LM² + ML²)) vs O((LM)²) full attn
│     ──► reshape ──► (A, B) matrices│  W' = W + B @ A  (standard LoRA merge)
└─────────────────┬──────────────────┘
                  │
                  ▼
        LoRAAdapter stored in
        AdapterRegistry (Redis + MinIO)
```

### Key Parameters (from paper §5)

| Parameter | Value | Notes |
|---|---|---|
| Backbone | Qwen3-8B | Frozen during inference |
| Meta LoRA rank | 128 | Trained offline (in HF weights) |
| Generated LoRA rank | 8 | Injected into target model |
| Memory tokens M | 148 | Per §3.3 formula: M = ⌈rD/H⌉ |
| M2P Transformer layers | 4 | Sparse row/column attention |
| Max input tokens | 1,150 | Hard limit — use TextChunker for longer |
| Adaptation latency | ~0.3s | Single forward pass, no gradient steps |
| F1 on MS MARCO MQA | 55.6 | vs 69.4 In-Context (−13.8 pts) |

---

## §30.2 Installation — Do You Need to Clone SHINE?

**No. You do NOT clone the SHINE GitHub repository.**

The SHINE repository contains training code (meta-training pipeline,
dataset preparation). For DRS inference, only the **pre-trained model
weights** are needed, and those are available directly on HuggingFace.

### Setup Steps

```bash
# 1. Install Python dependencies
pip install -r requirements-shine.txt

# 2. (Optional) Pre-download weights — ~16GB total
#    If skipped, weights auto-download on first SHINEHypernetwork() call
python -c "
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen3-8B', trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained('Qwen/Qwen3-8B', trust_remote_code=True)
model = PeftModel.from_pretrained(model, 'Yewei-Liu/SHINE-ift_mqa')
print('SHINE weights downloaded successfully')
"

# 3. Verify integration
python -c "
from src.shine import SHINEHypernetwork
shine = SHINEHypernetwork(device='cuda')  # or 'cpu' for testing
adapter = shine.generate_adapter('Test section content.')
print(f'Adapter generated: {len(adapter.weights)} layers, rank={adapter.rank}')
"
```

### `requirements-shine.txt`

```
transformers>=4.45.0
peft>=0.13.0
torch>=2.2.0
accelerate>=0.30.0
bitsandbytes>=0.43.0    # optional: 4-bit quantisation for <24GB VRAM
```

### Hardware Requirements

| Mode | VRAM | Notes |
|---|---|---|
| BF16 (default) | ~18GB | Recommended for A100/H100 |
| 8-bit quantised | ~10GB | Add `load_in_8bit=True` to AutoModelForCausalLM |
| 4-bit quantised | ~6GB | Add `load_in_4bit=True`; minor quality degradation |
| CPU-only | ~32GB RAM | Slow (~30s/adapter); only for dev/testing |

---

## §30.3 Integration Points in DRS

### Files Added / Modified

```
src/
├── shine/
│   ├── __init__.py             NEW — package exports
│   ├── hypernetwork.py         NEW — SHINEHypernetwork, LoRAAdapter
│   ├── adapter_registry.py     NEW — AdapterRegistry (Redis + MinIO + memory)
│   └── chunker.py              NEW — TextChunker (1150-token splits)
│
├── graph/nodes/
│   └── context_compressor.py   NEW — replaces stub; SHINE-enhanced §14
│
docs/
└── 30_shine_integration.md     NEW — this file
```

### DocumentState Fields Added

```python
class DocumentState(TypedDict):
    # ... all existing fields ...

    # SHINE integration (§30)
    shine_enabled:             bool        # feature flag; default True
    active_lora_section_idxs:  list[int]   # sections currently encoded as adapters
```

### LangGraph Node

No changes to the graph topology. `context_compressor` is already wired:

```python
# §4.5 — edge already exists, no modification needed
g.add_edge("context_compressor", "coherence_guard")
```

The node implementation at `src/graph/nodes/context_compressor.py` now
automatically uses SHINE for verbatim-tier sections when `shine_enabled=True`.

### Writer Node — Adapter Injection (TODO)

The Writer must be updated to merge active LoRA adapters before inference.
When `state["active_lora_section_idxs"]` is non-empty:

```python
# In src/graph/nodes/writer.py — to be implemented
from src.shine.adapter_registry import AdapterRegistry

async def run(state: dict) -> dict:
    registry = AdapterRegistry(...)
    adapters = registry.load_all_for_doc(
        doc_id=state["run_id"],
        up_to_section=state["current_section_idx"],
    )

    # Inject adapters into local Qwen3-8B before calling Writer LLM
    # Only applies when Writer uses the local vLLM backend
    # Commercial models (Claude, GPT) are not affected — they receive
    # the LBC-only text context (already much smaller)
    if adapters and state.get("writer_uses_local_backend"):
        _inject_adapters(writer_model, adapters)
```

> **Note**: For commercial LLM writers (Claude Opus 4.5 via OpenRouter),
> adapter injection is not possible. In this case, SHINE savings come
> from the drastically reduced token context (`approved_sections_context`
> contains only LBC claims instead of full verbatim text).

---

## §30.4 Cost Savings Model

### Per-Section Token Reduction

For a document with N sections, at section k the Writer receives:

**Without SHINE:**
```
approved_sections_context ≈ Σᵢ₌₀ᵏ⁻¹ words(section_i) × 1.3  [tokens]
```

**With SHINE (verbatim tier d=1,2 → adapter; rest → compressed text):**
```
approved_sections_context ≈ words(LBC claims, sections d=1,2) × 1.3
                           + 120 words × (min(k, 5) - 2)        [structured_summary]
                           + 40 words  × max(k - 5, 0)          [thematic_extract]
```

### Savings Table (10-section document, avg 2000 words/section)

| Section | Without SHINE | With SHINE | Savings |
|---|---|---|---|
| §1 | 0 token | 0 token | — |
| §3 | ~5,200 tok | ~200 tok | −96% |
| §5 | ~10,400 tok | ~560 tok | −95% |
| §7 | ~15,600 tok | ~900 tok | −94% |
| §9 | ~20,800 tok | ~1,200 tok | −94% |

Applied across Writer + Jury (×3) + Fusor + Reflector + CoherenceGuard:

| Document size | Estimated savings | At $0.015/1K tok (Claude Opus) |
|---|---|---|
| 10 sections | ~870K tokens | **~$13 per document** |
| 20 sections | ~4.2M tokens | **~$63 per document** |

---

## §30.5 Limitations and Mitigations

| Limitation | Details | Mitigation |
|---|---|---|
| F1 gap vs full context | −13.8 pts (55.6 vs 69.4) | LBC claims in text context preserve logical dependencies |
| Max 1,150 tokens/chunk | Hard architectural limit | TextChunker + merge_adapters() |
| Backbone fixed to Qwen3-8B | Cannot inject into Claude/GPT | Token reduction alone saves ~90% of verbatim cost for commercial models |
| Meta-training costly upfront | 6B token pretraining (done) | Use HF weights — no retraining needed |
| Multi-adapter interference | 50+ adapters → degradation | Only 2 sections in verbatim tier at any time (d=1,2); older sections use text |
| VRAM overhead | ~18GB for BF16 | Shared with local vLLM instance; quantisation available |

---

## §30.6 Feature Flag and A/B Testing

SHINE is controlled by `DocumentState.shine_enabled` (default: `True`).
Set to `False` to fall back to pure LLM compression (§14 original behaviour):

```python
# Disable SHINE for a specific run (e.g., low-VRAM environment)
config = DRSConfig(
    shine_enabled=False,   # falls back to qwen/qwen3-7b LLM compression
    ...
)
```

For A/B testing, run 50 documents with `shine_enabled=True` and 50 with
`False`, comparing `run_metrics.cost_per_document` and jury CSS scores.
Results stored in `run_metrics.shine_ab_test` (to be added to §23 Grafana
dashboard).

---

## §30.7 Cross-References

| Section | Topic |
|---|---|
| §14 | ContextCompressor base spec (tier definitions, LBC algorithm, timing) |
| §5.7 | Writer agent (consumes `approved_sections_context` + adapters) |
| §4.6 | DocumentState (`shine_enabled`, `active_lora_section_idxs`) |
| §19 | BudgetController (token savings reduce `projected_final`) |
| §23 | Grafana monitoring (`shine_ab_test` metrics) |
| §28 | LLM Assignments (SHINE backbone = Qwen3-8B, separate from OpenRouter models) |

<!-- SPEC_COMPLETE -->
