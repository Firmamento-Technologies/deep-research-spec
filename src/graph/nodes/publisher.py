"""Publisher node (§5.22) — format and emit final document.

Assembles all approved sections into the final document,
applies formatting, and writes output files.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def publisher_node(state: dict) -> dict:
    """Assemble and publish the final document.

    Returns:
        Partial state with ``published``, ``output_path``, and
        ``publish_metadata``.
    """
    approved = state.get("approved_sections", [])
    outline = state.get("outline", [])
    config = state.get("config", {})
    doc_id = state.get("doc_id", "default")
    topic = state.get("topic", config.get("topic", "Untitled Document"))

    if not approved:
        logger.warning("Publisher: no approved sections to publish")
        return {"published": False}

    # Build final document
    sections_md = []
    for i, section in enumerate(approved):
        title = section.get("title", f"Section {i + 1}")
        content = section.get("content", section.get("draft", ""))
        sections_md.append(f"## {title}\n\n{content}")

    document = f"# {topic}\n\n" + "\n\n---\n\n".join(sections_md)

    # Write output files
    output_dir = Path("output") / doc_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Main document
    doc_path = output_dir / "document.md"
    doc_path.write_text(document, encoding="utf-8")

    # Metadata
    metadata = {
        "doc_id": doc_id,
        "topic": topic,
        "sections": len(approved),
        "total_words": len(document.split()),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "quality_preset": state.get("budget", {}).get("quality_preset", "balanced"),
        "total_cost": state.get("budget", {}).get("spent_dollars", 0),
        "qa_passed": state.get("qa_passed", False),
    }

    meta_path = output_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    logger.info(
        "Publisher: wrote %d sections to %s (%d words, $%.2f)",
        len(approved), doc_path, metadata["total_words"],
        metadata["total_cost"],
    )

    return {
        "published": True,
        "output_path": str(doc_path),
        "publish_metadata": metadata,
    }
