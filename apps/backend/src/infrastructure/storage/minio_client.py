from minio import Minio

from src.infrastructure.config.settings import settings


def get_minio_client() -> Minio:

    client = Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False,
    )

    # Create bucket if it doesn't exist
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)

    return client


def get_object_bytes(object_name: str) -> bytes:
    """Descarga el contenido completo de un objeto del bucket."""
    client = get_minio_client()
    response = client.get_object(settings.MINIO_BUCKET, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
