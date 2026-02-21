#!/usr/bin/env python3
"""
check_consistency.py — Free deterministic consistency checker
Parses all spec files, extracts agents/inputs/outputs, checks cross-refs.
No API calls. Run after generate_specs.py.
Usage: python check_consistency.py
"""
import re, json
from pathlib import Path
from collections import defaultdict

OUTPUT_DIR = Path("output")
REPORT_FILE = Path("consistency_report.json")

def extract_agents(text: str) -> list[dict]:
    """Extract AGENT blocks from a spec file."""
    agents = []
    pattern = re.compile(
        r'##\s+AGENT:\s+(\w+)\s+\[§([\d.]+)\].*?'
        r'(?:CONSUMES:\s*\[([^\]]*)\])?.*?'
        r'(?:PRODUCES:\s*\[([^\]]*)\].*?(?=##\s+AGENT:|\Z))',
        re.DOTALL
    )
    for m in pattern.finditer(text):
        name     = m.group(1).strip()
        section  = m.group(2).strip()
        consumes = [x.strip() for x in (m.group(3) or "").split(",") if x.strip()]
        produces = [x.strip() for x in (m.group(4) or "").split(",") if x.strip()]
        agents.append({"name": name, "section": section, "consumes": consumes, "produces": produces})
    return agents

def extract_section_refs(text: str) -> list[str]:
    """Extract all §N.M cross-references."""
    return re.findall(r'§([\d.]+)', text)

def extract_thresholds(text: str) -> dict[str, list[str]]:
    """Extract threshold values by name."""
    results = defaultdict(list)
    for m in re.finditer(r'(CSS\w*|threshold|max_iter)\s*[=:≥≤<>]\s*([\d.]+)', text, re.IGNORECASE):
        results[m.group(1).lower()].append(m.group(2))
    return dict(results)

def check_all() -> dict:
    files = sorted(OUTPUT_DIR.glob("*.md"))
    if not files:
        return {"error": f"No files in {OUTPUT_DIR}/"}

    all_agents   = {}   # agent_name → {file, section, consumes, produces}
    all_produces = {}   # field_name → agent_name
    file_refs    = {}   # file → list of §refs used
    file_thresholds = {}

    # Pass 1: collect
    for f in files:
        text = f.read_text(encoding="utf-8")
        agents = extract_agents(text)
        for ag in agents:
            all_agents[ag["name"]] = {**ag, "file": f.name}
            for p in ag["produces"]:
                all_produces[p] = ag["name"]
        file_refs[f.name] = extract_section_refs(text)
        file_thresholds[f.name] = extract_thresholds(text)

    # Pass 2: check
    issues = []

    # 2a. Orphan inputs (consumed but never produced)
    for name, ag in all_agents.items():
        for field in ag["consumes"]:
            if field and field not in all_produces:
                issues.append({
                    "type":     "ORPHAN_INPUT",
                    "severity": "HIGH",
                    "agent":    name,
                    "file":     ag["file"],
                    "detail":   f"Consumes '{field}' but no agent PRODUCES it"
                })

    # 2b. Dead outputs (produced but never consumed)
    all_consumed = {f for ag in all_agents.values() for f in ag["consumes"]}
    for field, producer in all_produces.items():
        if field not in all_consumed:
            issues.append({
                "type":     "DEAD_OUTPUT",
                "severity": "MEDIUM",
                "agent":    producer,
                "file":     all_agents[producer]["file"],
                "detail":   f"Produces '{field}' but nothing consumes it"
            })

    # 2c. Missing section references
    existing_sections = {ag["section"] for ag in all_agents.values()}
    existing_files    = {re.search(r'(\d+)', f.stem).group(1).lstrip("0") or "0"
                         for f in files if re.search(r'(\d+)', f.stem)}
    for fname, refs in file_refs.items():
        for ref in refs:
            top = ref.split(".")[0]
            if top not in existing_files and ref not in existing_sections:
                issues.append({
                    "type":     "MISSING_REF",
                    "severity": "LOW",
                    "file":     fname,
                    "detail":   f"References §{ref} which may not exist"
                })

    # 2d. CSS threshold inconsistencies across files
    css_values = defaultdict(list)
    for fname, thresholds in file_thresholds.items():
        for key, vals in thresholds.items():
            if "css" in key:
                for v in vals:
                    css_values[v].append(fname)

    # Summary
    high   = [i for i in issues if i["severity"] == "HIGH"]
    medium = [i for i in issues if i["severity"] == "MEDIUM"]
    low    = [i for i in issues if i["severity"] == "LOW"]

    return {
        "summary": {
            "files_checked":   len(files),
            "agents_found":    len(all_agents),
            "total_issues":    len(issues),
            "high":            len(high),
            "medium":          len(medium),
            "low":             len(low),
        },
        "agents": list(all_agents.keys()),
        "issues": issues,
        "css_threshold_values_found": dict(css_values),
    }

def main():
    print("=" * 55)
    print("DRS CONSISTENCY CHECKER (free, deterministic)")
    print("=" * 55)

    report = check_all()

    if "error" in report:
        print(f"Error: {report['error']}")
        return

    s = report["summary"]
    print(f"\nFiles checked : {s['files_checked']}")
    print(f"Agents found  : {s['agents_found']}")
    print(f"Issues found  : {s['total_issues']}")
    print(f"  HIGH   : {s['high']}")
    print(f"  MEDIUM : {s['medium']}")
    print(f"  LOW    : {s['low']}")

    if report["issues"]:
        print("\n--- ISSUES ---")
        for issue in report["issues"]:
            sev = issue["severity"]
            print(f"[{sev}] {issue['file']}: {issue['detail']}")

    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nFull report: {REPORT_FILE}")
    print("=" * 55)

if __name__ == "__main__":
    main()
