"""S3-compatible upload/download/presigned URLs — §33.5, §33.8 canonical.

Uses boto3 for MinIO/S3 compatibility. In production, MinIO runs as a Docker
service (``minio:9000``). For cloud migration, swap ``MINIO_ENDPOINT`` to the
real S3 endpoint.

Output formats: DOCX, PDF, Markdown, LaTeX, HTML, JSON (see §33.8).
"""
from __future__ import annotations

import io
import logging
from typing import Literal

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

OutputFormat = Literal["docx", "pdf", "markdown", "latex", "html", "json"]

# Default presigned URL expiry (15 min — §33.8)
PRESIGNED_URL_EXPIRY: int = 900

# Default bucket name (override via env MINIO_BUCKET)
DEFAULT_BUCKET: str = "drs-documents"


class MinIOClient:
    """Thin async-friendly wrapper around boto3 S3 client for MinIO.

    Note: boto3 is synchronous. For async contexts, call methods via
    ``asyncio.to_thread()`` or use in a thread pool executor.

    Args:
        endpoint: MinIO endpoint (e.g. ``"minio:9000"``).
        access_key: MinIO access key.
        secret_key: MinIO secret key.
        bucket: Bucket name (default ``drs-documents``).
        secure: Use HTTPS (default ``False`` for local dev).
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str = DEFAULT_BUCKET,
        secure: bool = False,
    ) -> None:
        scheme = "https" if secure else "http"
        self._client = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",  # MinIO ignores this but boto3 requires it
        )
        self._bucket = bucket

    def ensure_bucket(self) -> None:
        """Create the bucket if it doesn't exist."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)
            logger.info("Created MinIO bucket: %s", self._bucket)

    # ── Upload ───────────────────────────────────────────────────────────

    def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload raw bytes to MinIO.

        Args:
            key: S3 object key (e.g. ``"runs/{run_id}/output.docx"``).
            data: Raw bytes to upload.
            content_type: MIME content type.

        Returns:
            The object key.
        """
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=io.BytesIO(data),
            ContentLength=len(data),
            ContentType=content_type,
        )
        logger.debug("Uploaded %d bytes to s3://%s/%s", len(data), self._bucket, key)
        return key

    def upload_file(self, key: str, file_path: str) -> str:
        """Upload a local file to MinIO.

        Args:
            key: S3 object key.
            file_path: Absolute path to the local file.

        Returns:
            The object key.
        """
        self._client.upload_file(file_path, self._bucket, key)
        logger.debug("Uploaded file %s to s3://%s/%s", file_path, self._bucket, key)
        return key

    # ── Download ─────────────────────────────────────────────────────────

    def download_bytes(self, key: str) -> bytes:
        """Download object as bytes.

        Args:
            key: S3 object key.

        Returns:
            Raw bytes of the object.
        """
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def download_file(self, key: str, file_path: str) -> None:
        """Download object to a local file.

        Args:
            key: S3 object key.
            file_path: Local destination path.
        """
        self._client.download_file(self._bucket, key, file_path)

    # ── Presigned URLs ───────────────────────────────────────────────────

    def presigned_download_url(self, key: str, expiry: int = PRESIGNED_URL_EXPIRY) -> str:
        """Generate a presigned GET URL for downloading.

        Args:
            key: S3 object key.
            expiry: URL validity in seconds (default 900 = 15 min).

        Returns:
            Presigned URL string.
        """
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expiry,
        )

    def presigned_upload_url(self, key: str, expiry: int = PRESIGNED_URL_EXPIRY) -> str:
        """Generate a presigned PUT URL for uploading (e.g. uploaded_sources).

        Args:
            key: S3 object key.
            expiry: URL validity in seconds (default 900 = 15 min).

        Returns:
            Presigned URL string.
        """
        return self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expiry,
        )

    # ── Delete ───────────────────────────────────────────────────────────

    def delete_object(self, key: str) -> None:
        """Delete an object from MinIO."""
        self._client.delete_object(Bucket=self._bucket, Key=key)

    # ── List ─────────────────────────────────────────────────────────────

    def list_objects(self, prefix: str) -> list[str]:
        """List object keys under a prefix.

        Args:
            prefix: Key prefix (e.g. ``"runs/{run_id}/"``).

        Returns:
            List of object key strings.
        """
        response = self._client.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
        return [obj["Key"] for obj in response.get("Contents", [])]


# ── Factory ──────────────────────────────────────────────────────────────────

def build_minio_client(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str = DEFAULT_BUCKET,
    secure: bool = False,
) -> MinIOClient:
    """Build and initialise a MinIO client, ensuring the bucket exists.

    Args:
        endpoint: MinIO endpoint (e.g. ``"minio:9000"``).
        access_key: MinIO access key.
        secret_key: MinIO secret key.
        bucket: Bucket name.
        secure: Use HTTPS.

    Returns:
        Initialised ``MinIOClient``.
    """
    client = MinIOClient(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket=bucket,
        secure=secure,
    )
    client.ensure_bucket()
    return client


# ── Key helpers ──────────────────────────────────────────────────────────────

# Standard key patterns for DRS outputs
CONTENT_TYPES: dict[OutputFormat, str] = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "markdown": "text/markdown",
    "latex": "application/x-latex",
    "html": "text/html",
    "json": "application/json",
}


def output_key(run_id: str, fmt: OutputFormat) -> str:
    """Build the standard S3 key for a run output file.

    Args:
        run_id: Run UUID string.
        fmt: Output format.

    Returns:
        S3 object key, e.g. ``"runs/abc123/output.pdf"``.
    """
    ext_map: dict[OutputFormat, str] = {
        "docx": "docx",
        "pdf": "pdf",
        "markdown": "md",
        "latex": "tex",
        "html": "html",
        "json": "json",
    }
    return f"runs/{run_id}/output.{ext_map[fmt]}"


def uploaded_source_key(run_id: str, filename: str) -> str:
    """Build the S3 key for an uploaded source file.

    Args:
        run_id: Run UUID string.
        filename: Original filename.

    Returns:
        S3 object key, e.g. ``"runs/abc123/sources/paper.pdf"``.
    """
    return f"runs/{run_id}/sources/{filename}"
