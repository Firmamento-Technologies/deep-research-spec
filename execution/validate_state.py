#!/usr/bin/env python3
"""
Validation script for Phase 1: State & Types.

Verifies that src/graph/state.py contains ALL required fields
from DocumentState (§4.6), with correct types and sub-TypedDicts.

Run: python execution/validate_state.py
"""
import ast
import sys
import os
from pathlib import Path
from typing import Any

# ─── Expected DocumentState fields from §4.6 ────────────────────────────────
# Each entry: (field_name, expected_type_substring)
# Type substrings are checked loosely to accommodate Annotated[], Optional[], etc.

DOCUMENT_STATE_FIELDS: list[tuple[str, str]] = [
    # Identity & lifecycle
    ("doc_id", "str"),
    ("thread_id", "str"),
    ("user_id", "str"),
    ("status", "Literal"),
    ("config", "dict"),
    # Outline
    ("outline", "list"),
    ("outline_approved", "bool"),
    # Section tracking
    ("current_section_idx", "int"),
    ("current_iteration", "int"),
    ("total_sections", "int"),
    # Draft
    ("current_draft", "str"),
    ("draft_history", "list"),
    # Sources
    ("sources", "list"),
    ("ghost_citations", "list"),
    ("synthesized_sources", "str"),
    # Jury
    ("jury_verdicts", "list"),
    ("css_content", "float"),
    ("css_style", "float"),
    ("css_history", "list"),
    # Reflector
    ("reflector_output", ""),   # can be dict or ReflectorOutput
    ("oscillation_detected", "bool"),
    ("oscillation_count", "int"),
    # Style
    ("style_violations", "list"),
    # Coherence
    ("coherence_conflicts", "list"),
    # WriterMemory
    ("writer_memory", "dict"),
    # Budget
    ("budget", ""),  # BudgetState or dict
    # Approved sections
    ("approved_sections", "list"),
    # Force approve
    ("force_approve", "bool"),
    # Context
    ("context_window", "str"),
    # Output
    ("export_urls", "dict"),
    # Companion
    ("companion_messages", ""),  # Annotated[list, add_messages]
    # Warnings
    ("warnings", "list"),
    # Metrics
    ("section_metrics", "dict"),
    # Run report
    ("run_report", "dict"),
    # Research control
    ("targeted_research_active", "bool"),
    # Rogue judge
    ("rogue_judge_flags", "list"),
    ("circuit_breaker_states", "dict"),
]

REQUIRED_SUB_TYPEDICTS = [
    "BudgetState",
    "OutlineSection",
    "Source",
    "JudgeVerdict",
    "AggregatorVerdict",
    "ReflectorOutput",
    "StyleLintViolation",
    "CoherenceConflict",
]

BUDGET_STATE_FIELDS: list[tuple[str, str]] = [
    ("max_budget_dollars", "float"),
    ("accumulated_cost", "float"),
    ("budget_per_section", "float"),
    ("quality_preset", ""),
    ("max_iterations", "int"),
    ("jury_size", "int"),
    ("mow_enabled", "bool"),
    ("css_content_threshold", "float"),
    ("css_style_threshold", "float"),
    ("css_panel_threshold", "float"),
    ("hard_stop_fired", "bool"),
    ("alarms_fired", "list"),
    ("regime_changes", "list"),
]


def find_state_file() -> Path:
    """Locate src/graph/state.py relative to project root."""
    candidates = [
        Path("src/graph/state.py"),
        Path("deep-research-system/src/graph/state.py"),
    ]
    for p in candidates:
        if p.exists():
            return p
    print("FAIL: Cannot find src/graph/state.py")
    print("  Searched:", [str(c) for c in candidates])
    sys.exit(1)


