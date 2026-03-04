"""
Space service — parsing, chunking, embedding, retrieval.

Pipeline per ogni sorgente:
  File   → pymupdf4llm (PDF) / pytesseract OCR (scansionato / img) /
             python-docx (DOCX) / UTF-8 read (MD, TXT)
  URL    → trafilatura (HTML→Markdown, no API key)
  Testo  → overlapping chunker (512 char, overlap 64)
         → SentenceTransformer all-MiniLM-L6-v2 embeddings
         → LanceDB per-space table (embedded, file-based)

Persistenza metadati (space / source):
  DATA_DIR/
    spaces.json
    {space_id}/
      sources.json
      files/           ← raw uploaded files
      vectors/         ← LanceDB native format
    __adhoc__/
      sources.json     ← ad-hoc sources (senza spazio)
      files/
      vectors/
"""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

DATA_DIR   = Path(os.environ.get("SPACES_DATA_DIR", "/data/spaces"))
EMBED_MODEL = "all-MiniLM-L6-v2"   # 90 MB, 384-dim, Apache-2
CHUNK_SIZE  = 512
CHUNK_OV    = 64
TOP_K       = 8
ADHOC_ID    = "__adhoc__"

_embed_model  = None
_spaces_lock  = asyncio.Lock()


# ── Pydantic models ───────────────────────────────────────────────────

class Space(BaseModel):
    id:           str
    name:         str
    description:  str = ""
    created_at:   str
    source_count: int = 0


class Source(BaseModel):
    id:          str
    space_id:    Optional[str]   = None  # None → ad-hoc
    type:        Literal["file", "url"]
    name:        str
    mime_type:   Optional[str]   = None
    size:        Optional[int]   = None
    url:         Optional[str]   = None
    status:      Literal["uploading", "indexing", "ready", "error"] = "uploading"
    chunk_count: int             = 0
    error:       Optional[str]   = None
    created_at:  str


# ── Lazy embed model ─────────────────────────────────────────────────────

def _embed_model_():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(EMBED_MODEL)
    return _embed_model


def _embed(texts: list[str]) -> list[list[float]]:
    m = _embed_model_()
    vecs = m.encode(texts, batch_size=32, show_progress_bar=False)
    return vecs.tolist()


# ── File / dir helpers ──────────────────────────────────────────────────

def _sdir(sid: str | None) -> Path:
    return DATA_DIR / (sid or ADHOC_ID)

def _ensure(sid: str | None):
    d = _sdir(sid)
    (d / "files").mkdir(parents=True, exist_ok=True)
    (d / "vectors").mkdir(exist_ok=True)

def _spaces_file()  -> Path: return DATA_DIR / "spaces.json"
def _sources_file(sid: str | None) -> Path: return _sdir(sid) / "sources.json"

def _read_json(p: Path) -> list[dict]:
    return json.loads(p.read_text("utf-8")) if p.exists() else []

def _write_json(p: Path, data: list[dict]):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _patch_source(space_id: str | None, source_id: str, **kw):
    """Update one source record in-place (called from background tasks)."""
    f = _sources_file(space_id)
    rows = _read_json(f)
    for r in rows:
        if r["id"] == source_id:
            r.update(kw)
    _write_json(f, rows)


# ── Chunking ─────────────────────────────────────────────────────────────

def _chunk(text: str, source_id: str, doc_name: str, space_id: str | None) -> list[dict]:
    chunks, start, idx = [], 0, 0
    text = text.strip()
    while start < len(text):
        t = text[start : start + CHUNK_SIZE].strip()
        if t:
            chunks.append({
                "id":        str(uuid.uuid4()),
                "space_id":  space_id or ADHOC_ID,
                "source_id": source_id,
                "doc_name":  doc_name,
                "chunk_idx": idx,
                "text":      t,
            })
            idx += 1
        start += CHUNK_SIZE - CHUNK_OV
    return chunks


# ── LanceDB ────────────────────────────────────────────────────────────────

def _lance_dir(space_id: str | None) -> str:
    return str(_sdir(space_id) / "vectors")

