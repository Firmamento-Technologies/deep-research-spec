"""Writer agent (§5.7) con §29.1 prompt caching + SHINE + RLM mode.

Genera il draft di una sezione usando uno di tre path:

- **SHINE LoRA path** (``shine_active=True`` AND ``SHINE_SERVING_URL`` set):
  L'hypernetwork SHINE encoda il corpus di ricerca in LoRA weight deltas in un
  singolo forward pass, iniettati in un server vLLM/AIBrix locale. Il modello
  ha la domain knowledge nei weights — corpus non nel prompt (~95% token reduction).
  Ref: https://github.com/Yewei-Liu/SHINE (arXiv:2602.06358)

  IMPORTANTE: ``state["shine_lora"]`` contiene tensori binari, NON testo.
  ``shine_active=True`` senza ``SHINE_SERVING_URL`` è una misconfiguration:
  il nodo fallback a corpus standard + logger.warning().

- **RLM path** (``rlm_mode=True``):
  RLM (https://github.com/alexzhang13/rlm, arXiv:2512.24601) apre un REPL
  e chiama il modello ricorsivamente per decomporre il corpus chunk-by-chunk.
  Il corpus completo (non compresso) è passato a ``rlm.completion()``;
  RLM gestisce il context management internamente.
  Budget enforcement: max_budget passato a RLM() + riconciliazione costi
  post-completion su state['budget']['spent_dollars'].
  Early return prima di llm_client.call().

- **Standard path** (fallback): corpus compresso/sintetizzato nel prompt,
  singola llm_client.call().

Il system prompt usa §29.1 cache-control blocks (Anthropic) per caching
delle style rules + exemplar attraverso le sezioni (~5 min TTL).
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from src.budget.guard import BudgetExhaustedError, check_budget
from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)

# Endpoint reale del server LoRA per SHINE.
# SHINE (https://github.com/Yewei-Liu/SHINE, arXiv:2602.06358) encoda il
# corpus in LoRA weight deltas tramite hypernetwork, poi li inietta in questo
# server di inferenza locale. Il modello "conosce" il corpus senza averlo
# nel prompt (~95% riduzione token).
# I modelli cloud API (Anthropic, OpenAI, OpenRouter) non possono ricevere
# iniezioni LoRA. Se vuoto: fallback a corpus standard + logger.warning().
_SHINE_SERVING_URL: str = os.getenv("SHINE_SERVING_URL", "")


# ── Writer Node ───────────────────────────────────────────────────────────────────────

def writer_node(state: dict) -> dict:
    """Genera il draft della sezione da corpus compresso, RLM o SHINE.

    Priorità di selezione path:
      1. SHINE LoRA   (shine_active=True AND SHINE_SERVING_URL set)
      2. RLM          (rlm_mode=True) — early return, bypassa llm_client
      3. Standard     (fallback)

    Args:
        state: DocumentState dict.

    Returns:
        Aggiornamento parziale dello stato con ``current_draft``,
        ``current_iteration`` e opzionalmente ``budget`` aggiornato.
        Se budget esaurito, ritorna {"force_approve": True}.
    """
    section_idx = state.get("current_section_idx", 0)
    outline = state.get("outline", [])
    section = outline[section_idx] if section_idx < len(outline) else {}

    section_scope = section.get("scope", "")
    target_words = section.get("target_words", 500)
    # Normalizza preset: stato usa 'Balanced' (cap), routing usa 'balanced' (lower)
    preset = (state.get("quality_preset") or "balanced").lower()

    style_profile = state.get("style_profile", {})
    style_profile_str = (
        style_profile if isinstance(style_profile, str)
        else style_profile.get("name", "academic")
    )
    style_exemplar = state.get("style_exemplar") or ""
    writer_memory = state.get("writer_memory", {})

    current_sources = state.get("current_sources", [])
    citation_text = _format_sources_as_citations(current_sources)

    shine_active = state.get("shine_active", False)
    rlm_mode = state.get("rlm_mode", False)

    # ─────────────────────────────────────────────────────────────────────────
    # PATH 1 — SHINE LoRA
    # ─────────────────────────────────────────────────────────────────────────
    if shine_active:
        if _SHINE_SERVING_URL:
            logger.info(
                "Writer: SHINE LoRA path — server %s — corpus come weight deltas "
                "(https://github.com/Yewei-Liu/SHINE)",
                _SHINE_SERVING_URL,
            )
            user_prompt = _build_prompt_shine_lora(
                style_profile_str, section_scope, target_words, citation_text,
            )
        else:
            logger.warning(
                "Writer: shine_active=True ma SHINE_SERVING_URL non configurato. "
                "SHINE richiede un server vLLM/AIBrix locale per iniettare i LoRA "
                "weight deltas — i modelli cloud non possono ricevere iniezioni LoRA. "
                "state['shine_lora'] contiene tensori binari, non testo. "
                "Fallback a corpus standard."
            )
            corpus = (
                state.get("synthesized_sources", "")
                or state.get("compressed_corpus", "")
            )
            user_prompt = _build_prompt_corpus(
                style_profile_str, section_scope, target_words, citation_text, corpus,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # PATH 2 — RLM (early return — bypassa llm_client.call)
    # RLM gestisce il proprio HTTP transport (backend string, non BaseLM inject).
    # Budget enforcement: max_budget a RLM + riconciliazione post-completion.
    # Ref: https://github.com/alexzhang13/rlm (arXiv:2512.24601)
    # ─────────────────────────────────────────────────────────────────────────
    elif rlm_mode:
        # §19.6 Budget guard per RLM path
        try:
            check_budget(state, agent="writer_rlm", estimated_cost=1.50)
        except BudgetExhaustedError:
            logger.warning(
                "Writer/RLM: budget exhausted before RLM call — forcing approval"
            )
            existing_draft = state.get("current_draft", "")
            return {
                "force_approve": True,
                "current_draft": existing_draft if existing_draft else f"(Section content unavailable — budget exhausted for: {section_scope})",
            }

        from src.llm.rlm_adapter import get_rlm_client  # lazy import

        # Corpus completo non compresso — RLM gestisce la decomposizione
        corpus = (
            state.get("sanitized_sources", "")
            or state.get("research_results", "")
            or state.get("synthesized_sources", "")  # fallback gracioso
        )

        full_prompt = _build_prompt_corpus(
            style_profile_str, section_scope, target_words, citation_text, corpus,
        )

        rlm = get_rlm_client(
            model=route_model("writer", preset),
            child_model=route_model("writer", "economy"),
            state=state,
        )

        logger.info(
            "Writer: RLM mode — https://github.com/alexzhang13/rlm — "
            "corpus=%d chars, model=%s",
            len(corpus),
            route_model("writer", preset),
        )

        result = rlm.completion(full_prompt)
        draft = result.response
        word_count = len(draft.split())
        citations_used = list(set(re.findall(r"\[(\w+)\]", draft)))

        # Riconciliazione costi: leggi da RLM e aggiorna budget state
        cost_usd = 0.0
        if result.usage_summary is not None:
            try:
                cost_usd = float(result.usage_summary.total_cost or 0.0)
            except (AttributeError, TypeError, ValueError):
                logger.warning(
                    "Writer/RLM: impossibile leggere total_cost da usage_summary, "
                    "budget state non aggiornato per questa sezione."
                )

        logger.info(
            "RLM draft: %d words, %d citations, cost=$%.4f, time=%.2fs",
            word_count, len(citations_used), cost_usd, result.execution_time,
        )

        # Aggiorna budget nel state
        budget_update: dict = {}
        existing_budget = state.get("budget", {})
        if cost_usd > 0 and existing_budget:
            new_spent = existing_budget.get("spent_dollars", 0.0) + cost_usd
            budget_update = {"budget": {**existing_budget, "spent_dollars": new_spent}}

        # Early return — RLM ha gestito il transport
        return {
            "current_draft": draft,
            "current_iteration": state.get("current_iteration", 0) + 1,
            **budget_update,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # PATH 3 — Standard (SHINE inactive, RLM inactive)
    # ─────────────────────────────────────────────────────────────────────────
    else:
        corpus = (
            state.get("synthesized_sources", "")
            or state.get("compressed_corpus", "")
        )
        logger.info("Writer: standard corpus path (SHINE inactive, RLM inactive)")
        user_prompt = _build_prompt_corpus(
            style_profile_str, section_scope, target_words, citation_text, corpus,
        )

    # ── §29.1 Prompt Caching: system come array con cache_control ────────────
    # Si applica a PATH 1 (SHINE) e PATH 3 (standard) soltanto.
    # PATH 2 (RLM) ha fatto early return sopra.
    system_blocks = [
        {
            "type": "text",
            "text": _get_style_profile_rules(style_profile),
            "cache_control": {"type": "ephemeral"},  # CACHED ~5 min
        },
        {
            "type": "text",
            "text": f"Style Exemplar:\n{style_exemplar}" if style_exemplar else "",
            "cache_control": {"type": "ephemeral"},  # CACHED ~5 min
        },
        {
            "type": "text",
            "text": _format_writer_memory(writer_memory),
            # NON cached — cambia per sezione
        },
    ]

    # P8: max_tokens dinamico proporzionale a target_words.
    # Formula: words × 1.5 safety buffer ÷ 0.75 words/token + 256 overhead.
    # Floor 512, cap 8192.
    max_tokens = max(512, min(int(target_words * 1.5 / 0.75) + 256, 8192))

    # ── §19.6 Budget guard per PATH 1 + PATH 3 ────────────────────────
    try:
        check_budget(state, agent="writer", estimated_cost=0.50)
    except BudgetExhaustedError:
        logger.warning(
            "Writer: budget exhausted before llm_client.call — forcing approval"
        )
        existing_draft = state.get("current_draft", "")
        return {
            "force_approve": True,
            "current_draft": existing_draft if existing_draft else f"(Section content unavailable — budget exhausted for: {section_scope})",
        }

    # ── LLM call (PATH 1 + PATH 3) ─────────────────────────────────────
    messages = [{"role": "user", "content": user_prompt}]

    response = llm_client.call(
        model=route_model("writer", preset),
        system=system_blocks,
        messages=messages,
        temperature=0.3,
        max_tokens=max_tokens,
        agent="writer",
        preset=preset,
    )

    draft = response["text"]
    word_count = len(draft.split())
    citations_used = list(set(re.findall(r"\[(\w+)\]", draft)))

    logger.info(
        "Draft: %d words, %d citations, cost=$%.4f, max_tokens=%d",
        word_count, len(citations_used), response["cost_usd"], max_tokens,
    )

    return {
        "current_draft": draft,
        "current_iteration": state.get("current_iteration", 0) + 1,
    }


# ── Prompt builders ───────────────────────────────────────────────────────────────────

def _build_prompt_shine_lora(
    style: str, scope: str, target_words: int, citations: str,
) -> str:
    """Prompt per il path LoRA reale SOLO.

    Chiamato esclusivamente quando SHINE_SERVING_URL è configurato. Il modello
    ha già la domain knowledge nei weights tramite iniezione LoRA.
    NON chiamare per modelli cloud API (non possono ricevere LoRA).
    """
    return f"""\
