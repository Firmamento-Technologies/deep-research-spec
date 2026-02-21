#!/usr/bin/env python3
"""
review_architecture.py — Single-call architectural review with retry + streaming.
Usage: python review_architecture.py
"""
import os, re, json, time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from json_repair import repair_json

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL       = "anthropic/claude-sonnet-4-6"
MAX_TOKENS  = 12000
MAX_RETRIES = 3
OUTPUT_DIR  = Path("output")
REPORT_FILE = Path("architecture_review.json")

REVIEW_PROMPT = """You are a senior distributed systems architect reviewing AI-readable specifications
for the Deep Research System (DRS), a multi-agent document generation system.

Review ALL the spec files below and produce a structured JSON report identifying:

1. LOGIC_ERROR: A component cannot do its job (missing input, impossible output, deadlock)
2. MISSING_COMPONENT: A needed function has no owner (gap in the pipeline)
3. INCONSISTENCY: Same value defined differently across files (thresholds, model names, field names)
4. UNREACHABLE_STATE: A graph state/edge that can never be triggered
5. AMBIGUITY: A constraint too vague for an AI developer to implement

For each issue:
- type: one of the 5 types above
- severity: CRITICAL | HIGH | MEDIUM
- files_affected: list of filenames
- description: precise description of the problem
- fix_suggestion: concrete actionable fix (1-2 sentences)

Output ONLY valid JSON in this exact format:
{
  "review_summary": "3 sentences max describing overall architecture quality",
  "issues": [
    {
      "type": "LOGIC_ERROR",
      "severity": "CRITICAL",
      "files_affected": ["05_agents.md", "04_architecture.md"],
      "description": "...",
      "fix_suggestion": "..."
    }
  ],
  "missing_components": ["list of components not specced but referenced"],
  "positive_observations": ["max 3 things done well"]
}

--- SPEC FILES START ---
{specs}
--- SPEC FILES END ---"""


def compress(text: str) -> str:
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
    return text.strip()


def load_all_specs() -> str:
    files = sorted(OUTPUT_DIR.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No spec files in {OUTPUT_DIR}/")
    parts = []
    for f in files:
        parts.append(f"### FILE: {f.name}\n{compress(f.read_text(encoding='utf-8'))}")
    combined = "\n\n---\n\n".join(parts)
    print(f"Loaded {len(files)} files → {len(combined):,} chars (~{len(combined)//4:,} tokens)")
    return combined


def extract_json(raw: str) -> dict:
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    candidate = m.group(1) if m else raw[raw.find("{"):raw.rfind("}")+1]
    if not candidate:
        Path("raw_response_debug.txt").write_text(raw, encoding="utf-8")
        raise ValueError("No JSON found. Saved to raw_response_debug.txt")
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON malformed ({e}), attempting repair...")
        repaired = repair_json(candidate, return_objects=True)
        print("✅ JSON repaired successfully")
        return repaired


def call_streaming(client: OpenAI, prompt: str) -> str:
    """Use streaming to avoid HTTP timeout on long responses."""
    chunks = []
    stream = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        extra_headers={
            "HTTP-Referer": "https://github.com/deep-research-spec",
            "X-Title": "DRS Architectural Review",
        },
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            chunks.append(delta)
    return "".join(chunks)


def main():
    print("=" * 55)
    print("DRS ARCHITECTURAL REVIEW")
    print(f"Model: {MODEL} | MAX_TOKENS: {MAX_TOKENS} | Retries: {MAX_RETRIES}")
    print("=" * 55)

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in .env")

    specs = load_all_specs()
    prompt = REVIEW_PROMPT.replace("{specs}", specs)
    est_cost = (len(prompt) // 4 / 1e6 * 3) + (MAX_TOKENS / 1e6 * 15)
    print(f"Estimated cost: ${est_cost:.2f}")
    print("Sending review request (streaming)...")

    client = OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        timeout=600.0,   # 10 min — enough for 145k token input
    )

    raw = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  Attempt {attempt}/{MAX_RETRIES}...")
            t0 = time.time()
            raw = call_streaming(client, prompt)
            elapsed = time.time() - t0
            print(f"  Done in {elapsed:.1f}s | {len(raw):,} chars received")
            break
        except Exception as e:
            print(f"  ✗ Error: {e}")
            if attempt < MAX_RETRIES:
                wait = 10 * attempt
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print("  All retries failed.")
                return

    # Save raw always
    Path("raw_response_debug.txt").write_text(raw, encoding="utf-8")

    report = extract_json(raw)
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'='*55}")
    print("REVIEW COMPLETE")
    print(f"{'='*55}")
    print(f"\nSummary: {report.get('review_summary', 'N/A')}")

    issues   = report.get("issues", [])
    critical = [i for i in issues if i.get("severity") == "CRITICAL"]
    high     = [i for i in issues if i.get("severity") == "HIGH"]
    medium   = [i for i in issues if i.get("severity") == "MEDIUM"]

    print(f"\nIssues: {len(issues)} total")
    print(f"  CRITICAL : {len(critical)}")
    print(f"  HIGH     : {len(high)}")
    print(f"  MEDIUM   : {len(medium)}")

    if report.get("missing_components"):
        print(f"\nMissing components:")
        for c in report["missing_components"]:
            print(f"  - {c}")

    print(f"\nFull report: {REPORT_FILE}")
    print("\nNext step: python fix_all_critical.py")


if __name__ == "__main__":
    main()