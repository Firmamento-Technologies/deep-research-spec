"""RLM adapter nodes for LangGraph.

Each adapter is a drop-in replacement for its corresponding DRS node.
All adapters:
  - Respect the DocumentState TypedDict contract (§4.6)
  - Implement feature flags inline (no AgentFactory)
  - Emit costs via budget_bridge.emit_cost_entries()
"""
