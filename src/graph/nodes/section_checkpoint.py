"""§5.21 — SectionCheckpoint node.

Single authoritative point where:
  1. A section transitions from in-progress → approved in PostgreSQL.
  2. currentsectionidx is incremented (only after successful INSERT).
  3. WriterMemory is refreshed with new verdicts/violations.
  4. SSE event SECTION_APPROVED is emitted to the Run Companion.
  5. [NEW] Approved section is mirrored to disk as Markdown for
     real-time human observation during the generation process.

Filesystem mirror layout::

    output/
    └── {doc_id}/
        ├── sections/
        │   ├── 00_introduction.md      ← written on §0 approval
        │   ├── 01_methodology.md       ← written on §1 approval
        │   └── ...
        ├── _live_document.md           ← append-only, grows in real time
        └── _run_metrics.json           ← updated after every checkpoint

The filesystem mirror is:
- Non-blocking: I/O errors are logged and never propagated to the graph.
- Written AFTER the PostgreSQL INSERT succeeds — never before.
- Idempotent: re-runs overwrite the same file safely.
- Observable with ``tail -f output/{doc_id}/_live_document.md``
  or any Markdown-aware editor (VSCode, Obsidian, …).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore

from src.models.state import DocumentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers — Markdown mirror (§5.21 extension)
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = "output"
_SLUG_RE = re.compile(r"[^\w\s-]")


def _slugify(text: str, max_len: int = 40) -> str:
    """Lowercase ASCII slug suitable for filenames."""
    text = text.lower().strip()
    text = _SLUG_RE.sub("", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:max_len].rstrip("_")


def _section_frontmatter(
    section_idx: int,
    title: str,
    css_final: float,
    css_content: float,
    css_style: float,
    iterations_used: int,
    approved_at: str,
) -> str:
    return textwrap.dedent(f"""\
        ---
        section: {section_idx}
        title: "{title}"
        css_final: {css_final:.4f}
        css_content: {css_content:.4f}
        css_style: {css_style:.4f}
        iterations_used: {iterations_used}
        approved_at: {approved_at}
        ---

    """)


def _write_section_markdown(
    doc_id: str,
    section_idx: int,
    title: str,
    content: str,
    css_final: float,
    css_content: float,
    css_style: float,
    iterations_used: int,
    approved_at: str,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> Path | None:
    """Write one approved section to ``output/{doc_id}/sections/{idx}_{slug}.md``.

    Returns the Path on success, None on failure (failure is logged, not raised).
    """
    try:
        folder = Path(output_dir) / doc_id / "sections"
        folder.mkdir(parents=True, exist_ok=True)

        filename = f"{section_idx:02d}_{_slugify(title)}.md"
        filepath = folder / filename

        fm = _section_frontmatter(
            section_idx, title, css_final, css_content, css_style,
            iterations_used, approved_at,
        )
        filepath.write_text(fm + content, encoding="utf-8")
        logger.debug("[checkpoint] section markdown written → %s", filepath)
        return filepath
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[checkpoint] failed to write section markdown (non-blocking): %s", exc
        )
        return None


def _append_to_live_document(
    doc_id: str,
    section_idx: int,
    title: str,
    content: str,
    css_final: float,
    approved_at: str,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> None:
    """Append approved section to ``output/{doc_id}/_live_document.md``.

    The file grows incrementally — observable in real time with::

        tail -f output/{doc_id}/_live_document.md

    Failure is logged and never propagated.
    """
    try:
        live_doc = Path(output_dir) / doc_id / "_live_document.md"
        live_doc.parent.mkdir(parents=True, exist_ok=True)

        separator = "\n\n---\n" if live_doc.exists() and live_doc.stat().st_size > 0 else ""
        block = (
            f"{separator}\n"
            f"## {section_idx:02d}. {title}\n"
            f"<!-- approved_at={approved_at} css={css_final:.3f} -->\n\n"
            f"{content}\n"
        )
        with live_doc.open("a", encoding="utf-8") as fh:
            fh.write(block)

        logger.debug("[checkpoint] live document updated → %s", live_doc)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[checkpoint] failed to update live document (non-blocking): %s", exc
        )


def _update_run_metrics_json(
    doc_id: str,
    section_idx: int,
    title: str,
    css_final: float,
    css_content: float,
    css_style: float,
    iterations_used: int,
    approved_at: str,
    total_sections: int,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> None:
    """Keep ``output/{doc_id}/_run_metrics.json`` up to date after each checkpoint.

    Failure is logged and never propagated.
    """
    try:
        metrics_path = Path(output_dir) / doc_id / "_run_metrics.json"
        metrics_path.parent.mkdir(parents=True, exist_ok=True)

        existing: dict[str, Any] = {}
        if metrics_path.exists():
            try:
                existing = json.loads(metrics_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass  # overwrite corrupted file

        sections: list[dict[str, Any]] = existing.get("sections", [])
        sections = [s for s in sections if s.get("section_idx") != section_idx]
        sections.append({
            "section_idx": section_idx,
            "title": title,
            "css_final": round(css_final, 4),
            "css_content": round(css_content, 4),
            "css_style": round(css_style, 4),
            "iterations_used": iterations_used,
            "approved_at": approved_at,
        })
        sections.sort(key=lambda s: s["section_idx"])

        payload = {
            "doc_id": doc_id,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "sections_approved": len(sections),
            "total_sections": total_sections,
            "sections": sections,
        }
        metrics_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.debug("[checkpoint] run metrics JSON updated → %s", metrics_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[checkpoint] failed to update run metrics JSON (non-blocking): %s", exc
        )


# ---------------------------------------------------------------------------
# PostgreSQL helpers (§5.21)
# ---------------------------------------------------------------------------

_INSERT_SQL = """
    INSERT INTO sections (
        document_id, run_id, section_index, title, content,
        css_final, css_breakdown, iterations_used, verdicts_history,
        approved_at, version
    ) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9::jsonb, $10, $11)
    ON CONFLICT (document_id, section_index, version) DO NOTHING
