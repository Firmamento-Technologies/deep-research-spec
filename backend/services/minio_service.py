from minio import Minio
from config.settings import settings


class MinioService:
    """
    Handles document storage in MinIO (S3-compatible).
    Bucket: drs-outputs
    Object key pattern: {doc_id}/{format}/output.{format}
    TODO: STEP 12 — integrate with publisher node and download endpoint
    """

    BUCKET = "drs-outputs"

    def __init__(self):
        self.client = Minio(
            settings.minio_url.replace("http://", "").replace("https://", ""),
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_url.startswith("https"),
        )

    def ensure_bucket(self):
        if not self.client.bucket_exists(self.BUCKET):
            self.client.make_bucket(self.BUCKET)

    def get_download_url(self, doc_id: str, fmt: str, expires: int = 3600) -> str:
        from datetime import timedelta
        return self.client.presigned_get_object(
            self.BUCKET,
            f"{doc_id}/{fmt}/output.{fmt}",
            expires=timedelta(seconds=expires),
        )
