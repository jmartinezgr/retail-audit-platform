"""
Lectura/escritura de tablas Delta Lake contra el storage S3-compatible
(MinIO local / R2 en prod) - vía Polars + deltalake (delta-rs), sin Spark.
"""

import polars as pl

from src.infrastructure.config.settings import settings


def _storage_options() -> dict[str, str]:
    scheme = "https" if settings.MINIO_SECURE else "http"
    return {
        "AWS_ENDPOINT_URL": f"{scheme}://{settings.MINIO_ENDPOINT}",
        "AWS_ACCESS_KEY_ID": settings.MINIO_ACCESS_KEY,
        "AWS_SECRET_ACCESS_KEY": settings.MINIO_SECRET_KEY,
        "AWS_REGION": settings.MINIO_REGION,
        "AWS_ALLOW_HTTP": "false" if settings.MINIO_SECURE else "true",
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }


def _delta_uri(object_key: str) -> str:
    return f"s3://{settings.MINIO_BUCKET}/{object_key}"


def write_delta(df: pl.DataFrame, object_key: str) -> None:
    """Escribe (sobrescribe) una tabla Delta en la ruta dada del bucket."""
    df.write_delta(
        _delta_uri(object_key),
        mode="overwrite",
        storage_options=_storage_options(),
    )


def read_delta(object_key: str) -> pl.DataFrame:
    """Lee una tabla Delta existente en la ruta dada del bucket."""
    return pl.read_delta(_delta_uri(object_key), storage_options=_storage_options())
