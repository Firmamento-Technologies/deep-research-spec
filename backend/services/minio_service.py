# MinIO service — stores generated output files (MD, DOCX, PDF, JSON).
# Used by GET /api/runs/{doc_id}/output/{format} in STEP 12.

from __future__ import annotations
import io
from minio import Minio
from minio.error import S3Error
from config.settings import settings

BUCKET = "drs-outputs"

_CONTENT_TYPES: dict[str, str] = {
    "md":   "text/markdown",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf":  "application/pdf",
    "json": "application/json",
}


def _client() -> Minio:
    url = settings.minio_url.replace("http://", "").replace("https://", "")
    return Minio(
        url,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_url.startswith("https://"),
    )


def _ensure_bucket(client: Minio) -> None:
    try:
        if not client.bucket_exists(BUCKET):
            client.make_bucket(BUCKET)
    except S3Error:
        pass


def upload_output(doc_id: str, fmt: str, content: bytes) -> str:
    """Synchronous upload — called from a thread pool in FastAPI endpoints."""
    client = _client()
    _ensure_bucket(client)
    obj = f"{doc_id}/{doc_id}.{fmt}"
    client.put_object(
        BUCKET, obj,
        io.BytesIO(content),
        length=len(content),
        content_type=_CONTENT_TYPES.get(fmt, "application/octet-stream"),
    )
    return obj


def download_output(doc_id: str, fmt: str) -> bytes:
    """Synchronous download — returns raw bytes of the stored file."""
    client = _client()
    obj = f"{doc_id}/{doc_id}.{fmt}"
    response = client.get_object(BUCKET, obj)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
