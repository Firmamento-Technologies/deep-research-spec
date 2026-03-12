"""Internal utilities for the graph pipeline.

These modules are NOT graph nodes — they are helper functions called by actual
nodes (writer, section_checkpoint, etc.). Moved from src/graph/nodes/ for clarity.

See graph.py:66 — "MoW nodes... are NOT graph nodes"
"""
