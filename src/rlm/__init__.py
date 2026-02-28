"""RLM (Recursive Language Model) integration layer for DRS.

Public API:
    RLMRuntime   — core sandboxed REPL runtime
    RLMResult    — result dataclass
    get_rlm_runtime — factory with DRS-safe defaults
"""

from src.rlm.runtime import RLMRuntime, RLMResult, get_rlm_runtime

__all__ = ["RLMRuntime", "RLMResult", "get_rlm_runtime"]
