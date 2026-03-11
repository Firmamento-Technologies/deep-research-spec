#!/usr/bin/env python3
"""Fallback API contract checks when backend test deps are unavailable."""
from pathlib import Path
import re
import sys

runs_py = Path("backend/api/runs.py")
if not runs_py.exists():
    print("Missing backend/api/runs.py")
    sys.exit(1)

text = runs_py.read_text(encoding="utf-8")
required_patterns = [
    r'@router\.post\("/runs".*status_code=201\)',
    r'@router\.get\("/runs".*response_model=.*RunListItem',
    r'@router\.get\("/runs/\{doc_id\}".*RunStatusResponse',
    r'@router\.get\("/runs/\{doc_id\}/stream"\)',
    r'@router\.get\("/runs/\{doc_id\}/events"\)',
    r'@router\.post\("/runs/\{doc_id\}/approve-outline".*status_code=200\)',
    r'@router\.post\("/runs/\{doc_id\}/approve-section".*status_code=200\)',
    r'@router\.delete\("/runs/\{doc_id\}".*status_code=204\)',
]

missing = [p for p in required_patterns if re.search(p, text) is None]
if missing:
    print("Missing required API contract declarations:")
    for pattern in missing:
        print(f" - {pattern}")
    sys.exit(1)

if 'media_type="text/event-stream"' not in text:
    print("SSE contract missing media_type=text/event-stream")
    sys.exit(1)

print("Fallback API contract checks passed")
