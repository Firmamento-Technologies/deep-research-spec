#!/usr/bin/env python3
"""
fix_specs.py — Targeted regeneration of files with architectural issues.
Reads architecture_review.json, regenerates ONLY the affected files
with targeted feedback, then auto-runs review_architecture.py to validate.
Usage: python fix_specs.py
"""
import os
import json
import time
import subprocess
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL       = "anthropic/claude-sonnet-4-6"
MAX_TOKENS  = 16000
OUTPUT_DIR  = Path("output")
SOURCE_DIR  = Path("source")
REVIEW_FILE = Path("architecture_review.json")
BACKUP_DIR  = Path("output_backup")


def load_sources() -> str:
    parts = []
    for path in sorted(SOURCE_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        parts.append(f"{'='*60}\nSOURCE: {path.name}\n{'='*60}\n{content}")
    return "\n".join(parts)


def backup_files(files: list[str]):
    """Backup all files before modifying them."""
    BACKUP_DIR.mkdir(exist_ok=True)
    for fname in files:
        src = OUTPUT_DIR / fname
        if src.exists():
            (BACKUP_DIR / fname).write_text(
                src.read_text(encoding="utf-8"), encoding="utf-8"
            )
    print(f"  📦 Backup saved to {BACKUP_DIR}/")


def get_files_to_fix() -> dict[str, list[dict]]:
    """Returns {filename: [issue dicts]} from architecture_review.json.
    Includes CRITICAL and HIGH issues only.
    """
    if not REVIEW_FILE.exists():
        raise FileNotFoundError(
            f"{REVIEW_FILE} not found. Run python review_architecture.py first."
        )

    report = json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
    to_fix: dict[str, list[dict]] = {}

    for issue in report.get("issues", []):
        if issue["severity"] not in ("CRITICAL", "HIGH"):
            continue
        for fname in issue.get("files_affected", []):
            to_fix.setdefault(fname, []).append(issue)

    # Also include missing components if they reference existing files
    for comp in report.get("missing_components", []):
        # missing components are strings — attach to index file for awareness
        pass

    return to_fix


def build_prompt(filename: str, issues: list[dict], original: str, sources: str) -> str:
    # Format issues as a numbered, structured list
    issues_text = ""
    for i, issue in enumerate(issues, 1):
        issues_text += f"""
{i}. [{issue['type']}] severity={issue['severity']}
   PROBLEM: {issue['description']}
   FIX:     {issue['fix_suggestion']}
"""

    return f"""You are a senior distributed systems architect fixing a technical specification file.

FILE TO FIX: {filename}

IDENTIFIED ISSUES (fix ALL of them):
{issues_text}

CURRENT FILE CONTENT:
{original}

SOURCE MATERIAL (ground truth):
{sources}

INSTRUCTIONS:
- Fix EVERY issue listed above. Do not skip any.
- Change ONLY the parts of the file affected by the issues. Do not rewrite correct sections.
- Maintain the existing format: typed Python contracts, structured headers, English.
- All thresholds, weights, and model names must be explicit literal values — no ranges, no "TBD".
- If a fix requires adding a new section or field, append it at the end of the relevant section.
- Do NOT add explanatory meta-comments like "# FIXED:" in the output — just the corrected spec.
- End the file with exactly this tag on its own line: <!-- SPEC_COMPLETE -->"""


def fix_file(
    client: OpenAI,
    filename: str,
    issues: list[dict],
    sources: str,
) -> str:
    original = (OUTPUT_DIR / filename).read_text(encoding="utf-8") \
        if (OUTPUT_DIR / filename).exists() else "(file not found — create from scratch)"

    prompt = build_prompt(filename, issues, original, sources)

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
        extra_headers={
            "HTTP-Referer": "https://github.com/deep-research-spec",
            "X-Title": "DRS Spec Fixer",
        },
    )
    content = response.choices[0].message.content

    # Warn if completion tag is missing (truncated response)
    if "<!-- SPEC_COMPLETE -->" not in content:
        print("  ⚠️  WARNING: <!-- SPEC_COMPLETE --> tag missing — response may be truncated")

    return content


def print_summary(to_fix: dict[str, list[dict]], fixed: int, failed: list[str]):
    total = len(to_fix)
    print(f"\n{'='*55}")
    print(f"FIX COMPLETE")
    print(f"{'='*55}")
    print(f"  Fixed  : {fixed}/{total} files")
    if failed:
        print(f"  Failed : {failed}")

    # Count issues by severity
    all_issues = [i for issues in to_fix.values() for i in issues]
    critical   = sum(1 for i in all_issues if i["severity"] == "CRITICAL")
    high       = sum(1 for i in all_issues if i["severity"] == "HIGH")
    print(f"  Issues addressed: {critical} CRITICAL, {high} HIGH")


def run_validation():
    """Re-run review_architecture.py to validate fixes."""
    print(f"\n{'='*55}")
    print("🔄  Running validation review...")
    print(f"{'='*55}\n")
    result = subprocess.run(["python", "review_architecture.py"])
    if result.returncode != 0:
        print("⚠️  Validation review failed — check errors above.")


def main():
    print("=" * 55)
    print("DRS SPEC FIXER — Targeted regeneration")
    print(f"Model: {MODEL}")
    print("=" * 55)

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in .env")

    to_fix = get_files_to_fix()
    if not to_fix:
        print("\n✅ No CRITICAL/HIGH issues found. Architecture is clean!")
        return

    print(f"\nFiles to fix : {len(to_fix)}")
    for fname, issues in to_fix.items():
        severities = [i["severity"] for i in issues]
        print(f"  {fname}: {len(issues)} issue(s) {severities}")

    # Estimate cost: input = original file + sources (~50k chars) + issues
    # Output = MAX_TOKENS per file
    est_input_tokens  = len(to_fix) * (50_000 // 4)
    est_output_tokens = len(to_fix) * MAX_TOKENS
    est_cost = (est_input_tokens / 1e6 * 3) + (est_output_tokens / 1e6 * 15)
    print(f"\nEstimated cost: ${est_cost:.2f}")

    # Backup before touching anything
    backup_files(list(to_fix.keys()))

    client  = OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
    sources = load_sources()
    fixed   = 0
    failed  = []

    for i, (fname, issues) in enumerate(to_fix.items(), 1):
        print(f"\n[{i}/{len(to_fix)}] Fixing: {fname}", flush=True)
        for issue in issues:
            print(f"  → [{issue['severity']}] {issue['description'][:80]}...", flush=True)

        try:
            content = fix_file(client, fname, issues, sources)
            (OUTPUT_DIR / fname).write_text(content, encoding="utf-8")
            print(f"  ✅ Saved", flush=True)
            fixed += 1
        except Exception as e:
            print(f"  ❌ Failed: {e}", flush=True)
            failed.append(fname)

        # Rate limit respect
        if i < len(to_fix):
            time.sleep(2)

    print_summary(to_fix, fixed, failed)

    # Auto-validate: re-run the review
    run_validation()


if __name__ == "__main__":
    main()
