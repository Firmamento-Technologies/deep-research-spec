"""RLM client factory — src/llm/rlm_adapter.py

Provides get_rlm_client() which builds a correctly-wired RLM instance.

ARCHITETTURA — perché DeepResearchLM è stato rimosso
=====================================================
RLM (https://github.com/alexzhang13/rlm, arXiv:2512.24601) espone un
construttore che accetta solo stringhe backend:

    RLM(backend='openrouter', backend_kwargs={'model_name': '...'}, ...)

get_client() in rlm/clients/__init__.py è una factory NON estendibile:
accetta {'openai','openrouter','anthropic','vllm','litellm','portkey',
'gemini','azure_openai','vercel'} e restituisce un BaseLM concreto.
Non c'è nessun parametro custom_client= / custom_sub_client= per iniettare
un'istanza BaseLM precostruita — TypeError immediato se usati.

STRATEGIA DI BUDGET (sostituisce il bridge approach)
=====================================================
  1. max_budget passato a RLM() → enforced internamente dal REPL loop
  2. Dopo rlm.completion(), il caller (writer_node) legge
     result.usage_summary.total_cost e aggiorna state['budget']['spent_dollars']
  3. Il rate limiting a livello provider è gestito dalle API key quotas

MAPPA BACKEND
=============
  Il routing table usa il formato 'provider/model_name':
    'openrouter/google/gemini-2.5-pro' → backend='openrouter', model_name='google/gemini-2.5-pro'
    'anthropic/claude-opus-4-5'        → backend='anthropic', model_name='claude-opus-4-5'
    'openai/gpt-4o'                    → backend='openai',    model_name='gpt-4o'
  I backend non riconosciuti fallback a 'openai' con model_name intatto.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ── Env config ──────────────────────────────────────────────────────────────

# RLM environment (default: 'corpus' — legge tutto il corpus nel REPL loop)
_RLM_ENVIRONMENT: str = os.getenv("RLM_ENVIRONMENT", "corpus")

# Directory per i log del REPL trace (debugging)
_RLM_LOG_DIR: str = os.getenv("RLM_LOG_DIR", "/tmp/rlm_logs")

# Profondità massima di ricorsione del REPL
_RLM_MAX_DEPTH: int = int(os.getenv("RLM_MAX_DEPTH", "10"))

# Iterazioni massime per completion
_RLM_MAX_ITERATIONS: int = int(os.getenv("RLM_MAX_ITERATIONS", "20"))

# Backend noti in RLM (da rlm/clients/__init__.py, alexzhang13/rlm@main)
_KNOWN_BACKENDS: frozenset[str] = frozenset({
    "openai", "openrouter", "anthropic", "vllm",
    "litellm", "portkey", "gemini", "azure_openai", "vercel",
})


# ── Backend parser ────────────────────────────────────────────────────────────

def _parse_model_string(model: str) -> tuple[str, str]:
    """Parse una stringa modello nel formato routing → (backend, model_name) RLM.

    Il routing table usa 'provider/model_name'. Esempi:
      'openrouter/google/gemini-2.5-pro' → ('openrouter', 'google/gemini-2.5-pro')
      'anthropic/claude-opus-4-5'        → ('anthropic', 'claude-opus-4-5')
      'openai/gpt-4o'                    → ('openai', 'gpt-4o')
      'gpt-4o'                           → ('openai', 'gpt-4o')  # fallback

    Args:
        model: Stringa modello nel formato del routing table.

    Returns:
        Tupla (backend, model_name) pronta per RLM().
    """
    parts = model.split("/", 1)
    if len(parts) == 2 and parts[0] in _KNOWN_BACKENDS:
        return parts[0], parts[1]
    # Fallback: stringa intera come model_name, backend openai
    logger.warning(
        "rlm_adapter: provider non riconosciuto in '%s', fallback backend='openai'",
        model,
    )
    return "openai", model


# ── Factory ───────────────────────────────────────────────────────────────────

def get_rlm_client(
    model: str,
    child_model: str | None = None,
    state: dict[str, Any] | None = None,
):
    """Costruisce un'istanza RLM configurata per il writer node.

    Non usa DeepResearchLM né custom_client= — quei parametri non esistono
    nell'API pubblica di RLM. Il budget è enforced via max_budget di RLM;
    la riconciliazione costi avviene nel caller dopo rlm.completion().

    Args:
        model:       Modello root (es. 'openrouter/google/gemini-2.5-pro').
                     Usato per il turno principale del REPL.
        child_model: Modello per i sub-call ricorsivi (es. 'openai/gpt-4o-mini').
                     Default: route_model('writer', 'economy').
        state:       DocumentState dict. Usato per leggere section_budget_usd.

    Returns:
        Istanza RLM pronta per .completion().
    """
    from rlm.core.rlm import RLM
    from rlm.utils.logger import RLMLogger

    state = state or {}

    # Budget per-sezione passato a RLM (enforced internamente)
    budget_usd: float | None = state.get("section_budget_usd")

    # Child model fallback
    if child_model is None:
        from src.llm.routing import route_model as _route_model
        child_model = _route_model("writer", "economy")

    # Parse entrambe le stringhe modello
    root_backend, root_model_name = _parse_model_string(model)
    child_backend, child_model_name = _parse_model_string(child_model)

    logger.info(
        "rlm_adapter: root=%s/%s child=%s/%s budget=$%s env=%s",
        root_backend, root_model_name,
        child_backend, child_model_name,
        f"{budget_usd:.4f}" if budget_usd is not None else "None",
        _RLM_ENVIRONMENT,
    )

    rlm_logger = RLMLogger(log_dir=_RLM_LOG_DIR)

    return RLM(
        backend=root_backend,
        backend_kwargs={"model_name": root_model_name},
        other_backends=[child_backend],
        other_backend_kwargs=[{"model_name": child_model_name}],
        environment=_RLM_ENVIRONMENT,
        max_depth=_RLM_MAX_DEPTH,
        max_iterations=_RLM_MAX_ITERATIONS,
        max_budget=budget_usd,
        logger=rlm_logger,
    )
