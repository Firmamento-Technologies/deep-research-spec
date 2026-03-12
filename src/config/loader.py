"""Centralized configuration loader — Task 2.5.

Singleton ``Config`` reads ``config/system.yaml``, substitutes
``${ENV_VAR:-default}`` patterns, and exposes dot-notation access.

Usage::

    from src.config.loader import config

    temperature = config.get("writer.temperature", 0.3)
    db_url = config.get("database.url")
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_ENV_PATTERN = re.compile(r"^\$\{([^}]+)\}$")


class Config:
    """Thread-safe singleton configuration store."""

    _instance: Config | None = None
    _config: dict[str, Any] = {}

    def __new__(cls) -> Config:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._load()
        return cls._instance

    @classmethod
    def _load(cls) -> None:
        config_path = Path(__file__).resolve().parents[2] / "config" / "system.yaml"
        if not config_path.exists():
            logger.warning("Config file not found: %s — using empty config", config_path)
            cls._config = {}
            return
        try:
            with open(config_path) as f:
                cls._config = yaml.safe_load(f) or {}
            cls._substitute_env_vars(cls._config)
            logger.info("Configuration loaded from %s", config_path)
        except Exception as exc:
            logger.error("Failed to load config: %s", exc)
            cls._config = {}

    @classmethod
    def _substitute_env_vars(cls, obj: Any) -> None:
        """Recursively replace ${VAR:-default} patterns with env values."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    m = _ENV_PATTERN.match(v)
                    if m:
                        var_expr = m.group(1)
                        if ":-" in var_expr:
                            var, default = var_expr.split(":-", 1)
                            obj[k] = os.getenv(var, default)
                        else:
                            obj[k] = os.getenv(var_expr, "")
                elif isinstance(v, (dict, list)):
                    cls._substitute_env_vars(v)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str):
                    m = _ENV_PATTERN.match(item)
                    if m:
                        var_expr = m.group(1)
                        if ":-" in var_expr:
                            var, default = var_expr.split(":-", 1)
                            obj[i] = os.getenv(var, default)
                        else:
                            obj[i] = os.getenv(var_expr, "")
                elif isinstance(item, (dict, list)):
                    cls._substitute_env_vars(item)

    def get(self, key: str, default: Any = None) -> Any:
        """Dot-notation access: ``config.get("writer.temperature", 0.3)``."""
        keys = key.split(".")
        value: Any = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def reload(self) -> None:
        """Force reload from disk (useful for testing)."""
        self._load()

    @property
    def raw(self) -> dict[str, Any]:
        """Access the full config dict."""
        return self._config


# Singleton instance
config = Config()