def _upsert(space_id: str | None, chunks: list[dict]):
    if not chunks:
        return
    import lancedb
    vecs = _embed([c["text"] for c in chunks])
    records = [
        {"id": c["id"], "space_id": c["space_id"], "source_id": c["source_id"],
         "doc_name": c["doc_name"], "chunk_idx": c["chunk_idx"],
         "text": c["text"], "vector": v}
        for c, v in zip(chunks, vecs)
    ]
    db = lancedb.connect(_lance_dir(space_id))
    if "chunks" in db.table_names():
        db.open_table("chunks").add(records)
    else:
        db.create_table("chunks", data=records)

def _delete_source_vectors(space_id: str | None, source_id: str):
    import lancedb
    db = lancedb.connect(_lance_dir(space_id))
    if "chunks" in db.table_names():
        db.open_table("chunks").delete(f'source_id = "{source_id}"')


# ── Text extraction ──────────────────────────────────────────────────────

def _extract(path: Path, mime: str) -> str:
    if mime == "application/pdf":
        return _pdf(path)
    if mime.startswith("image/"):
        return _img_ocr(path)
    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _docx(path)
    # markdown / plain text
    return path.read_text(encoding="utf-8", errors="replace")

def _pdf(path: Path) -> str:
    try:
        import pymupdf4llm
        md = pymupdf4llm.to_markdown(str(path))
        # Se pochissimo testo → PDF scansionato → OCR
        if len(md.strip()) < 80:
            logger.info("PDF scansionato rilevato, avvio OCR: %s", path.name)
            return _pdf_ocr(path)
        return md
    except ImportError:
        return _pdf_ocr(path)

def _pdf_ocr(path: Path) -> str:
    """OCR pagina per pagina con Tesseract (ita+eng)."""
    try:
        import fitz  # PyMuPDF, installato con pymupdf4llm
        from PIL import Image
        import pytesseract
        doc, pages = fitz.open(str(path)), []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            t = pytesseract.image_to_string(img, lang="ita+eng")
            if t.strip():
                pages.append(t)
        doc.close()
        return "\n\n".join(pages)
    except Exception as e:
        logger.error("PDF OCR fallita: %s", e)
        return ""

def _img_ocr(path: Path) -> str:
    from PIL import Image
    import pytesseract
    img = Image.open(path).convert("RGB")
    return pytesseract.image_to_string(img, lang="ita+eng")

def _docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


# ── URL scraping ──────────────────────────────────────────────────────────

async def _scrape(url: str) -> tuple[str, str]:
    """Returns (title, markdown). Usa trafilatura (no API key)."""
    import trafilatura, httpx, re
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        r = await c.get(url, headers={"User-Agent": "DRS-SpaceBot/1.0"})
        r.raise_for_status()
        html = r.text
    text = trafilatura.extract(html, include_tables=True, include_links=False,
                               output_format="markdown") or ""
    m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    title = (m.group(1).strip()[:80] if m else url)
    return title, text


# ── Background tasks ──────────────────────────────────────────────────────

async def _process_file(space_id: str | None, source_id: str,
                        path: Path, mime: str, name: str):
    try:
        _patch_source(space_id, source_id, status="indexing")
        loop  = asyncio.get_event_loop()
        text  = await loop.run_in_executor(None, _extract, path, mime)
        chunks = _chunk(text, source_id, name, space_id)
        _ensure(space_id)
        await loop.run_in_executor(None, _upsert, space_id, chunks)
        _patch_source(space_id, source_id, status="ready", chunk_count=len(chunks))
        logger.info("Indicizzati %d chunk per source %s", len(chunks), source_id)
    except Exception as e:
        logger.error("Errore indicizzazione source %s: %s", source_id, e, exc_info=True)
        _patch_source(space_id, source_id, status="error", error=str(e)[:200])


async def _process_url(space_id: str | None, source_id: str, url: str):
    try:
        _patch_source(space_id, source_id, status="indexing")
        title, text = await _scrape(url)
        chunks = _chunk(text, source_id, title, space_id)
        _ensure(space_id)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _upsert, space_id, chunks)
        # Aggiorna nome con il titolo reale
        _patch_source(space_id, source_id, status="ready",
                      chunk_count=len(chunks), name=title)
    except Exception as e:
        logger.error("Errore scraping URL %s: %s", url, e, exc_info=True)
        _patch_source(space_id, source_id, status="error", error=str(e)[:200])