Scrivi una sezione per un documento {style}.

Sezione: {scope}
Conteggio parole target: {target_words} (±15% accettabile)

Fonti (usa SOLO le citazioni da questa mappa):
{citations}

Vincoli:
- Il tuo adapter LoRA contiene la domain knowledge per questa sezione
- Cita le fonti nel formato [source_id]
- Conteggio parole: {target_words} ±15%
- Nessuna formattazione markdown"""


def _build_prompt_corpus(
    style: str, scope: str, target_words: int, citations: str, corpus: str,
) -> str:
    """Prompt per path standard e RLM.

    Usato da:
      - PATH 2 (RLM): corpus completo non compresso
      - PATH 3 (standard): corpus pre-compresso
      - PATH 1 fallback (SHINE mal configurato): corpus compresso
    """
    return f"""\
Scrivi una sezione per un documento {style}.

Sezione: {scope}
Conteggio parole target: {target_words} (±15% accettabile)

Fonti (usa SOLO le citazioni da questa mappa):
{citations}

Corpus di ricerca:
{corpus}

Vincoli:
- Usa SOLO fatti dal corpus sopra
- Cita le fonti nel formato [source_id]
- Conteggio parole: {target_words} ±15%
- Nessuna formattazione markdown"""


# ── Helpers ─────────────────────────────────────────────────────────────────────────

def _get_style_profile_rules(style_profile: Any) -> str:
    """Carica le style rules da config/style_profiles.yaml (§26)."""
    import yaml as _yaml
    from pathlib import Path as _Path

    if isinstance(style_profile, str):
        profile_name = style_profile
    elif isinstance(style_profile, dict):
        inline_rules = style_profile.get("rules", [])
        if inline_rules:
            return "Style rules:\n" + "\n".join(f"- {r}" for r in inline_rules)
        profile_name = style_profile.get("name", "academic")
    else:
        profile_name = "academic"

    config_path = _Path(__file__).resolve().parents[3] / "config" / "style_profiles.yaml"
    if config_path.exists():
        try:
            with open(config_path) as f:
                profiles = _yaml.safe_load(f) or {}
            profile = profiles.get(profile_name, profiles.get("academic", {}))
            rules = profile.get("rules", [])
            if rules:
                return "Style rules:\n" + "\n".join(f"- {r}" for r in rules)
        except Exception:
            pass

    return "Segui le convenzioni di scrittura accademica. Sii preciso e ben documentato."


def _format_sources_as_citations(sources: list[dict]) -> str:
    """Formatta current_sources come mappa di citazioni."""
    if not sources:
        return "(nessuna fonte disponibile)"
    lines = []
    for s in sources:
        sid = s.get("source_id", "?")
        title = s.get("title", "Senza titolo")
        snippet = (s.get("abstract") or s.get("full_text_snippet") or "")[:200]
        lines.append(f"[{sid}] {title}: {snippet}")
    return "\n".join(lines)


def _format_writer_memory(writer_memory: dict) -> str:
    """Formatta gli errori ricorrenti dalla writer memory (§5.18)."""
    recurring = writer_memory.get("recurring_errors", [])
    if not recurring:
        return ""
    return "Errori precedenti da evitare:\n" + "\n".join(f"- {err}" for err in recurring)
