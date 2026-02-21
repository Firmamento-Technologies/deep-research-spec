#!/usr/bin/env python3
"""
manual_patch.py — Applies surgical patches to fix remaining CRITICAL issues.
No LLM calls. Pure string replacement on the actual file content.
Run: python manual_patch.py
"""
import re
from pathlib import Path

OUTPUT_DIR = Path("output")
BACKUP_DIR = Path("output_backup_manual")
patched = []
failed  = []


def backup(fname: str):
    BACKUP_DIR.mkdir(exist_ok=True)
    src = OUTPUT_DIR / fname
    if src.exists():
        (BACKUP_DIR / fname).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def apply_patch(fname: str, find: str, replace: str, description: str) -> bool:
    path = OUTPUT_DIR / fname
    if not path.exists():
        print(f"  ✗ FILE NOT FOUND: {fname}")
        failed.append(f"{fname} — file not found")
        return False
    content = path.read_text(encoding="utf-8")
    if find not in content:
        print(f"  ⚠ PATTERN NOT FOUND in {fname}: {description}")
        print(f"    Looking for: {repr(find[:80])}")
        failed.append(f"{fname} — pattern not found: {description}")
        return False
    backup(fname)
    new_content = content.replace(find, replace, 1)
    path.write_text(new_content, encoding="utf-8")
    print(f"  ✓ {fname}: {description}")
    patched.append(f"{fname}: {description}")
    return True


print("=" * 60)
print("MANUAL PATCH — DRS Spec CRITICAL fixes")
print("=" * 60)


# ─────────────────────────────────────────────────────────────
# PATCH 1 — 19_budget_controller.md
# CRITICAL: REGIME_PARAMS thresholds must match §9.3 (0.70/0.78)
# ─────────────────────────────────────────────────────────────
print("\n[1/5] Verifying §19.2 REGIME_PARAMS thresholds...")
f19 = (OUTPUT_DIR / "19_budget_controller.md")
if f19.exists():
    c = f19.read_text(encoding="utf-8")
    ok_balanced = "\"css_threshold\": 0.70" in c
    ok_premium  = "\"css_threshold\": 0.78" in c
    if ok_balanced and ok_premium:
        print("  ✓ 19_budget_controller.md: thresholds already correct (0.70/0.78)")
    else:
        apply_patch(
            "19_budget_controller.md",
            "\"css_threshold\": 0.50",
            "\"css_threshold\": 0.70",
            "Balanced css_threshold 0.50 → 0.70 (align to §9.3)"
        )
        apply_patch(
            "19_budget_controller.md",
            "\"css_threshold\": 0.45",
            "\"css_threshold\": 0.78",
            "Premium css_threshold 0.45 → 0.78 (align to §9.3)"
        )
else:
    print("  ✗ 19_budget_controller.md not found")
    failed.append("19_budget_controller.md — not found")


# ─────────────────────────────────────────────────────────────
# PATCH 2 — 01_vision.md
# CRITICAL: §1.4.1 css_threshold comment wrong values
# ─────────────────────────────────────────────────────────────
print("\n[2/5] Patching §1.4.1 DerivedParams css_threshold comment...")
apply_patch(
    "01_vision.md",
    "css_threshold: float            # >=0.65 Economy | >=0.50 Balanced | >=0.45 Premium",
    "css_threshold: float            # >=0.65 Economy | >=0.70 Balanced | >=0.78 Premium",
    "DerivedParams css_threshold aligned to §9.3"
)
# Try UTF-8 ≥ variant too
apply_patch(
    "01_vision.md",
    "css_threshold: float            # ≥0.65 Economy | ≥0.50 Balanced | ≥0.45 Premium",
    "css_threshold: float            # ≥0.65 Economy | ≥0.70 Balanced | ≥0.78 Premium",
    "DerivedParams css_threshold (≥ variant) aligned to §9.3"
)


