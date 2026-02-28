"""Style linter (§5.9) — detect style rule violations in draft.

Checks the current draft against style profile rules and produces
a list of ``StyleLintViolation`` dicts. Il router ``route_style_lint``
(src/graph/routers/style_lint.py) decide il routing post-lint:
  - 'violation'       → style_fixer
  - 'clean'           → metrics_collector
  - 'max_style_iter'  → metrics_collector (uscita garantita)

RESPONSABILITÀ DI QUESTO NODO:
  Solo linting e incremento contatore. NON decide dove andare.
  La guardia di terminazione vive in route_style_lint (router).
  Non duplicare MAX_STYLE_ITERATIONS qui: importarla dal router.

DESIGN NOTE — perché il guard non sta qui:
  Il pattern precedente aveva la guardia dentro il nodo:
    if style_iterations >= MAX: return {violations: []}
  Questo era sbagliato per tre motivi:
  1. Logica di routing nel nodo — viola separazione responsabilità
  2. Falsificava i log: 0 violazioni anche se ne esistevano reali
  3. Non incrementava il contatore, rendendo lo stato incoerente
  Il corretto design: il nodo fa il suo lavoro (sempre), il router
  interpreta il risultato e prende la decisione.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from src.graph.routers.style_lint import MAX_STYLE_ITERATIONS  # fonte di verità
from src.llm.client import llm_client
from src.llm.routing import route_model

logger = logging.getLogger(__name__)


# ── Built-in L1 rules (always enforced) ───────────────────────────────────────

_L1_RULES: list[dict] = [
    {
        "rule_id": "L1_NO_FIRST_PERSON",
        "pattern": r"\b(I |my |we |our )\b",
        "category": "voice",
        "message": "Avoid first-person pronouns in academic writing",
        "fix_hint": "Rephrase using passive voice or third person",
    },
    {
        "rule_id": "L1_NO_CONTRACTIONS",
        "pattern": r"\b(don't|won't|can't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't|shouldn't|wouldn't|couldn't)\b",
        "category": "formality",
        "message": "Avoid contractions in formal writing",
        "fix_hint": "Expand the contraction",
    },
    {
        "rule_id": "L1_NO_VERY",
        "pattern": r"\bvery\b",
        "category": "precision",
        "message": "'Very' is imprecise — use a stronger adjective",
        "fix_hint": "Replace 'very X' with a more precise word",
    },
]


# ── Style Linter Node ──────────────────────────────────────────────────────────

def style_linter_node(state: dict) -> dict:
    """Lint il current_draft contro le style rules.

    Esegue SEMPRE il linting, anche all'ultima iterazione consentita.
    Il router (route_style_lint) deciderà se uscire verso metrics_collector
    o iterare verso style_fixer in base a style_iterations e alle violazioni.

    Il contatore style_iterations viene SEMPRE incrementato, anche quando
    vengono trovate violazioni all'iterazione massima. Questo è necessario
    perché route_style_lint controlla style_iterations DOPO che il nodo
    ha già restituito il suo output.

    Args:
        state: DocumentState dict.

    Returns:
        Partial state update con ``style_lint_violations`` (lista reale,
        mai forzata a vuoto) e ``style_iterations`` incrementato.
    """
    style_iterations: int = state.get("style_iterations", 0)
    new_iterations: int = style_iterations + 1

    draft: str = state.get("current_draft", "")
    style_profile: Any = state.get("style_profile", {})

    violations: list[dict] = []

    # 1. Regex-based L1 rules (fast, deterministico)
    profile_name = (
        style_profile if isinstance(style_profile, str)
        else style_profile.get("name", "academic")
    )

    if profile_name in ("academic", "formal", "scientific"):
        for rule in _L1_RULES:
            matches = list(re.finditer(rule["pattern"], draft, re.IGNORECASE))
            for m in matches[:3]:  # cap a 3 per regola
                violations.append({
                    "rule_id": rule["rule_id"],
                    "level": "L1",
                    "category": rule["category"],
                    "position": m.start(),
                    "matched_text": m.group()[:50],
                    "message": rule["message"],
                    "fix_hint": rule["fix_hint"],
                })

    # 2. LLM-based L2 rules (style profile specifiche)
    custom_rules: list[str] = []
    if isinstance(style_profile, dict):
        custom_rules = style_profile.get("rules", [])

    if custom_rules and draft:
        preset = (state.get("quality_preset") or "balanced").lower()
        l2_violations = _check_l2_rules(draft, custom_rules, preset)
        violations.extend(l2_violations)

    # Log: mostra violazioni reali anche all'ultima iterazione.
    # Se new_iterations >= MAX_STYLE_ITERATIONS, route_style_lint
    # eseguirà l'uscita garantita verso metrics_collector.
    if new_iterations >= MAX_STYLE_ITERATIONS and violations:
        logger.warning(
            "StyleLinter: iterazione %d/%d — %d violazioni residue non risolte. "
            "route_style_lint farà uscita su 'max_style_iter' → metrics_collector. "
            "Le violazioni verranno registrate nei run_metrics come warning.",
            new_iterations, MAX_STYLE_ITERATIONS, len(violations),
        )
    else:
        logger.info(
            "StyleLinter: %d violazioni (%d L1, %d L2), iterazione %d/%d",
            len(violations),
            sum(1 for v in violations if v.get("level") == "L1"),
            sum(1 for v in violations if v.get("level") == "L2"),
            new_iterations,
            MAX_STYLE_ITERATIONS,
        )

    return {
        "style_lint_violations": violations,  # mai forzato a []
        "style_iterations": new_iterations,   # sempre incrementato
    }


# ── L2 Rule Checker ──────────────────────────────────────────────────────────────

def _check_l2_rules(
    draft: str,
    rules: list[str],
    quality_preset: str = "balanced",
) -> list[dict]:
    """Usa LLM per controllare regole di stile custom (L2)."""
    try:
        rules_text = "\n".join(f"- {r}" for r in rules)
        response = llm_client.call(
            model=route_model("style_fixer", quality_preset),
            messages=[{
                "role": "user",
                "content": f"""\
Check this draft against these style rules. Report violations only.

Rules:
{rules_text}

Draft (first 3000 chars):
{draft[:3000]}

For each violation, return one line in format:
VIOLATION: [rule] | [matched text excerpt] | [fix suggestion]

If no violations, return: NO_VIOLATIONS""",
            }],
            temperature=0.1,
            max_tokens=1024,
            agent="style_linter",
            preset=quality_preset,
        )

        violations: list[dict] = []
        for line in response["text"].split("\n"):
            line = line.strip()
            if line.startswith("VIOLATION:"):
                parts = line[len("VIOLATION:"):].split("|")
                if len(parts) >= 2:
                    violations.append({
                        "rule_id": "L2_CUSTOM",
                        "level": "L2",
                        "category": "custom_rule",
                        "position": 0,
                        "matched_text": parts[1].strip()[:50],
                        "message": parts[0].strip(),
                        "fix_hint": parts[2].strip() if len(parts) >= 3 else "Fix the violation",
                    })
        return violations[:10]

    except Exception as exc:
        logger.warning("StyleLinter L2 check failed: %s", exc)
        return []
