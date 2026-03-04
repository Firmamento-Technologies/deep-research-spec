"""
Spaces API router.

Rotte spazi:
  GET    /api/spaces                           ← lista spazi
  POST   /api/spaces                           ← crea spazio
  PATCH  /api/spaces/{id}                      ← rinomina / aggiorna desc
  DELETE /api/spaces/{id}                      ← elimina spazio + vettori

Rotte fonti in uno spazio:
  GET    /api/spaces/{id}/sources              ← lista fonti
  POST   /api/spaces/{id}/sources/file         ← upload file (multipart)
  POST   /api/spaces/{id}/sources/url          ← aggiungi URL (JSON)
  GET    /api/spaces/{id}/sources/{sid}        ← stato fonte (polling)
  GET    /api/spaces/{id}/sources/{sid}/stream ← stato fonte (SSE)
  DELETE /api/spaces/{id}/sources/{sid}        ← rimuovi fonte

Rotte fonti ad-hoc (per singolo run, senza spazio persistente):
  POST   /api/sources/adhoc/file               ← file ad-hoc
  POST   /api/sources/adhoc/url                ← URL ad-hoc
  GET    /api/sources/{sid}/status             ← stato (polling)
  GET    /api/sources/{sid}/stream             ← stato (SSE)

Tutte le upload ritornano 202 Accepted: parsing/embedding in BackgroundTask.
L'SSE emette status updates ogni 500ms finché lo status non è ready|error.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services import space_service

router = APIRouter(tags=["spaces"])

ALLOWED_MIME = {
    # Documenti
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/rtf",
    # Testo
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "text/x-rst",     # reStructuredText
    # Immagini (OCR / Vision)
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
}
MAX_BYTES = 50 * 1024 * 1024  # 50 MB

SSE_POLL_INTERVAL = 0.5  # secondi tra poll SSE
SSE_TIMEOUT       = 300  # secondi massimi attesa indexing


# ── Pydantic request models ──────────────────────────────────────────────────────────

class CreateSpaceBody(BaseModel):
    name:        str
    description: str = ""


class UpdateSpaceBody(BaseModel):
    name:        str | None = None
    description: str | None = None


class AddUrlBody(BaseModel):
    url: str  # stringa raw per supportare URL intranet e localhost


# ── SSE helper ───────────────────────────────────────────────────────────────────

async def _source_status_stream(space_id: str | None, source_id: str):
    """
    Generator SSE: emette il JSON della fonte ogni SSE_POLL_INTERVAL finché
    status è 'ready' o 'error', poi chiude lo stream.
    Chiude anche dopo SSE_TIMEOUT secondi per evitare leak.
    """
    elapsed = 0.0
    while elapsed < SSE_TIMEOUT:
        src = await space_service.get_source(space_id, source_id)
        if src is None:
            yield f"data: {json.dumps({'error': 'source not found'})}\n\n"
            return
        payload = json.dumps({
            "id":          src.id,
            "status":      src.status,
            "chunk_count": src.chunk_count,
            "error":       src.error,
            "name":        src.name,
        })
        yield f"data: {payload}\n\n"
        if src.status in ("ready", "error"):
            return
        await asyncio.sleep(SSE_POLL_INTERVAL)
        elapsed += SSE_POLL_INTERVAL
    yield f"data: {json.dumps({'error': 'timeout'})}\n\n"


def _sse_response(generator) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ── Spazi ────────────────────────────────────────────────────────────────────────

@router.get("/spaces")
async def list_spaces():
    return await space_service.list_spaces()


@router.post("/spaces", status_code=201)
async def create_space(body: CreateSpaceBody):
    if not body.name.strip():
        raise HTTPException(422, "Il nome dello spazio non può essere vuoto")
    return await space_service.create_space(body.name.strip(), body.description)


@router.patch("/spaces/{space_id}")
async def update_space(space_id: str, body: UpdateSpaceBody):
    sp = await space_service.update_space(space_id, body.name, body.description)
    if not sp:
        raise HTTPException(404, "Spazio non trovato")
    return sp


@router.delete("/spaces/{space_id}", status_code=204)
async def delete_space(space_id: str):
    sp = await space_service.get_space(space_id)
    if not sp:
        raise HTTPException(404, "Spazio non trovato")
    await space_service.delete_space(space_id)


# ── Fonti in uno spazio ──────────────────────────────────────────────────────────────

@router.get("/spaces/{space_id}/sources")
async def list_sources(space_id: str):
    sp = await space_service.get_space(space_id)
    if not sp:
        raise HTTPException(404, "Spazio non trovato")
    return await space_service.list_sources(space_id)


@router.post("/spaces/{space_id}/sources/file", status_code=202)
async def upload_file_to_space(
    space_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    sp = await space_service.get_space(space_id)
    if not sp:
        raise HTTPException(404, "Spazio non trovato")
    return await _handle_file(space_id, file, background_tasks)


@router.post("/spaces/{space_id}/sources/url", status_code=202)
async def add_url_to_space(
    space_id: str,
    body: AddUrlBody,
    background_tasks: BackgroundTasks,
):
    sp = await space_service.get_space(space_id)
    if not sp:
        raise HTTPException(404, "Spazio non trovato")
    return await space_service.add_url_source(space_id, body.url, background_tasks)


@router.get("/spaces/{space_id}/sources/{source_id}")
async def get_source_status(space_id: str, source_id: str):
    src = await space_service.get_source(space_id, source_id)
    if not src:
        raise HTTPException(404, "Fonte non trovata")
    return src


@router.get("/spaces/{space_id}/sources/{source_id}/stream")
async def stream_source_status(space_id: str, source_id: str):
    """SSE: emette status updates ogni 500ms durante l'indicizzazione."""
    src = await space_service.get_source(space_id, source_id)
    if not src:
        raise HTTPException(404, "Fonte non trovata")
    return _sse_response(_source_status_stream(space_id, source_id))


