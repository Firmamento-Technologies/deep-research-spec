"""Regression tests — ALTA-05, ALTA-07, ALTA-08.

Queste suite bloccano le regressioni sui tre fix critici:

  ALTA-05  Section checkpoint reset (27 campi per-section)
  ALTA-07  Panel loop escape guarantee (force_approve=True a max_rounds)
  ALTA-08  Budget guard pervasivo (BudgetExhaustedError → force_approve=True
           in writer_node, jury_node, reflector_node,
           panel_discussion_node, researcher_targeted.run)

Convenzione di naming:
  - Classi ``Test<Fix>_<NomeNodo>``
  - Un test per comportamento osservabile, non per implementazione
  - Mock scope minimo: si mocka SOLO ciò che farebbe una chiamata HTTP
    esterna (llm_client.call). Tutta la logica di routing interna
    viene esercitata realmente.

Esecuzione:
  pytest tests/test_budget_guard_regression.py -v
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Factories di stato condivise
# ---------------------------------------------------------------------------

def _exhausted_budget(**overrides: object) -> dict:
    """BudgetState minimale con hard_stop_fired=True."""
    base: dict = {
        "hard_stop_fired": True,
        "spent_dollars": 10.0,
        "max_dollars": 5.0,
        "jury_size": 1,
        "max_iterations": 3,
        "regime": "economy",
    }
    return {**base, **overrides}


def _base_state(**overrides: object) -> dict:
    """DocumentState minimale per i test ALTA-08 (budget esaurito)."""
    return {
        "budget": _exhausted_budget(),
        "quality_preset": "balanced",
        "current_section_idx": 0,
        "current_iteration": 1,
        "outline": [{"scope": "Introduction", "target_words": 300}],
        "current_draft": "Existing draft text.",
        "current_sources": [],
        "synthesized_sources": "",
        "jury_verdicts": [],
        "panel_round": 0,
        "panel_anonymized_log": [],
        "style_profile": {},
        "reflector_output": {},
        "rlm_mode": False,
        "shine_active": False,
        **overrides,
    }


def _panel_state(
    panel_round: int = 0,
    max_iterations: int = 3,
    hard_stop_fired: bool = False,
) -> dict:
    """DocumentState minimale orientato al panel discussion."""
    return {
        "current_draft": "Draft text for panel evaluation.",
        "jury_verdicts": [
            {"judge_slot": "R1", "pass_fail": False,
             "css_contribution": 0.4, "motivation": "Too shallow."},
        ],
        "panel_round": panel_round,
        "panel_anonymized_log": [],
        "quality_preset": "balanced",
        "current_section_idx": 0,
        "outline": [{"scope": "Background", "target_words": 500}],
        "budget": {
            "hard_stop_fired": hard_stop_fired,
            "max_iterations": max_iterations,
            "spent_dollars": 1.0 if not hard_stop_fired else 10.0,
            "max_dollars": 10.0 if not hard_stop_fired else 5.0,
            "jury_size": 1,
        },
    }


_FAKE_LLM_RESPONSE = {
    "text": (
        "SUMMARY: Panel identified main issues.\n"
        "CONSENSUS: PARTIAL\n"
        "KEY_ISSUES:\n1. Lacks citations\nREVISED_SCORES:"
    ),
    "usage": {"input_tokens": 100, "output_tokens": 50},
}


# ===========================================================================
# ALTA-05 — Section checkpoint reset (27 campi per-section)
# ===========================================================================

class TestSectionCheckpointReset:
    """ALTA-05: tutti i 27 campi per-section devono essere resettati.

    Lista canonica: 11 originali + 16 aggiunti da ALTA-05 = 27 totali.
    Se questo test fallisce perché il numero non torna, aggiornare PRIMA
    _PER_SECTION_RESET in section_checkpoint.py, POI questa lista.
    """

    _PER_SECTION_FIELDS: list[str] = [
        # 11 originali (già presenti prima di ALTA-05)
        "current_draft",
        "current_iteration",
        "css_history",
        "all_verdicts_history",
        "style_lint_violations",
        "post_draft_gaps",
        "reflector_output",
        "aggregator_verdict",
        "draft_embeddings",
        "oscillation_detected",
        "oscillation_type",
        # 16 aggiunti da ALTA-05
        "current_sources",
        "synthesized_sources",
        "jury_verdicts",
        "style_iterations",
        "mow_drafts",
        "mow_css_per_draft",
        "fusor_draft",
        "targeted_research_active",
        "css_content_current",
        "css_style_current",
        "css_composite_current",
        "panel_active",
        "panel_round",
        "panel_anonymized_log",
        "force_approve",
        "human_intervention_required",
    ]

    def _dirty_state(self) -> dict:
        """State con tutti i campi per-section contaminati da sezione 0."""
        return {
            # Campi cross-section (devono sopravvivere)
            "approved_sections": [{"idx": 0, "draft": "Approved section 0."}],
            "current_section_idx": 0,
            "writer_memory": "Prefer active voice.",
            "outline": [
                {"scope": "Introduction", "target_words": 300},
                {"scope": "Background", "target_words": 500},
            ],
            "budget": {"spent_dollars": 1.5, "max_dollars": 20.0,
                       "hard_stop_fired": False},
            "quality_preset": "balanced",
            # Contaminazione per-section
            "current_draft": "STALE from section 0",
            "current_iteration": 4,
            "css_history": [0.3, 0.55, 0.7],
            "all_verdicts_history": [[{"judge_slot": "R1", "pass_fail": True}]],
            "style_lint_violations": ["Passive voice detected."],
            "post_draft_gaps": ["Missing citation."],
            "reflector_output": {"feedback_items": ["stale feedback"]},
            "aggregator_verdict": {"pass_fail": True, "css_composite": 0.9},
            "draft_embeddings": [0.1, 0.2, 0.3],
            "oscillation_detected": True,
            "oscillation_type": "content",
            "current_sources": [{"title": "Old Source"}],
            "synthesized_sources": "old synthesis",
            "jury_verdicts": [{"judge_slot": "R1", "pass_fail": True}],
            "style_iterations": 3,
            "mow_drafts": ["draft A", "draft B"],
            "mow_css_per_draft": [0.5, 0.65],
            "fusor_draft": "stale fused draft",
            "targeted_research_active": True,
            "css_content_current": 0.88,
            "css_style_current": 0.92,
            "css_composite_current": 0.90,
            "panel_active": True,
            "panel_round": 2,
            "panel_anonymized_log": [{"round": 1, "summary": "stale log"}],
            "force_approve": True,
            "human_intervention_required": True,
        }

    def test_regression_list_has_exactly_27_fields(self):
        """Invariante: la lista di regressione deve avere 27 voci.

        Se fallisce → un campo è stato aggiunto o rimosso da _PER_SECTION_RESET
        senza aggiornare questo test. Aggiornare entrambi in sync.
        """
        assert len(self._PER_SECTION_FIELDS) == 27, (
            f"Attesi 27 campi per-section, trovati {len(self._PER_SECTION_FIELDS)}"
        )

    def test_checkpoint_advances_section_index(self):
        """Il nodo deve incrementare current_section_idx di 1."""
        from src.graph.nodes.section_checkpoint import section_checkpoint_node
        result = section_checkpoint_node(self._dirty_state())
        assert result.get("current_section_idx") == 1

    def test_list_fields_are_emptied(self):
        """Campi lista devono essere [] o falsy dopo il reset."""
        from src.graph.nodes.section_checkpoint import section_checkpoint_node
        result = section_checkpoint_node(self._dirty_state())
        list_fields = [
            "css_history", "all_verdicts_history", "style_lint_violations",
            "post_draft_gaps", "draft_embeddings", "current_sources",
            "jury_verdicts", "mow_drafts", "mow_css_per_draft",
            "panel_anonymized_log",
        ]
        for field in list_fields:
            val = result.get(field)
            assert not val, (
                f"Campo lista '{field}' non resettato: contiene {val!r}"
            )

    def test_string_fields_are_emptied(self):
        """Campi stringa devono essere '' o None dopo il reset."""
        from src.graph.nodes.section_checkpoint import section_checkpoint_node
        result = section_checkpoint_node(self._dirty_state())
        for field in ("current_draft", "synthesized_sources", "fusor_draft"):
            val = result.get(field)
            assert not val, (
                f"Campo stringa '{field}' non resettato: contiene {val!r}"
            )

    def test_bool_flags_are_false(self):
        """Flag booleani devono essere False dopo il reset."""
        from src.graph.nodes.section_checkpoint import section_checkpoint_node
        result = section_checkpoint_node(self._dirty_state())
        bool_flags = [
            "oscillation_detected", "targeted_research_active",
            "panel_active", "force_approve", "human_intervention_required",
        ]
        for flag in bool_flags:
            assert result.get(flag) is False, (
                f"Flag '{flag}' non resettato a False: {result.get(flag)!r}"
            )

    def test_numeric_counters_are_zero(self):
        """Contatori numerici devono essere 0 dopo il reset."""
        from src.graph.nodes.section_checkpoint import section_checkpoint_node
        result = section_checkpoint_node(self._dirty_state())
        for counter in ("current_iteration", "style_iterations", "panel_round"):
            assert result.get(counter) == 0, (
                f"Contatore '{counter}' non resettato a 0: {result.get(counter)!r}"
            )

    def test_dict_fields_are_empty(self):
        """Campi dict devono essere {} o falsy dopo il reset."""
        from src.graph.nodes.section_checkpoint import section_checkpoint_node
        result = section_checkpoint_node(self._dirty_state())
        for field in ("reflector_output", "aggregator_verdict"):
            val = result.get(field)
            assert not val, (
                f"Campo dict '{field}' non resettato: contiene {val!r}"
            )

    def test_css_floats_are_zero(self):
        """CSS float correnti devono essere 0.0 dopo il reset."""
        from src.graph.nodes.section_checkpoint import section_checkpoint_node
        result = section_checkpoint_node(self._dirty_state())
        for field in (
            "css_content_current", "css_style_current", "css_composite_current"
        ):
            assert result.get(field) == 0.0, (
                f"CSS '{field}' non resettato a 0.0: {result.get(field)!r}"
            )

    def test_cross_section_fields_preserved(self):
        """approved_sections, writer_memory, outline NON devono essere resettati."""
        from src.graph.nodes.section_checkpoint import section_checkpoint_node
        dirty = self._dirty_state()
        result = section_checkpoint_node(dirty)
        assert result["approved_sections"] == dirty["approved_sections"]
        assert result["writer_memory"] == dirty["writer_memory"]
        assert result["outline"] == dirty["outline"]


# ===========================================================================
# ALTA-07 — Panel loop escape guarantee
# ===========================================================================

class TestPanelLoopEscape:
    """ALTA-07: panel_discussion_node deve impostare force_approve=True a max_rounds."""

    @patch("src.graph.nodes.panel_discussion.llm_client")
    def test_force_approve_at_exact_max_rounds(self, mock_llm: MagicMock):
        """panel_round=2 + max_iterations=3 → new_round_num=3 → force_approve=True."""
        mock_llm.call.return_value = _FAKE_LLM_RESPONSE
        from src.graph.nodes.panel_discussion import panel_discussion_node
        result = panel_discussion_node(_panel_state(panel_round=2, max_iterations=3))
        assert result["force_approve"] is True
        assert result["panel_round"] == 3

    @patch("src.graph.nodes.panel_discussion.llm_client")
    def test_force_approve_beyond_max_rounds(self, mock_llm: MagicMock):
        """panel_round > max_rounds: il guard deve comunque scattare."""
        mock_llm.call.return_value = _FAKE_LLM_RESPONSE
        from src.graph.nodes.panel_discussion import panel_discussion_node
        result = panel_discussion_node(_panel_state(panel_round=10, max_iterations=3))
        assert result["force_approve"] is True

    @patch("src.graph.nodes.panel_discussion.llm_client")
    def test_no_force_approve_before_max_rounds(self, mock_llm: MagicMock):
        """Round 1/3: force_approve deve essere False, panel deve continuare."""
        mock_llm.call.return_value = _FAKE_LLM_RESPONSE
        from src.graph.nodes.panel_discussion import panel_discussion_node
        result = panel_discussion_node(_panel_state(panel_round=0, max_iterations=3))
        assert result["force_approve"] is False
        assert result["panel_round"] == 1
        assert result["panel_active"] is True

    @patch("src.graph.nodes.panel_discussion.llm_client")
    def test_panel_log_appended(self, mock_llm: MagicMock):
        """Il log del round deve essere aggiunto anche quando non si forza."""
        mock_llm.call.return_value = _FAKE_LLM_RESPONSE
        from src.graph.nodes.panel_discussion import panel_discussion_node
        result = panel_discussion_node(_panel_state(panel_round=0, max_iterations=3))
        assert len(result["panel_anonymized_log"]) == 1
        assert result["panel_anonymized_log"][0]["round"] == 1


# ===========================================================================
# ALTA-08 — Budget guard: unit test del meccanismo
# ===========================================================================

class TestBudgetGuardUnit:
    """Unit test di src.budget.guard.check_budget_before_call."""

    def test_raises_budget_exhausted_error_when_fired(self):
        """hard_stop_fired=True deve sollevare BudgetExhaustedError."""
        from src.budget.guard import BudgetExhaustedError, check_budget_before_call
        state = {"budget": {
            "hard_stop_fired": True, "spent_dollars": 6.0, "max_dollars": 5.0,
        }}
        with pytest.raises(BudgetExhaustedError):
            check_budget_before_call(state, "test_caller")

    def test_no_raise_when_not_fired(self):
        """hard_stop_fired=False: nessuna eccezione."""
        from src.budget.guard import check_budget_before_call
        state = {"budget": {
            "hard_stop_fired": False, "spent_dollars": 1.0, "max_dollars": 5.0,
        }}
        check_budget_before_call(state, "test_caller")  # must not raise

    def test_no_raise_when_budget_key_absent(self):
        """Budget assente: default conservativo (non solleva)."""
        from src.budget.guard import check_budget_before_call
        check_budget_before_call({}, "test_caller")  # must not raise

    def test_error_message_contains_spent_amount(self):
        """Il messaggio dell'eccezione deve includere l'importo speso."""
        from src.budget.guard import BudgetExhaustedError, check_budget_before_call
        state = {"budget": {
            "hard_stop_fired": True, "spent_dollars": 7.5, "max_dollars": 5.0,
        }}
        with pytest.raises(BudgetExhaustedError, match="7.5"):
            check_budget_before_call(state, "test_caller")

    def test_error_message_contains_cap_amount(self):
        """Il messaggio dell'eccezione deve includere il cap."""
        from src.budget.guard import BudgetExhaustedError, check_budget_before_call
        state = {"budget": {
            "hard_stop_fired": True, "spent_dollars": 7.5, "max_dollars": 5.0,
        }}
        with pytest.raises(BudgetExhaustedError, match="5.0"):
            check_budget_before_call(state, "test_caller")


