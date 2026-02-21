#!/usr/bin/env python3
"""
fix_all_critical.py — Single LLM call fixing ALL CRITICAL issues.
Legge i CRITICAL da architecture_review.json, raccoglie i file,
manda una sola chiamata in streaming con istruzioni esplicite per file.
"""
import os, json, time, re
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL       = "anthropic/claude-sonnet-4-6"
MAX_TOKENS  = 80000
MAX_RETRIES = 3
OUTPUT_DIR  = Path("output")
BACKUP_DIR  = Path("output_backup_atomic")

SYSTEM_PROMPT = """You are a senior distributed systems architect fixing specification files.

CRITICAL REQUIREMENT: You MUST output a <<<FILE>>> block for EVERY file listed under
"FILES YOU MUST MODIFY" — even if the changes are small. Do not skip any file.

OUTPUT FORMAT — use this exact delimiter for every file:
<<<FILE: filename.md>>>
<complete corrected file content — never truncate>
<<<END_FILE>>>

Rules:
- Output ONLY <<<FILE>>> blocks, no prose outside them
- Every output file MUST end with exactly: <!-- SPEC_COMPLETE -->
- Output the COMPLETE file content — never truncate mid-file
- If a file was damaged/truncated in a previous edit, restore it fully from the provided content
"""

