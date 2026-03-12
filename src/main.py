"""DRS CLI entrypoint — §4.5 pipeline invocation.

Usage:
    python -m src.main --topic "Machine Learning" --words 5000
    python -m src.main --config config/my_project.yaml
    python -m src.main --topic "AI Safety" --preset premium --style academic
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv  # type: ignore
load_dotenv()  # Load .env before any config/API key access

import yaml  # type: ignore

from src.config.schema import DRSYAMLConfig
from src.graph.graph import build_graph
from src.graph.state import DocumentState
from src.observability.metrics import (
    start_metrics_server,
    update_budget_gauge,
    DRS_PIPELINE_DURATION,
)

logger = logging.getLogger("drs")


# ── Logging Setup ────────────────────────────────────────────────────────────

def _setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure structured logging."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stderr)
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
    root.addHandler(handler)


class _JsonFormatter(logging.Formatter):
    """Structured JSON log output."""
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        })


# ── Config Loading ───────────────────────────────────────────────────────────

def _load_config(config_path: str | None) -> DRSYAMLConfig:
    """Load YAML config file, returning defaults if not found."""
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        logger.info("Loaded config from %s", config_path)
        return DRSYAMLConfig(**data)

    # Try default paths
    for default in ("config/drs.yaml", "config/drs.yml", "drs.yaml"):
        if Path(default).exists():
            with open(default) as f:
                data = yaml.safe_load(f) or {}
            logger.info("Loaded config from %s", default)
            return DRSYAMLConfig(**data)

    logger.info("No config file found — using defaults")
    return DRSYAMLConfig()


# ── Initial State Builder ────────────────────────────────────────────────────

def _build_initial_state(
    topic: str,
    target_words: int,
    quality_preset: str,
    style_profile: str,
    max_budget: float,
    config: DRSYAMLConfig,
) -> dict:
    """Build the initial DocumentState for graph invocation."""
    thread_id = str(uuid.uuid4())

    return {
        # Core fields
        "doc_id": thread_id,
        "topic": topic,
        "target_words": target_words,
        "style_profile": style_profile,
        "quality_preset": quality_preset,
        "document_type": "",
        "outline": [],
        "outline_approved": False,
        "current_section_idx": 0,
        "total_sections": 0,
        "current_draft": "",
        "current_iteration": 1,
        "approved_sections": [],

        # Budget
        "budget": {
            "quality_preset": quality_preset,
            "max_dollars": max_budget,
            "spent_dollars": 0.0,
            "hard_stop_fired": False,
        },

        # Config
        "config": {
            "topic": topic,
            "target_words": target_words,
            "quality_preset": quality_preset,
            "style_profile": style_profile,
            "auto_approve_outline": not config.defaults.hitl_enabled,
            "auto_resolve_escalations": not config.defaults.hitl_enabled,
            "output_formats": config.defaults.output_formats,
            "convergence": {
                "panel_max_rounds": config.convergence.panel_max_rounds,
                "oscillation_soft_limit": config.convergence.oscillation_soft_limit,
                "oscillation_hard_limit": config.convergence.oscillation_hard_limit,
                "jury_weights": config.convergence.jury_weights,
            },
        },

        # Thread ID for checkpointing
        "thread_id": thread_id,

        # RAG / SHINE
        "shine_active": False,
        "compressed_corpus": "",
        "citation_map": {},

        # Writer memory
        "writer_memory": {},

        # MoW (internal)
        "mow_active": False,
        "mow_drafts": [],

        # Jury
        "jury_verdicts": [],
        "css_history": [],

        # Coherence
        "coherence_conflicts": [],

        # Escalation
        "force_approve": False,
        "human_review_pending": None,
        "escalation_log": [],
    }


# ── Checkpointer ─────────────────────────────────────────────────────────────

def _get_checkpointer():
    """Get PostgreSQL checkpointer, falling back to MemorySaver."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            logger.info("Using PostgreSQL checkpointer")
            return AsyncPostgresSaver.from_conn_string(db_url)
        except Exception as exc:
            logger.warning("PostgreSQL checkpointer failed: %s — using MemorySaver", exc)

    from langgraph.checkpoint.memory import MemorySaver
    logger.info("Using in-memory checkpointer (MemorySaver)")
    return MemorySaver()