# ===========================================================================
# ALTA-08 — Budget guard: writer_node
# ===========================================================================

class TestBudgetGuardWriterNode:
    """ALTA-08: writer_node deve restituire force_approve=True a budget esaurito."""

    @patch("src.graph.nodes.writer.llm_client")
    def test_returns_force_approve_true(self, mock_llm: MagicMock):
        from src.graph.nodes.writer import writer_node
        result = writer_node(_base_state())
        assert result.get("force_approve") is True

    @patch("src.graph.nodes.writer.llm_client")
    def test_llm_not_called(self, mock_llm: MagicMock):
        """Con budget esaurito, llm_client.call non deve MAI essere invocato."""
        from src.graph.nodes.writer import writer_node
        writer_node(_base_state())
        mock_llm.call.assert_not_called()

    @patch("src.graph.nodes.writer.llm_client")
    def test_normal_budget_calls_llm(self, mock_llm: MagicMock):
        """Con budget disponibile, il writer deve chiamare l'LLM.

        Verifica che il guard NON blocchi il path normale.
        """
        mock_llm.call.return_value = {
            "text": "Generated section content.",
            "usage": {"input_tokens": 200, "output_tokens": 400},
        }
        normal_budget = {
            "hard_stop_fired": False, "spent_dollars": 1.0, "max_dollars": 20.0,
            "jury_size": 1, "max_iterations": 3, "regime": "balanced",
        }
        state = _base_state(budget=normal_budget)
        writer_node(state)
        mock_llm.call.assert_called_once()