@router.delete("/spaces/{space_id}/sources/{source_id}", status_code=204)
async def delete_source(space_id: str, source_id: str):
    sp = await space_service.get_space(space_id)
    if not sp:
        raise HTTPException(404, "Spazio non trovato")
    await space_service.delete_source(space_id, source_id)


# ── Fonti ad-hoc (senza spazio, per singolo run) ─────────────────────────────────

@router.post("/sources/adhoc/file", status_code=202)
async def upload_adhoc_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    return await _handle_file(None, file, background_tasks)


@router.post("/sources/adhoc/url", status_code=202)
async def add_adhoc_url(body: AddUrlBody, background_tasks: BackgroundTasks):
    return await space_service.add_url_source(None, body.url, background_tasks)


@router.get("/sources/{source_id}/status")
async def adhoc_status(source_id: str):
    src = await space_service.get_source(None, source_id)
    if not src:
        raise HTTPException(404, "Fonte non trovata")
    return {"id": src.id, "status": src.status,
            "chunk_count": src.chunk_count, "error": src.error}


@router.get("/sources/{source_id}/stream")
async def stream_adhoc_status(source_id: str):
    """SSE: stato fonte ad-hoc durante indicizzazione."""
    src = await space_service.get_source(None, source_id)
    if not src:
        raise HTTPException(404, "Fonte non trovata")
    return _sse_response(_source_status_stream(None, source_id))


# ── Helper condiviso upload file ──────────────────────────────────────────────────────

async def _handle_file(
    space_id: str | None, file: UploadFile, bg: BackgroundTasks
):
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "File troppo grande (max 50 MB)")

    fname = file.filename or "unnamed"
    mime  = (
        file.content_type
        or mimetypes.guess_type(fname)[0]
        or "text/plain"
    )
    # Normalizza mime: .md e .txt possono arrivare come application/octet-stream
    if mime == "application/octet-stream":
        guessed = mimetypes.guess_type(fname)[0]
        if guessed:
            mime = guessed

    if mime not in ALLOWED_MIME:
        raise HTTPException(415, f"Tipo file non supportato: {mime}")

    return await space_service.add_file_source(space_id, fname, content, mime, bg)