# ── Public API ─────────────────────────────────────────────────────────────

async def list_spaces() -> list[Space]:
    async with _spaces_lock:
        return [Space(**s) for s in _read_json(_spaces_file())]

async def create_space(name: str, description: str = "") -> Space:
    sp = Space(id=str(uuid.uuid4()), name=name, description=description,
               created_at=datetime.now(timezone.utc).isoformat())
    async with _spaces_lock:
        rows = _read_json(_spaces_file())
        rows.append(sp.model_dump())
        _write_json(_spaces_file(), rows)
    _ensure(sp.id)
    return sp

async def get_space(space_id: str) -> Space | None:
    async with _spaces_lock:
        for s in _read_json(_spaces_file()):
            if s["id"] == space_id:
                return Space(**s)
    return None

async def delete_space(space_id: str):
    async with _spaces_lock:
        rows = [s for s in _read_json(_spaces_file()) if s["id"] != space_id]
        _write_json(_spaces_file(), rows)
    d = _sdir(space_id)
    if d.exists():
        shutil.rmtree(d)

async def list_sources(space_id: str) -> list[Source]:
    return [Source(**s) for s in _read_json(_sources_file(space_id))]

async def get_source(space_id: str | None, source_id: str) -> Source | None:
    for s in _read_json(_sources_file(space_id)):
        if s["id"] == source_id:
            return Source(**s)
    return None

async def add_file_source(
    space_id: str | None, filename: str, content: bytes,
    mime: str, background_tasks
) -> Source:
    _ensure(space_id)
    sid  = str(uuid.uuid4())
    path = _sdir(space_id) / "files" / f"{sid}_{filename}"
    path.write_bytes(content)
    src = Source(id=sid, space_id=space_id, type="file", name=filename,
                 mime_type=mime, size=len(content),
                 created_at=datetime.now(timezone.utc).isoformat())
    rows = _read_json(_sources_file(space_id))
    rows.append(src.model_dump())
    _write_json(_sources_file(space_id), rows)
    _inc_count(space_id)
    background_tasks.add_task(_process_file, space_id, sid, path, mime, filename)
    return src

async def add_url_source(
    space_id: str | None, url: str, background_tasks
) -> Source:
    _ensure(space_id)
    sid = str(uuid.uuid4())
    src = Source(id=sid, space_id=space_id, type="url", name=url[:80],
                 mime_type="text/html", url=url,
                 created_at=datetime.now(timezone.utc).isoformat())
    rows = _read_json(_sources_file(space_id))
    rows.append(src.model_dump())
    _write_json(_sources_file(space_id), rows)
    _inc_count(space_id)
    background_tasks.add_task(_process_url, space_id, sid, url)
    return src

async def delete_source(space_id: str, source_id: str):
    rows = [s for s in _read_json(_sources_file(space_id)) if s["id"] != source_id]
    _write_json(_sources_file(space_id), rows)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _delete_source_vectors, space_id, source_id)
    for f in (_sdir(space_id) / "files").glob(f"{source_id}_*"):
        f.unlink(missing_ok=True)
    _dec_count(space_id)

async def retrieve_chunks(space_id: str, query: str, top_k: int = TOP_K) -> list[dict]:
    """Hybrid retrieval — usato dal Researcher agent in TH."""
    import lancedb
    db = lancedb.connect(_lance_dir(space_id))
    if "chunks" not in db.table_names():
        return []
    q_vec = _embed([query])[0]
    return (
        db.open_table("chunks")
        .search(q_vec).limit(top_k)
        .select(["text", "doc_name", "chunk_idx", "source_id"])
        .to_list()
    )


# ── Internal helpers ───────────────────────────────────────────────────────

def _inc_count(space_id: str | None):
    if not space_id:
        return
    rows = _read_json(_spaces_file())
    for s in rows:
        if s["id"] == space_id:
            s["source_count"] = s.get("source_count", 0) + 1
    _write_json(_spaces_file(), rows)

def _dec_count(space_id: str | None):
    if not space_id:
        return
    rows = _read_json(_spaces_file())
    for s in rows:
        if s["id"] == space_id:
            s["source_count"] = max(0, s.get("source_count", 1) - 1)
    _write_json(_spaces_file(), rows)