"""


async def _db_insert_section(
    conn: asyncpg.Connection,
    doc_id: str,
    run_id: str,
    section_idx: int,
    title: str,
    content: str,
    css_final: float,
    css_breakdown: dict[str, float],
    iterations_used: int,
    verdicts_history: list[dict],
    approved_at: datetime,
    version: int = 1,
) -> None:
    """Insert one section row. ON CONFLICT DO NOTHING ensures idempotency."""
    await conn.execute(
        _INSERT_SQL,
        doc_id,
        run_id,
        section_idx,
        title,
        content,
        css_final,
        json.dumps(css_breakdown),
        iterations_used,
        json.dumps(verdicts_history),
        approved_at,
        version,
    )


async def _insert_with_retry(
    db_dsn: str,
    *args: Any,
    max_retries: int = 3,
) -> None:
    """Retry DB INSERT up to *max_retries* times with 1s / 2s / 4s backoff."""
    delays = [1, 2, 4]
    last_exc: Exception | None = None

    for attempt, delay in enumerate(delays[:max_retries], start=1):
        try:
            conn: asyncpg.Connection = await asyncpg.connect(db_dsn)
            try:
                await _db_insert_section(conn, *args)
                return  # success
            finally:
                await conn.close()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "[checkpoint] DB INSERT attempt %d/%d failed: %s",
                attempt, max_retries, exc,
            )
            if attempt < max_retries:
                await asyncio.sleep(delay)

    raise RuntimeError(
        f"SectionCheckpoint DB INSERT failed after {max_retries} retries"
    ) from last_exc


# ---------------------------------------------------------------------------
# WriterMemory update stub (§5.18)
# ---------------------------------------------------------------------------

def _update_writer_memory(
    state: DocumentState,
    new_verdicts: list[dict],
    new_violations: list[dict],
    section_idx: int,
    draft: str,
) -> dict[str, Any]:
    """Synchronous accumulator — updates WriterMemory in DocumentState.

    Full logic lives in src/graph/nodes/writer_memory.py (§5.18).
    This shim calls it directly so SectionCheckpoint stays decoupled.
    """
    try:
        from src.graph.nodes.writer_memory import update_writer_memory  # lazy import
        return update_writer_memory(
            existing=state.get("writer_memory", {}),
            new_verdicts=new_verdicts,
            new_violations=new_violations,
            section_idx=section_idx,
            draft=draft,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[checkpoint] WriterMemory update failed (non-blocking): %s", exc
        )
        return state.get("writer_memory", {})


# ---------------------------------------------------------------------------
# SSE emission stub (§5.21 — Run Companion §6)
# ---------------------------------------------------------------------------

def _emit_section_approved_sse(
    doc_id: str,
    section_idx: int,
    css_final: float,
    approved_at: str,
) -> None:
    """Emit SECTION_APPROVED SSE event to the Run Companion stream (§6).

    Full implementation lives in src/sse/emitter.py.
    Failure is non-blocking.
    """
    try:
        from src.sse.emitter import emit  # lazy import
        emit(
            event="SECTION_APPROVED",
            data={
                "doc_id": doc_id,
                "section_index": section_idx,
                "css_final": round(css_final, 4),
                "approved_at": approved_at,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[checkpoint] SSE emit failed (non-blocking): %s", exc
        )


# ---------------------------------------------------------------------------
# Main node entrypoint (§5.21)
# ---------------------------------------------------------------------------

async def run(state: DocumentState) -> DocumentState:  # type: ignore[return]
    """SectionCheckpoint node — §5.21.

    Invariants (never violated)::

        currentsectionidx increments ONLY after DB INSERT succeeds.
        Filesystem writes happen ONLY after DB INSERT succeeds.
        Filesystem failures never block section advancement.
    """
    doc_id: str = state["doc_id"]
    run_id: str = state["run_id"]
    section_idx: int = state["current_section_idx"]
    content: str = state["current_draft"]
    css_history: list[float] = state.get("css_history", [])
    all_verdicts: list[list[dict]] = state.get("all_verdicts_history", [])
    style_violations: list[dict] = state.get("style_lint_violations", [])
    outline: list[dict] = state["outline"]
    total_sections: int = state["total_sections"]
    db_dsn: str = state["config"]["db_dsn"]
    output_dir: str = state["config"].get("output_dir", DEFAULT_OUTPUT_DIR)

    section_meta = outline[section_idx]
    title: str = section_meta["title"]

    css_final: float = css_history[-1] if css_history else 0.0
    # Aggregator breakdown stored in state by §9.1
    agg: dict[str, Any] = state.get("aggregator_verdict") or {}
    css_content: float = agg.get("css_content", css_final)
    css_style: float = agg.get("css_style", css_final)
    iterations_used: int = len(css_history)
    # Flatten all verdicts for this section
    flat_verdicts: list[dict] = [v for round_ in all_verdicts for v in round_]
    approved_at_dt: datetime = datetime.now(timezone.utc)
    approved_at_iso: str = approved_at_dt.isoformat()
    version: int = 1  # incremented on regeneration

    css_breakdown = {
        "css_content": round(css_content, 4),
        "css_style": round(css_style, 4),
    }

    # ------------------------------------------------------------------
    # Step 1 — PostgreSQL INSERT (retry ×3, raises on total failure)
    # NEVER increment currentsectionidx before this succeeds.
    # ------------------------------------------------------------------
    try:
        await _insert_with_retry(
            db_dsn,
            doc_id,
            run_id,
            section_idx,
            title,
            content,
            css_final,
            css_breakdown,
            iterations_used,
            flat_verdicts,
            approved_at_dt,
            version,
        )
    except RuntimeError:
        logger.error(
            "[checkpoint] CHECKPOINT_FAILED for section %d — section not advanced",
            section_idx,
        )
        return {**state, "status": "CHECKPOINT_FAILED"}  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Step 2 — Filesystem mirror [NEW]
    # Non-blocking: errors are logged, never raised.
    # ------------------------------------------------------------------
    _write_section_markdown(
        doc_id=doc_id,
        section_idx=section_idx,
        title=title,
        content=content,
        css_final=css_final,
        css_content=css_content,
        css_style=css_style,
        iterations_used=iterations_used,
        approved_at=approved_at_iso,
        output_dir=output_dir,
    )
    _append_to_live_document(
        doc_id=doc_id,
        section_idx=section_idx,
        title=title,
        content=content,
        css_final=css_final,
        approved_at=approved_at_iso,
        output_dir=output_dir,
    )
    _update_run_metrics_json(
        doc_id=doc_id,
        section_idx=section_idx,
        title=title,
        css_final=css_final,
        css_content=css_content,
        css_style=css_style,
        iterations_used=iterations_used,
        approved_at=approved_at_iso,
        total_sections=total_sections,
        output_dir=output_dir,
    )

    # ------------------------------------------------------------------
    # Step 3 — WriterMemory update (synchronous, non-blocking on error)
    # ------------------------------------------------------------------
    updated_memory = _update_writer_memory(
        state=state,
        new_verdicts=flat_verdicts,
        new_violations=style_violations,
        section_idx=section_idx,
        draft=content,
    )

    # ------------------------------------------------------------------
    # Step 4 — Append to approved_sections in DocumentState
    # ------------------------------------------------------------------
    new_entry: dict[str, Any] = {
        "idx": section_idx,
        "title": title,
        "content": content,
        "css_final": css_final,
        "css_history": css_history,
        "css_breakdown": css_breakdown,
        "iterations_used": iterations_used,
        "verdicts_history": flat_verdicts,
        "approved_at": approved_at_iso,
        "version": version,
    }
    approved_sections: list[dict] = list(state.get("approved_sections") or [])
    approved_sections.append(new_entry)

    # ------------------------------------------------------------------
    # Step 5 — SSE event (non-blocking)
    # ------------------------------------------------------------------
    _emit_section_approved_sse(
        doc_id=doc_id,
        section_idx=section_idx,
        css_final=css_final,
        approved_at=approved_at_iso,
    )

    # ------------------------------------------------------------------
    # Step 6 — Increment currentsectionidx (LAST, after all writes)
    # ------------------------------------------------------------------
    next_idx = section_idx + 1
    logger.info(
        "[checkpoint] §%d '%s' approved | css=%.3f | iter=%d | next_idx=%d",
        section_idx, title, css_final, iterations_used, next_idx,
    )

    return {  # type: ignore[return-value]
        **state,
        "approved_sections": approved_sections,
        "current_section_idx": next_idx,
        "writer_memory": updated_memory,
        # Reset per-section state for the next section
        "current_draft": "",
        "current_iteration": 1,
        "css_history": [],
        "all_verdicts_history": [],
        "style_lint_violations": [],
        "post_draft_gaps": [],
        "reflector_output": None,
        "aggregator_verdict": None,
        "draft_embeddings": [],
        "oscillation_detected": False,
        "oscillation_type": None,
    }