# ===========================================================================
# ALTA-08 — Budget guard: jury_node
# ===========================================================================

class TestBudgetGuardJuryNode:
    """ALTA-08: jury_node deve restituire force_approve=True a budget esaurito.

    NOTA IMPLEMENTATIVA: Se questo test fallisce, significa che il guard
    in jury_base._call_llm_with_cache() non riceve ``state`` quando
    invocato da judge.evaluate(). In quel caso aggiungere il check a
    jury_node() prima del ThreadPoolExecutor.submit() loop.
    """

    @patch("src.graph.nodes.jury.llm_client", new_callable=MagicMock)
    @patch("src.graph.nodes.judge_r.llm_client", new_callable=MagicMock)
    @patch("src.graph.nodes.judge_f.llm_client", new_callable=MagicMock)
    @patch("src.graph.nodes.judge_s.llm_client", new_callable=MagicMock)
    def test_returns_force_approve_true(
        self, mock_s: MagicMock, mock_f: MagicMock,
        mock_r: MagicMock, mock_jury: MagicMock,
    ):
        from src.graph.nodes.jury import jury_node
        result = jury_node(_base_state())
        assert result.get("force_approve") is True

    @patch("src.graph.nodes.jury.llm_client", new_callable=MagicMock)
    @patch("src.graph.nodes.judge_r.llm_client", new_callable=MagicMock)
    @patch("src.graph.nodes.judge_f.llm_client", new_callable=MagicMock)
    @patch("src.graph.nodes.judge_s.llm_client", new_callable=MagicMock)
    def test_llm_not_called(
        self, mock_s: MagicMock, mock_f: MagicMock,
        mock_r: MagicMock, mock_jury: MagicMock,
    ):
        from src.graph.nodes.jury import jury_node
        jury_node(_base_state())
        for mock in (mock_s, mock_f, mock_r, mock_jury):
            mock.call.assert_not_called()