# ── Main Pipeline ─────────────────────────────────────────────────────────────

async def run_pipeline(
    topic: str,
    target_words: int = 5000,
    quality_preset: str = "balanced",
    style_profile: str = "academic",
    max_budget: float = 50.0,
    config_path: str | None = None,
) -> dict:
    """Run the full DRS pipeline.

    Args:
        topic: Research topic / question
        target_words: Target document length
        quality_preset: economy | balanced | premium
        style_profile: Style profile name
        max_budget: Maximum budget in USD
        config_path: Optional path to YAML config

    Returns:
        Final DocumentState dict
    """
    config = _load_config(config_path)

    # CLI overrides take precedence over YAML
    if target_words == 5000:  #  default
        target_words = config.defaults.target_words
    if max_budget == 50.0:  # default
        max_budget = config.defaults.max_budget_dollars

    initial_state = _build_initial_state(
        topic=topic,
        target_words=target_words,
        quality_preset=quality_preset,
        style_profile=style_profile,
        max_budget=max_budget,
        config=config,
    )

    checkpointer = _get_checkpointer()
    graph = build_graph(checkpointer=checkpointer)

    thread_id = initial_state["thread_id"]
    logger.info(
        "Starting DRS pipeline — topic='%s' words=%d preset=%s thread=%s",
        topic, target_words, quality_preset, thread_id,
    )

    import time
    t0 = time.perf_counter()

    try:
        result = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        raise

    duration_s = time.perf_counter() - t0
    DRS_PIPELINE_DURATION.observe(duration_s)

    # Summary
    sections = result.get("approved_sections", [])
    budget_data = result.get("budget", {})
    cost = budget_data.get("spent_dollars", 0)
    max_budget_val = budget_data.get("max_dollars", max_budget)

    update_budget_gauge(thread_id, cost, max_budget_val)

    logger.info(
        "Pipeline complete — %d sections, $%.4f spent, %.1fs elapsed, thread=%s",
        len(sections), cost, duration_s, thread_id,
    )

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="drs",
        description="Deep Research System — AI-powered document generation",
    )
    parser.add_argument(
        "--topic", "-t",
        required=True,
        help="Research topic or question",
    )
    parser.add_argument(
        "--words", "-w",
        type=int, default=5000,
        help="Target word count (default: 5000)",
    )
    parser.add_argument(
        "--preset", "-p",
        choices=["economy", "balanced", "premium"],
        default="balanced",
        help="Quality preset (default: balanced)",
    )
    parser.add_argument(
        "--style", "-s",
        default="academic",
        help="Style profile (default: academic)",
    )
    parser.add_argument(
        "--budget",
        type=float, default=50.0,
        help="Maximum budget in USD (default: 50.0)",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )
    parser.add_argument(
        "--log-format",
        choices=["json", "text"],
        default="text",
        help="Log format (default: text)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint."""
    args = _parse_args(argv)
    _setup_logging(level=args.log_level, fmt=args.log_format)

    # Start Prometheus metrics endpoint
    start_metrics_server(port=9090)

    # Graceful shutdown
    loop = asyncio.new_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: loop.stop())
        except NotImplementedError:
            pass  # Windows

    try:
        result = loop.run_until_complete(
            run_pipeline(
                topic=args.topic,
                target_words=args.words,
                quality_preset=args.preset,
                style_profile=args.style,
                max_budget=args.budget,
                config_path=args.config,
            )
        )

        # Output summary
        sections = result.get("approved_sections", [])
        budget = result.get("budget", {})
        print(f"\n{'='*60}")
        print(f"DRS Pipeline Complete")
        print(f"{'='*60}")
        print(f"Topic:    {args.topic}")
        print(f"Sections: {len(sections)}")
        print(f"Cost:     ${budget.get('spent_dollars', 0):.4f} / ${budget.get('max_dollars', 0):.2f}")
        print(f"Preset:   {args.preset}")
        print(f"{'='*60}")

    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(130)
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc)
        sys.exit(1)
    finally:
        loop.close()


if __name__ == "__main__":
    main()
