"""
Spaces API router.

Rotte:
  GET  /api/spaces                           ← lista spazi
  POST /api/spaces                           ← crea spazio
  DEL  /api/spaces/{id}                      ← elimina spazio + vettori
  GET  /api/spaces/{id}/sources              ← lista fonti dello spazio
  POST /api/spaces/{id}/sources/file         ← upload file (multipart)
  POST /api/spaces/{id}/sources/url          ← aggiungi URL (JSON)
  DEL  /api/spaces/{id}/sources/{sid}        ← rimuovi fonte
  GET  /api/spaces/{id}/sources/{sid}        ← stato fonte (polling)

  POST /api/sources/adhoc/file               ← file ad-hoc (no spazio)
  POST /api/sources/adhoc/url               ← URL ad-hoc
  GET  /api/sources/{sid}/status            ← stato fonte ad-hoc

Tutte le upload ritornano 202 Accepted: parsing/embedding in BackgroundTask.
"""
import mimetypes
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from pydantic import BaseModel, HttpUrl
from services import space_service

router = APIRouter(tags=["spaces"])

ALLOWED_MIME = {
    "application/pdf",
    "text/plain", "text/markdown", "text/x-markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp",
}
MAX_BYTES = 50 * 1024 * 1024  # 50 MB


class CreateSpaceBody(BaseModel):
    name: str
    description: str = ""


class AddUrlBody(BaseModel):
    url: str  # HttpUrl non usato per flessibilità con URL privati/intranet


# ── Spazi ──────────────────────────────────────────────────────────────

@router.get("/spaces")
async def list_spaces():
    return await space_service.list_spaces()


@router.post("/spaces", status_code=201)
async def create_space(body: CreateSpaceBody):
    if not body.name.strip():
        raise HTTPException(422, "Il nome dello spazio non può essere vuoto")
    return await space_service.create_space(body.name.strip(), body.description)


@router.delete("/spaces/{space_id}", status_code=204)
async def delete_space(space_id: str):
    sp = await space_service.get_space(space_id)
    if not sp:
        raise HTTPException(404, "Spazio non trovato")
    await space_service.delete_space(space_id)


# ── Fonti in uno spazio ─────────────────────────────────────────────────

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


@router.delete("/spaces/{space_id}/sources/{source_id}", status_code=204)
async def delete_source(space_id: str, source_id: str):
    sp = await space_service.get_space(space_id)
    if not sp:
        raise HTTPException(404, "Spazio non trovato")
    await space_service.delete_source(space_id, source_id)


# ── Fonti ad-hoc (senza spazio, per singolo run) ───────────────────────

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


# ── Helper condiviso upload file ───────────────────────────────────────────

async def _handle_file(space_id: str | None, file: UploadFile, bg: BackgroundTasks):
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "File troppo grande (max 50 MB)")
    mime = (
        file.content_type
        or mimetypes.guess_type(file.filename or "")[0]
        or "text/plain"
    )
    if mime not in ALLOWED_MIME:
        raise HTTPException(415, f"Tipo file non supportato: {mime}")
    return await space_service.add_file_source(
        space_id, file.filename or "unnamed", content, mime, bg
    )
