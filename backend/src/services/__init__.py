"""DRS services package.

Keep package import lightweight while still exposing the historical API
(`run_manager`, `configure_run_manager`) through lazy access.
"""

from __future__ import annotations

from typing import Any

__all__ = ["run_manager", "configure_run_manager"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .run_manager import configure_run_manager, run_manager

        return {
            "run_manager": run_manager,
            "configure_run_manager": configure_run_manager,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
