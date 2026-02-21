# §0 — Conflict Resolutions (read this first)

## Single Sources of Truth
- CSS thresholds → §9.3 THRESHOLD_TABLE in 09_css_aggregator.md
- Model assignments → §28.2 in 28_llm_assignments.md  
- route_after_aggregator() → §9.4 in 09_css_aggregator.md (only here)
- route_after_reflector() → §12.5 in 12_reflector.md (only here)
- DocumentState schema → §4.6 in 04_architecture.md

## Resolved Values
- economy:  css_content=0.65, css_style=0.75, css_panel_trigger=0.40
- balanced: css_content=0.70, css_style=0.80, css_panel_trigger=0.50
- premium:  css_content=0.78, css_style=0.85, css_panel_trigger=0.55
- judge_r1=deepseek/deepseek-r1
- judge_r2=openai/o3-mini
- judge_r3=qwen/qwq-32b
- MoW: single 'writer' node, asyncio.gather internal
- oscillation: SURGICAL→span_editor, PARTIAL→writer, FULL→await_human

## If you find a conflict in any file, this file wins.
<!-- SPEC_COMPLETE -->