# ─────────────────────────────────────────────────────────────
# PATCH 3 — 03_input_config.md
# CRITICAL: max_budget_dollars le=10_000.0 → le=500.0
# ─────────────────────────────────────────────────────────────
print("\n[3/5] Patching §03 max_budget_dollars upper bound...")
ok = apply_patch(
    "03_input_config.md",
    "le=10_000.0",
    "le=500.0",
    "max_budget_dollars le=10_000.0 → le=500.0"
)
if not ok:
    apply_patch(
        "03_input_config.md",
        "le=10000.0",
        "le=500.0",
        "max_budget_dollars le=10000.0 → le=500.0"
    )


# ─────────────────────────────────────────────────────────────
# PATCH 4 — 04_architecture.md
# CRITICAL: duplicate route_after_aggregator body
# §9.4 is canonical. §4.5 must only delegate.
# ─────────────────────────────────────────────────────────────
print("\n[4/5] Checking route_after_aggregator in §4.5...")
f04 = OUTPUT_DIR / "04_architecture.md"
if f04.exists():
    c = f04.read_text(encoding="utf-8")
    if "canonical definition: §9.4" in c or "canonical definition is in §9.4" in c or "CANONICAL" in c:
        print("  ✓ 04_architecture.md: already delegates to §9.4")
    elif "def route_after_aggregator" in c:
        old_match = re.search(
            r'(def route_after_aggregator\(state.*?)(?=\ndef [a-z]|\n# ------|\nclass |\Z)',
            c, re.DOTALL
        )
        if old_match:
            stub = (
                'def route_after_aggregator(state: "DocumentState") -> str:\n'
                '    """\n'
                '    CANONICAL implementation is in §9.4 (09_css_aggregator.md).\n'
                '    Return literals: "approved", "force_approve", "fail_reflector",\n'
                '    "fail_style", "panel", "veto", "fail_missing_ev", "budget_hard_stop"\n'
                '    force_approve is checked FIRST — see §9.4 priority order.\n'
                '    """\n'
                '    from src.agents.aggregator import route_after_aggregator as _impl\n'
                '    return _impl(state)\n'
            )
            backup("04_architecture.md")
            new_c = c[:old_match.start()] + stub + c[old_match.end():]
            f04.write_text(new_c, encoding="utf-8")
            print("  ✓ 04_architecture.md: replaced body with delegation stub")
            patched.append("04_architecture.md: route_after_aggregator → delegation stub")
        else:
            print("  ⚠ 04_architecture.md: function found but regex did not match body")
            failed.append("04_architecture.md — regex did not match function body")
    else:
        print("  ✓ 04_architecture.md: no duplicate function found")
else:
    print("  ✗ 04_architecture.md not found")
    failed.append("04_architecture.md — not found")


# ─────────────────────────────────────────────────────────────
# PATCH 5 — 04_architecture.md
# CRITICAL: verify full researcher_targeted edge chain
# ─────────────────────────────────────────────────────────────
print("\n[5/5] Verifying researcher_targeted edge chain...")
f04 = OUTPUT_DIR / "04_architecture.md"
if f04.exists():
    c = f04.read_text(encoding="utf-8")
    edges = [
        'add_edge("researcher_targeted"',
        'add_edge("citation_manager"',
        'add_edge("citation_verifier"',
        'add_edge("source_sanitizer"',
        'add_edge("source_synthesizer"',
    ]
    missing = [e for e in edges if e not in c]
    if not missing:
        print("  ✓ 04_architecture.md: all researcher_targeted edges present")
    else:
        # Add missing edges after researcher_targeted line
        for edge in missing:
            node = edge.split('"')[1]
            print(f"  ⚠ Missing edge definition for: {node}")
            failed.append(f"04_architecture.md — missing edge: {edge}")


# ─────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("PATCH SUMMARY")
print("=" * 60)
print(f"Applied : {len(patched)}")
for p in patched:
    print(f"  ✓ {p}")
if failed:
    print(f"Skipped : {len(failed)}")
    for f in failed:
        print(f"  ⚠ {f}")
print("\nBackups saved to:", BACKUP_DIR)
print("\nNext step: python review_architecture.py")
