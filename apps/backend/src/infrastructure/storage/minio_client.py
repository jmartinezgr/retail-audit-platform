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
