"""
Space service — parsing, chunking, embedding, retrieval.

Pipeline per ogni sorgente:
  File    → parser layer (dual-track)
             • PDF programmatico  → pymupdf4llm (fast-path, ~5ms/pag)
             • PDF scansionato    → Docling dlparse_v2 + OCR on-demand
             • PDF con tabelle    → Docling (detect automatico)
             • DOCX/PPTX         → Docling
             • Immagine           → pytesseract OCR (default)
                                    claude-haiku vision (USE_VISION_FOR_IMAGES=true)
             • MD / TXT           → UTF-8 read
  URL     → trafilatura (no API key, multi-strategy)
  Testo estratto
          → SentenceSplitter (llama-index-core, 512 tok, overlap 64)
          → Hash-cache LlamaIndex: salta re-embedding su file identici
          → SentenceTransformer all-MiniLM-L6-v2 (384-dim, ~90MB)
          → LanceDB per-space table (embedded, Apache Arrow)

Persistenza metadati:
  DATA_DIR/
    spaces.json
    {space_id}/
      sources.json
      files/           ← raw uploaded files
      vectors/         ← LanceDB native format
      cache/           ← LlamaIndex ingestion cache (hash → chunks)
    __adhoc__/         ← fonti ad-hoc (senza spazio)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

DATA_DIR      = Path(os.environ.get("SPACES_DATA_DIR", "/data/spaces"))
EMBED_MODEL   = os.environ.get("EMBED_MODEL", "all-MiniLM-L6-v2")
CHUNK_SIZE    = int(os.environ.get("CHUNK_SIZE",  "512"))   # token
CHUNK_OV      = int(os.environ.get("CHUNK_OV",    "64"))    # token
TOP_K         = int(os.environ.get("RETRIEVAL_K", "8"))
USE_VISION    = os.environ.get("USE_VISION_FOR_IMAGES", "").lower() == "true"
VISION_MODEL  = os.environ.get("VISION_MODEL", "anthropic/claude-3-haiku")
ADHOC_ID      = "__adhoc__"

# Soglia: se un PDF ha meno di N char di testo estratto via pymupdf4llm,
# lo trattiamo come scansionato e invochiamo Docling con OCR.
_SCAN_THRESHOLD = 80

_embed_model  = None
_spaces_lock  = asyncio.Lock()


# ── Pydantic models ─────────────────────────────────────────────────────────────

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
    # SHA-256 del contenuto raw (per hash-cache)
    content_hash: Optional[str]  = None


# ── Lazy models ─────────────────────────────────────────────────────────────────

def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(EMBED_MODEL)
    return _embed_model


def _embed(texts: list[str]) -> list[list[float]]:
    vecs = _get_embed_model().encode(texts, batch_size=32, show_progress_bar=False)
    return vecs.tolist()


# ── File / dir helpers ───────────────────────────────────────────────────────────

def _sdir(sid: str | None) -> Path:
    return DATA_DIR / (sid or ADHOC_ID)

def _ensure(sid: str | None):
    d = _sdir(sid)
    (d / "files").mkdir(parents=True, exist_ok=True)
    (d / "vectors").mkdir(exist_ok=True)
    (d / "cache").mkdir(exist_ok=True)

def _spaces_file()  -> Path: return DATA_DIR / "spaces.json"
def _sources_file(sid: str | None) -> Path: return _sdir(sid) / "sources.json"
def _cache_file(sid: str | None, content_hash: str) -> Path:
    return _sdir(sid) / "cache" / f"{content_hash}.json"

def _read_json(p: Path) -> list[dict]:
    return json.loads(p.read_text("utf-8")) if p.exists() else []

def _write_json(p: Path, data: list[dict]):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _patch_source(space_id: str | None, source_id: str, **kw):
    """Aggiorna un record source in-place."""
    f = _sources_file(space_id)
    rows = _read_json(f)
    for r in rows:
        if r["id"] == source_id:
            r.update(kw)
    _write_json(f, rows)

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── Semantic chunking (LlamaIndex SentenceSplitter) ─────────────────────────────

def _chunk_semantic(
    text: str, source_id: str, doc_name: str, space_id: str | None
) -> list[dict]:
    """
    Usa SentenceSplitter di llama-index-core per chunk sentence-aware.
    Chunk size = CHUNK_SIZE token, overlap = CHUNK_OV token.
    Fallback: char-based se llama-index non disponibile.
    """
    try:
        from llama_index.core.node_parser import SentenceSplitter
        splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OV)
        raw_chunks = splitter.split_text(text.strip())
    except ImportError:
        logger.warning("llama-index-core non disponibile, uso chunker char-based")
        raw_chunks = _chunk_charbase(text)

    return [
        {
            "id":        str(uuid.uuid4()),
            "space_id":  space_id or ADHOC_ID,
            "source_id": source_id,
            "doc_name":  doc_name,
            "chunk_idx": i,
            "text":      t,
        }
        for i, t in enumerate(raw_chunks) if t.strip()
    ]


def _chunk_charbase(text: str) -> list[str]:
    """Fallback: sliding window su caratteri."""
    text  = text.strip()
    out   = []
    start = 0
    while start < len(text):
        out.append(text[start : start + CHUNK_SIZE * 4])
        start += (CHUNK_SIZE - CHUNK_OV) * 4
    return out


# ── Hash-cache (zero re-embed su file identici) ─────────────────────────────────

def _cache_hit(
    space_id: str | None, content_hash: str
) -> list[dict] | None:
    """Restituisce i chunk dalla cache se il file non è cambiato."""
    cf = _cache_file(space_id, content_hash)
    if cf.exists():
        return json.loads(cf.read_text("utf-8"))
    return None


def _cache_store(space_id: str | None, content_hash: str, chunks: list[dict]):
    cf = _cache_file(space_id, content_hash)
    cf.parent.mkdir(parents=True, exist_ok=True)
    cf.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")


# ── LanceDB ────────────────────────────────────────────────────────────────────────

def _lance_dir(space_id: str | None) -> str:
    return str(_sdir(space_id) / "vectors")


def _upsert(space_id: str | None, chunks: list[dict]):
    """Scrive i chunk nel LanceDB della collection dello spazio."""
    if not chunks:
        return
    import lancedb
    vecs    = _embed([c["text"] for c in chunks])
    records = [
        {
            "id":        c["id"],
            "space_id":  c["space_id"],
            "source_id": c["source_id"],
            "doc_name":  c["doc_name"],
            "chunk_idx": c["chunk_idx"],
            "text":      c["text"],
            "vector":    v,
        }
        for c, v in zip(chunks, vecs)
    ]
    db = lancedb.connect(_lance_dir(space_id))
    if "chunks" in db.table_names():
        tbl = db.open_table("chunks")
        tbl.add(records)
    else:
        tbl = db.create_table("chunks", data=records)
    # Crea FTS index per hybrid search (idempotente)
    try:
        tbl.create_fts_index("text", replace=True)
    except Exception:
        pass  # FTS opzionale, non blocca


def _delete_source_vectors(space_id: str | None, source_id: str):
    import lancedb
    db = lancedb.connect(_lance_dir(space_id))
    if "chunks" in db.table_names():
        db.open_table("chunks").delete(f'source_id = "{source_id}"')


# ── Text extraction ───────────────────────────────────────────────────────────────

def _extract(path: Path, mime: str) -> str:
    if mime == "application/pdf":
        return _pdf(path)
    if mime.startswith("image/"):
        return _img_extract(path)
    if mime in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ):
        return _office(path)
    # Markdown, plain text, RST, RTF…
    return path.read_text(encoding="utf-8", errors="replace")


def _pdf(path: Path) -> str:
    """
    Dual-track:
    1. pymupdf4llm → fast-path (PDF programmatico)
    2. Docling     → layout complesso / tabelle / PDF scansionato
    """
    # Fast-path
    try:
        import pymupdf4llm
        md = pymupdf4llm.to_markdown(str(path))
        if len(md.strip()) > _SCAN_THRESHOLD and not _has_complex_layout(md):
            return md
        logger.info("PDF complesso o scansionato, avvio Docling: %s", path.name)
    except ImportError:
        md = ""

    # Docling fallback
    return _pdf_docling(path) or md or _pdf_ocr(path)


def _has_complex_layout(md: str) -> bool:
    """
    Euristica: se il documento ha tabelle (|---) o il testo sembra colonne
    troppo corte per essere prosa normale, usa Docling.
    """
    table_rows = md.count("|---") + md.count("| ---")
    return table_rows >= 3


def _pdf_docling(path: Path) -> str:
    """Usa Docling dlparse_v2 backend per parsing strutturato."""
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

        opts = PdfPipelineOptions()
        opts.do_ocr = False  # OCR on-demand solo se testo assente

        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
        )
        result = converter.convert(str(path))
        md = result.document.export_to_markdown()
        # Se Docling non trova testo → PDF scansionato → OCR
        if len(md.strip()) < _SCAN_THRESHOLD:
            logger.info("Docling: nessun testo, avvio OCR: %s", path.name)
            return _pdf_ocr(path)
        return md
    except Exception as e:
        logger.warning("Docling fallito per %s: %s", path.name, e)
        return ""


def _pdf_ocr(path: Path) -> str:
    """OCR pagina-per-pagina con Tesseract ita+eng."""
    try:
        import fitz
        from PIL import Image
        import pytesseract
        doc, pages = fitz.open(str(path)), []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            t   = pytesseract.image_to_string(img, lang="ita+eng")
            if t.strip():
                pages.append(t)
        doc.close()
        return "\n\n".join(pages)
    except Exception as e:
        logger.error("PDF OCR fallita: %s", e)
        return ""


def _img_extract(path: Path) -> str:
    """
    Immagini: OCR locale (default) oppure Vision model se USE_VISION=true.
    Vision è utile per grafici, diagrammi, screenshot di codice.
    """
    if USE_VISION:
        result = _img_vision(path)
        if result:
            return result
    return _img_ocr(path)


def _img_ocr(path: Path) -> str:
    from PIL import Image
    import pytesseract
    img = Image.open(path).convert("RGB")
    return pytesseract.image_to_string(img, lang="ita+eng")


def _img_vision(path: Path) -> str:
    """Vision via OpenRouter (claude-haiku, ~$0.00025/img)."""
    try:
        import base64, httpx, os
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return ""
        b64 = base64.b64encode(path.read_bytes()).decode()
        suffix = path.suffix.lstrip(".").lower() or "jpeg"
        mime   = f"image/{suffix}"
        payload = {
            "model": VISION_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text",
                     "text": "Descrivi dettagliatamente il contenuto di questa immagine, "
                             "inclusi testi, grafici, tabelle e dati visibili."},
                ],
            }],
        }
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning("Vision fallback a OCR per %s: %s", path.name, e)
        return ""


def _office(path: Path) -> str:
    """DOCX/PPTX tramite Docling (preserva struttura heading/tabelle)."""
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result    = converter.convert(str(path))
        return result.document.export_to_markdown()
    except Exception:
        pass
    # Fallback python-docx per DOCX
    try:
        from docx import Document
        doc = Document(str(path))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        logger.error("Office extraction fallita: %s", e)
        return ""


# ── URL scraping ─────────────────────────────────────────────────────────────────

async def _scrape(url: str) -> tuple[str, str]:
    """Returns (title, markdown). Multi-strategy: trafilatura + readability."""
    import re
    import httpx
    import trafilatura
    async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                  headers={"User-Agent": "DRS-SpaceBot/1.0"}) as c:
        r = await c.get(url)
        r.raise_for_status()
        html = r.text
    text = (
        trafilatura.extract(html, include_tables=True, include_links=False,
                             output_format="markdown")
        or trafilatura.extract(html, favor_recall=True, output_format="markdown")
        or ""
    )
    m     = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    title = m.group(1).strip()[:100] if m else url[:80]
    return title, text


# ── Background tasks ────────────────────────────────────────────────────────────────

async def _process_file(
    space_id: str | None, source_id: str,
    path: Path, mime: str, name: str, content_hash: str
):
    try:
        _patch_source(space_id, source_id, status="indexing")

        # 1. Controlla hash-cache
        cached = _cache_hit(space_id, content_hash)
        if cached:
            logger.info("Cache hit per %s (hash=%s), skip re-embedding", name, content_hash[:8])
            # Riscrive solo i chunk nel LanceDB (lo spazio potrebbe essere nuovo)
            loop = asyncio.get_event_loop()
            new_chunks = [
                {**c, "id": str(uuid.uuid4()), "source_id": source_id,
                 "space_id": space_id or ADHOC_ID}
                for c in cached
            ]
            await loop.run_in_executor(None, _upsert, space_id, new_chunks)
            _patch_source(space_id, source_id, status="ready",
                          chunk_count=len(new_chunks), content_hash=content_hash)
            return

        # 2. Estrazione testo (CPU-bound → executor)
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, _extract, path, mime)

        # 3. Chunking semantico
        chunks = _chunk_semantic(text, source_id, name, space_id)

        # 4. Embedding + LanceDB
        _ensure(space_id)
        await loop.run_in_executor(None, _upsert, space_id, chunks)

        # 5. Salva in cache
        _cache_store(space_id, content_hash, chunks)

        _patch_source(space_id, source_id, status="ready",
                      chunk_count=len(chunks), content_hash=content_hash)
        logger.info("Indicizzati %d chunk per source %s (%s)", len(chunks), source_id, name)
    except Exception as e:
        logger.error("Errore indicizzazione source %s: %s", source_id, e, exc_info=True)
        _patch_source(space_id, source_id, status="error", error=str(e)[:200])


async def _process_url(space_id: str | None, source_id: str, url: str):
    try:
        _patch_source(space_id, source_id, status="indexing")
        title, text = await _scrape(url)

        # Hash del testo estratto (URL cambiano, ma contenuto potrebbe essere cacheabile)
        content_hash = _sha256(text.encode())
        cached = _cache_hit(space_id, content_hash)

        if cached:
            new_chunks = [
                {**c, "id": str(uuid.uuid4()), "source_id": source_id,
                 "space_id": space_id or ADHOC_ID}
                for c in cached
            ]
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _upsert, space_id, new_chunks)
            _patch_source(space_id, source_id, status="ready",
                          chunk_count=len(new_chunks), name=title, content_hash=content_hash)
            return

        chunks = _chunk_semantic(text, source_id, title, space_id)
        _ensure(space_id)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _upsert, space_id, chunks)
        _cache_store(space_id, content_hash, chunks)
        _patch_source(space_id, source_id, status="ready",
                      chunk_count=len(chunks), name=title, content_hash=content_hash)
    except Exception as e:
        logger.error("Errore scraping URL %s: %s", url, e, exc_info=True)
        _patch_source(space_id, source_id, status="error", error=str(e)[:200])


# ── Public API (CRUD) ────────────────────────────────────────────────────────────────

async def list_spaces() -> list[Space]:
    async with _spaces_lock:
        return [Space(**s) for s in _read_json(_spaces_file())]


async def create_space(name: str, description: str = "") -> Space:
    sp = Space(
        id=str(uuid.uuid4()), name=name, description=description,
        created_at=datetime.now(timezone.utc).isoformat()
    )
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


async def update_space(space_id: str, name: str | None, description: str | None) -> Space | None:
    async with _spaces_lock:
        rows = _read_json(_spaces_file())
        for s in rows:
            if s["id"] == space_id:
                if name        is not None: s["name"]        = name
                if description is not None: s["description"] = description
                _write_json(_spaces_file(), rows)
                return Space(**s)
    return None


async def delete_space(space_id: str):
    async with _spaces_lock:
        rows = [s for s in _read_json(_spaces_file()) if s["id"] != space_id]
        _write_json(_spaces_file(), rows)
    d = _sdir(space_id)
    if d.exists():
        shutil.rmtree(d)


async def list_sources(space_id: str | None) -> list[Source]:
    return [Source(**s) for s in _read_json(_sources_file(space_id))]


async def get_source(space_id: str | None, source_id: str) -> Source | None:
    for s in _read_json(_sources_file(space_id)):
        if s["id"] == source_id:
            return Source(**s)
    return None


async def add_file_source(
    space_id: str | None, filename: str, content: bytes,
    mime: str, background_tasks: Any
) -> Source:
    _ensure(space_id)
    sid          = str(uuid.uuid4())
    content_hash = _sha256(content)
    path         = _sdir(space_id) / "files" / f"{sid}_{filename}"
    path.write_bytes(content)
    src = Source(
        id=sid, space_id=space_id, type="file", name=filename,
        mime_type=mime, size=len(content), content_hash=content_hash,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    rows = _read_json(_sources_file(space_id))
    rows.append(src.model_dump())
    _write_json(_sources_file(space_id), rows)
    _inc_count(space_id)
    background_tasks.add_task(
        _process_file, space_id, sid, path, mime, filename, content_hash
    )
    return src


async def add_url_source(
    space_id: str | None, url: str, background_tasks: Any
) -> Source:
    _ensure(space_id)
    sid = str(uuid.uuid4())
    src = Source(
        id=sid, space_id=space_id, type="url", name=url[:80],
        mime_type="text/html", url=url,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    rows = _read_json(_sources_file(space_id))
    rows.append(src.model_dump())
    _write_json(_sources_file(space_id), rows)
    _inc_count(space_id)
    background_tasks.add_task(_process_url, space_id, sid, url)
    return src


async def delete_source(space_id: str | None, source_id: str):
    rows = [s for s in _read_json(_sources_file(space_id)) if s["id"] != source_id]
    _write_json(_sources_file(space_id), rows)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _delete_source_vectors, space_id, source_id)
    for f in (_sdir(space_id) / "files").glob(f"{source_id}_*"):
        f.unlink(missing_ok=True)
    _dec_count(space_id)


async def retrieve_chunks(
    space_id: str, query: str, top_k: int = TOP_K
) -> list[dict]:
    """
    Hybrid retrieval per il Researcher agent (TH).
    Combina vector search (HNSW) e full-text search (BM25) via Reciprocal Rank Fusion.
    """
    import lancedb
    db = lancedb.connect(_lance_dir(space_id))
    if "chunks" not in db.table_names():
        return []
    tbl   = db.open_table("chunks")
    q_vec = _embed([query])[0]

    # Vector search
    vec_results = (
        tbl.search(q_vec).limit(top_k * 2)
        .select(["id", "text", "doc_name", "chunk_idx", "source_id"])
        .to_list()
    )

    # Full-text search (BM25, se FTS index presente)
    try:
        fts_results = (
            tbl.search(query, query_type="fts").limit(top_k * 2)
            .select(["id", "text", "doc_name", "chunk_idx", "source_id"])
            .to_list()
        )
    except Exception:
        fts_results = []

    # Reciprocal Rank Fusion (k=60)
    scores: dict[str, float] = {}
    for rank, r in enumerate(vec_results):
        scores[r["id"]] = scores.get(r["id"], 0) + 1 / (60 + rank + 1)
    for rank, r in enumerate(fts_results):
        scores[r["id"]] = scores.get(r["id"], 0) + 1 / (60 + rank + 1)

    # Merge e deduplica
    seen, merged = set(), []
    for r in vec_results + fts_results:
        if r["id"] not in seen:
            seen.add(r["id"])
            merged.append(r)

    merged.sort(key=lambda r: scores.get(r["id"], 0), reverse=True)
    return merged[:top_k]


# ── Internal helpers ─────────────────────────────────────────────────────────────────

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