# ===========================================================================
# ALTA-08 — Budget guard: reflector_node
# ===========================================================================

class TestBudgetGuardReflectorNode:
    """ALTA-08: reflector_node deve restituire force_approve=True a budget esaurito."""

    @patch("src.graph.nodes.reflector.llm_client")
    def test_returns_force_approve_true(self, mock_llm: MagicMock):
        from src.graph.nodes.reflector import reflector_node
        state = _base_state(
            jury_verdicts=[{
                "judge_slot": "R1", "pass_fail": False,
                "motivation": "Lacks depth.", "css_contribution": 0.3,
            }],
        )
        result = reflector_node(state)
        assert result.get("force_approve") is True

    @patch("src.graph.nodes.reflector.llm_client")
    def test_llm_not_called(self, mock_llm: MagicMock):
        from src.graph.nodes.reflector import reflector_node
        reflector_node(_base_state())
        mock_llm.call.assert_not_called()


# ===========================================================================
# ALTA-08 — Budget guard: panel_discussion_node
# ===========================================================================

class TestBudgetGuardPanelDiscussionNode:
    """ALTA-08: panel_discussion_node deve restituire force_approve=True a budget esaurito."""

    @patch("src.graph.nodes.panel_discussion.llm_client")
    def test_returns_force_approve_true(self, mock_llm: MagicMock):
        from src.graph.nodes.panel_discussion import panel_discussion_node
        state = _panel_state(panel_round=0, hard_stop_fired=True)
        result = panel_discussion_node(state)
        assert result.get("force_approve") is True

    @patch("src.graph.nodes.panel_discussion.llm_client")
    def test_panel_active_is_false(self, mock_llm: MagicMock):
        """panel_active deve essere False: il loop panel non deve riprendere."""
        from src.graph.nodes.panel_discussion import panel_discussion_node
        state = _panel_state(panel_round=0, hard_stop_fired=True)
        result = panel_discussion_node(state)
        assert result.get("panel_active") is False

    @patch("src.graph.nodes.panel_discussion.llm_client")
    def test_panel_round_incremented(self, mock_llm: MagicMock):
        """panel_round deve essere incrementato anche sull'early exit.

        Il router (panel_loop.py) legge panel_round per decidere
        il routing: un valore stale causerebbe loop.
        """
        from src.graph.nodes.panel_discussion import panel_discussion_node
        state = _panel_state(panel_round=1, hard_stop_fired=True)
        result = panel_discussion_node(state)
        assert result["panel_round"] == 2

    @patch("src.graph.nodes.panel_discussion.llm_client")
    def test_llm_not_called(self, mock_llm: MagicMock):
        from src.graph.nodes.panel_discussion import panel_discussion_node
        state = _panel_state(panel_round=0, hard_stop_fired=True)
        panel_discussion_node(state)
        mock_llm.call.assert_not_called()

    @patch("src.graph.nodes.panel_discussion.llm_client")
    def test_normal_budget_calls_llm(self, mock_llm: MagicMock):
        """Con budget disponibile, il panel deve effettuare la chiamata LLM."""
        mock_llm.call.return_value = _FAKE_LLM_RESPONSE
        from src.graph.nodes.panel_discussion import panel_discussion_node
        state = _panel_state(panel_round=0, hard_stop_fired=False)
        panel_discussion_node(state)
        mock_llm.call.assert_called_once()