def load_review() -> tuple[list[dict], list[dict]]:
    path = Path("architecture_review.json")
    if not path.exists():
        raise FileNotFoundError("architecture_review.json not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    issues = data.get("issues", [])
    return (
        [i for i in issues if i["severity"] == "CRITICAL"],
        [i for i in issues if i["severity"] == "HIGH"],
    )

def collect_files(criticals: list[dict]) -> list[str]:
    seen, result = set(), []
    for issue in criticals:
        for f in issue.get("files_affected", []):
            if f not in seen and (OUTPUT_DIR / f).exists():
                seen.add(f)
                result.append(f)
    return result

def backup(fnames: list[str]):
    BACKUP_DIR.mkdir(exist_ok=True)
    for f in fnames:
        p = OUTPUT_DIR / f
        if p.exists():
            (BACKUP_DIR / f).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

def build_prompt(files: dict[str, str], criticals: list[dict]) -> str:
    # Issue list
    issue_text = ""
    for n, issue in enumerate(criticals, 1):
        issue_text += (
            f"CRITICAL {n} [{issue['type']}]\n"
            f"  Files  : {', '.join(issue['files_affected'])}\n"
            f"  Problem: {issue['description']}\n"
            f"  Fix    : {issue['fix_suggestion']}\n\n"
        )

    # Explicit per-file instructions
    file_instructions = {
        "09_css_aggregator.md": (
            "RESTORE complete file. Must contain: §9.1 CSS formula, §9.2 JURY_WEIGHTS, "
            "§9.3 THRESHOLD_TABLE with ALL three presets (economy/balanced/premium) and ALL three "
            "threshold types (css_content_threshold, css_style_threshold, css_panel_trigger), "
            "§9.4 route_after_aggregator() CANONICAL implementation (do NOT reference §10 — "
            "this IS the canonical definition), §9.5 panel self-loop, §9.6 Aggregator agent spec."
        ),
        "10_minority_veto.md": (
            "REMOVE any implementation of route_after_aggregator() — replace with a comment "
            "pointing to §9.4 as canonical. Keep only veto condition definitions."
        ),
        "04_architecture.md": (
            "Fix: (1) MoW topology — use single \'writer\' node with asyncio.gather internally, "
            "remove writer_a/b/c from NODES list; "
            "(2) oscillation_check must use scope-aware routing: SURGICAL→span_editor, PARTIAL→writer; "
            "(3) context_compressor must NOT run on section_idx==0 — add conditional skip; "
            "(4) add targeted_research_active: bool to DocumentState; "
            "(5) css_content_current, css_style_current, css_composite_current must be in DocumentState."
        ),
        "05_agents.md": (
            "Fix: (1) align oscillation_check routing with §12.5 (SURGICAL→span_editor, PARTIAL→writer); "
            "(2) add §5.22 LengthAdjuster agent spec; "
            "(3) add targeted_research_active flag usage in researcher_targeted and source_synthesizer."
        ),
        "07_mixture_of_writers.md": (
            "Fix MoW topology to use single \'writer\' node with asyncio.gather internally. "
            "Remove all references to writer_a/writer_b/writer_c as separate graph nodes."
        ),
        "12_reflector.md": (
            "Ensure route_after_reflector routes: SURGICAL→oscillation_check (which then→span_editor), "
            "PARTIAL→oscillation_check (which then→writer), FULL→await_human. "
            "This must match §4.5 graph edges exactly."
        ),
        "08_jury_system.md": (
            "Fix §8.5 JURY_TIERS: judge_r1 primary=deepseek/deepseek-r1, "
            "judge_r2 primary=openai/o3-mini, judge_r3 primary=qwen/qwq-32b (align to §28.2)."
        ),
        "01_vision.md": (
            "Fix §1.4.1 DerivedParams comment for css_threshold: "
            "≥0.65 Economy | ≥0.70 Balanced | ≥0.78 Premium (align to §9.3)."
        ),
        "19_budget_controller.md": (
            "Fix §19.2 REGIME_PARAMS: Balanced css_threshold=0.70, Premium css_threshold=0.78 "
            "(align to §9.3 THRESHOLD_TABLE)."
        ),
        "03_input_config.md": (
            "Fix jury config: define jury_reasoning as three independent slots "
            "(judge_r1, judge_r2, judge_r3) each with own primary+fallbacks, not shared tier1/tier2/tier3."
        ),
        "29_yaml_config.md": (
            "Fix ModelsConfig: jury_reasoning must be per-slot (r1/r2/r3) matching §28.2, "
            "not shared tier1/tier2/tier3."
        ),
    }

    # Files section
    files_text = ""
    for fname, content in files.items():
        instruction = file_instructions.get(fname, "Fix as needed based on CRITICAL issues above.")
        files_text += (
            f"<<<CURRENT: {fname}>>>\n"
            f"INSTRUCTION FOR THIS FILE: {instruction}\n\n"
            f"{content}\n"
            f"<<<END_CURRENT>>>\n\n"
        )

    must_modify = ", ".join(files.keys())

    return (
        f"FILES YOU MUST MODIFY (output a <<<FILE>>> block for EACH one): {must_modify}\n\n"
        f"CRITICAL ISSUES:\n{issue_text}"
        f"FILES:\n{files_text}"
    )

def call_streaming(client: OpenAI, messages: list) -> tuple[str, bool]:
    chunks = []
    finished_stop = False
    stream = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=messages,
        stream=True,
        extra_headers={
            "HTTP-Referer": "https://github.com/deep-research-spec",
            "X-Title": "DRS Critical Fixer",
        },
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            chunks.append(delta)
        if chunk.choices[0].finish_reason == "stop":
            finished_stop = True
    return "".join(chunks), finished_stop

def parse_response(raw: str, valid: list[str]) -> dict[str, str]:
    pattern = r'<<<FILE:\s*([^>\n]+)>>>\s*(.*?)<<<END_FILE>>>' 
    result = {}
    for fname, content in re.findall(pattern, raw, re.DOTALL):
        fname = fname.strip()
        if fname in valid:
            result[fname] = content.strip()
        else:
            print(f"  ⚠ Skipping unknown filename: {repr(fname[:60])}")
    return result

def main():
    print("=" * 60)
    print("FIX ALL CRITICAL — Single streaming call")
    print(f"Model: {MODEL} | MAX_TOKENS: {MAX_TOKENS}")
    print("=" * 60)

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in .env")

    criticals, _ = load_review()
    print(f"\nCRITICAL issues: {len(criticals)}")
    for i, issue in enumerate(criticals, 1):
        print(f"  {i}. {issue['type']} — {', '.join(issue['files_affected'])}")

    fnames = collect_files(criticals)
    # Always include 29_yaml_config.md if present (needed for CRITICAL 2)
    for extra in ["29_yaml_config.md", "10_minority_veto.md"]:
        if extra not in fnames and (OUTPUT_DIR / extra).exists():
            fnames.append(extra)

    files = {f: (OUTPUT_DIR / f).read_text(encoding="utf-8") for f in fnames}
    total_chars = sum(len(c) for c in files.values())
    est_in  = total_chars // 4
    est_cost = (est_in / 1e6 * 3.0) + (MAX_TOKENS / 1e6 * 15.0)

    print(f"\nFiles: {len(files)} — {fnames}")
    print(f"Input ~{est_in:,} tokens | Est. cost ~${est_cost:.2f}")

    backup(fnames)
    print(f"Backed up to {BACKUP_DIR}/")

    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        timeout=600.0,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": build_prompt(files, criticals)},
    ]

    raw, finished_ok = "", False
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"\nAttempt {attempt}/{MAX_RETRIES}...")
            t0 = time.time()
            raw, finished_ok = call_streaming(client, messages)
            elapsed = time.time() - t0
            print(f"Done in {elapsed:.1f}s | {len(raw):,} chars | finish_stop={finished_ok}")
            break
        except Exception as e:
            print(f"  ✗ {e}")
            if attempt < MAX_RETRIES:
                wait = 10 * attempt
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)

    Path("fix_all_critical_raw.txt").write_text(raw, encoding="utf-8")

    if not raw:
        print("\n✗ No response. Check fix_all_critical_raw.txt")
        return

    if not finished_ok:
        print("\n⚠ Response may be truncated (finish_reason != stop)")

    fixed = parse_response(raw, fnames)
    if not fixed:
        print("\n✗ No <<<FILE>>> blocks found. Check fix_all_critical_raw.txt")
        return

    print(f"\nSaving {len(fixed)} files...")
    saved = []
    for fname, content in fixed.items():
        if "<!-- SPEC_COMPLETE -->" not in content:
            print(f"  ⚠ {fname}: missing SPEC_COMPLETE tag")
        (OUTPUT_DIR / fname).write_text(content, encoding="utf-8")
        print(f"  ✓ {fname}")
        saved.append(fname)

    not_saved = [f for f in fnames if f not in saved]
    print(f"\n{'='*60}")
    print(f"Fixed    : {len(saved)}")
    if not_saved:
        print(f"NOT saved: {not_saved}")
        print("  → Relancia lo script per i file mancanti")
    print(f"Raw      : fix_all_critical_raw.txt")
    print(f"\nNext: python review_architecture.py")
    print("=" * 60)

if __name__ == "__main__":
    main()