def parse_file(path: Path) -> ast.Module:
    """Parse Python file into AST."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        print(f"FAIL: Syntax error in {path}: {e}")
        sys.exit(1)
    return tree


def extract_class_fields(tree: ast.Module, class_name: str) -> dict[str, str]:
    """
    Extract annotated fields from a TypedDict or class definition.
    Returns {field_name: annotation_source_text}.
    """
    fields: dict[str, str] = {}
    source_lines = Path(tree._attributes[0] if hasattr(tree, '_attributes') else "").read_text().splitlines() if False else []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    field_name = item.target.id
                    # Get annotation as string
                    ann_str = ast.dump(item.annotation)
                    fields[field_name] = ann_str
            break
    return fields


def extract_class_names(tree: ast.Module) -> list[str]:
    """Extract all top-level class names."""
    return [node.name for node in ast.iter_child_nodes(tree)
            if isinstance(node, ast.ClassDef)]


def check_field_type(ann_dump: str, expected_type: str) -> bool:
    """Check if annotation dump contains expected type substring."""
    if not expected_type:
        return True  # no type constraint
    return expected_type.lower() in ann_dump.lower()


def validate() -> bool:
    """Run all validations. Returns True if all pass."""
    path = find_state_file()
    print(f"Validating: {path}")
    tree = parse_file(path)
    source_text = path.read_text(encoding="utf-8")

    all_class_names = extract_class_names(tree)
    errors: list[str] = []
    warnings: list[str] = []

    # ── Check DocumentState exists ────────────────────────────────────────
    if "DocumentState" not in all_class_names:
        errors.append("DocumentState class not found")
        print(f"FAIL: DocumentState class not found in {path}")
        return False

    # ── Check DocumentState fields ────────────────────────────────────────
    ds_fields = extract_class_fields(tree, "DocumentState")
    print(f"\n  DocumentState has {len(ds_fields)} fields")

    missing_fields = []
    type_mismatches = []

    for field_name, expected_type in DOCUMENT_STATE_FIELDS:
        if field_name not in ds_fields:
            missing_fields.append(field_name)
        elif not check_field_type(ds_fields[field_name], expected_type):
            type_mismatches.append(
                f"  {field_name}: expected type containing '{expected_type}', "
                f"got {ds_fields[field_name]}"
            )

    if missing_fields:
        errors.append(f"Missing DocumentState fields ({len(missing_fields)}): {missing_fields}")

    if type_mismatches:
        for tm in type_mismatches:
            warnings.append(f"Type mismatch: {tm}")

    # ── Check sub-TypedDicts exist ────────────────────────────────────────
    missing_classes = []
    for cls_name in REQUIRED_SUB_TYPEDICTS:
        if cls_name not in all_class_names:
            missing_classes.append(cls_name)

    if missing_classes:
        errors.append(f"Missing sub-TypedDicts: {missing_classes}")

    # ── Check BudgetState fields ──────────────────────────────────────────
    if "BudgetState" in all_class_names:
        bs_fields = extract_class_fields(tree, "BudgetState")
        missing_bs = [f for f, _ in BUDGET_STATE_FIELDS if f not in bs_fields]
        if missing_bs:
            errors.append(f"Missing BudgetState fields: {missing_bs}")
        print(f"  BudgetState has {len(bs_fields)} fields")

    # ── Check add_messages import ─────────────────────────────────────────
    if "add_messages" not in source_text:
        warnings.append("'add_messages' not found in source (needed for companion_messages)")

    # ── Check Source type uses correct literals ───────────────────────────
    if "Source" in all_class_names:
        source_fields = extract_class_fields(tree, "Source")
        if "source_type" in source_fields:
            ann = source_fields["source_type"]
            # Check for resolved conflict C01: must use "web" not "general"
            if "general" in source_text.lower().split("source_type")[1][:200] if "source_type" in source_text else False:
                warnings.append("Source.source_type may contain 'general' — should be 'web' per C01")

    # ── Report ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")
    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠ {w}")
    if not errors and not warnings:
        print("  ✓ All checks passed!")
    elif not errors:
        print(f"\n  ✓ All required fields present ({len(warnings)} warnings)")

    print("=" * 60)

    if errors:
        print(f"\nRESULT: FAIL — {len(errors)} errors found")
        return False
    else:
        print(f"\nRESULT: PASS")
        return True


if __name__ == "__main__":
    success = validate()
    sys.exit(0 if success else 1)