# ===========================================================================
# ALTA-08 — Budget guard: researcher_targeted
# ===========================================================================

class TestBudgetGuardResearcherTargeted:
    """ALTA-08: researcher_targeted.run() deve restituire force_approve=True
    a budget esaurito, senza chiamare alcun connector LLM.
    """

    @patch("src.graph.nodes.researcher_targeted.llm_client")
    def test_returns_force_approve_true(self, mock_llm: MagicMock):
        from src.graph.nodes.researcher_targeted import run
        state = _base_state(
            reflector_output={
                "feedback_items": [
                    {"type": "missing_evidence", "text": "Need source."},
                ],
            },
        )
        result = run(state)
        assert result.get("force_approve") is True

    @patch("src.graph.nodes.researcher_targeted.llm_client")
    def test_llm_not_called(self, mock_llm: MagicMock):
        from src.graph.nodes.researcher_targeted import run
        run(_base_state())
        mock_llm.call.assert_not_called()

    @patch("src.graph.nodes.researcher_targeted.llm_client")
    def test_existing_sources_preserved(self, mock_llm: MagicMock):
        """Le fonti già accumulate devono sopravvivere all'early exit."""
        from src.graph.nodes.researcher_targeted import run
        existing = [{"title": "Previously found source", "url": "https://example.com"}]
        state = _base_state(current_sources=existing)
        result = run(state)
        # Le fonti esistenti non devono essere cancellate dal guard
        returned_sources = result.get("current_sources")
        if returned_sources is not None:
            assert returned_sources == existing
