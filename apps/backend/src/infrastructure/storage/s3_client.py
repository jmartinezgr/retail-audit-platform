"""
Cliente S3-compatible (SDK `minio`, funciona igual contra MinIO local o
Cloudflare R2 en prod - ver Settings.S3_* en infrastructure/config/settings.py).
"""

from datetime import timedelta
from io import BytesIO

from minio import Minio

from src.infrastructure.config.settings import settings


def get_s3_client() -> Minio:

    client = Minio(
        endpoint=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY,
        secure=settings.S3_SECURE,
    )

    # Create bucket if it doesn't exist
    if not client.bucket_exists(settings.S3_BUCKET):
        client.make_bucket(settings.S3_BUCKET)

    return client


def get_object_bytes(object_name: str) -> bytes:
    """Descarga el contenido completo de un objeto del bucket."""
    client = get_s3_client()
    response = client.get_object(settings.S3_BUCKET, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def put_object_bytes(object_name: str, data: bytes, content_type: str) -> None:
    """Sube bytes directo al bucket (sin URL prefirmada - uso server-side)."""
    client = get_s3_client()
    client.put_object(
        settings.S3_BUCKET,
        object_name,
        BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def get_presigned_download_url(object_name: str, expires_minutes: int = 30) -> str:
    client = get_s3_client()
    return client.presigned_get_object(
        settings.S3_BUCKET,
        object_name,
        expires=timedelta(minutes=expires_minutes),
    )
