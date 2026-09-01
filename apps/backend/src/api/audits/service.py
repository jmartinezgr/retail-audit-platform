"""
Servicio de auditoría - orquesta el pipeline (domain) sobre un upload
confirmado, usando los adaptadores de infraestructura.
"""

from sqlalchemy.orm import Session

from src.domain.pipeline.bronze import to_bronze
from src.domain.pipeline.silver import to_silver
from src.domain.uploads import UploadStatus
from src.infrastructure.db.uploads.repository import UploadRepository
from src.infrastructure.storage import lake
from src.infrastructure.storage.minio_client import get_object_bytes


def _bronze_key(upload_id: str) -> str:
    return f"jobs/{upload_id}/bronze"


def _silver_key(upload_id: str) -> str:
    return f"jobs/{upload_id}/silver"


class AuditService:
    def __init__(self, db: Session):
        self.db = db
        self.uploads = UploadRepository(db)

    def run_pipeline(self, upload_id: str) -> None:
        """Corre bronze -> silver sobre el upload. No marca el upload como
        COMPLETED - eso queda reservado para cuando gold exista."""
        upload = self.uploads.get(upload_id)
        if not upload:
            raise ValueError(f"Upload {upload_id} no encontrado")

        self.uploads.update_status(upload_id, UploadStatus.PROCESSING)
        try:
            file_bytes = get_object_bytes(upload.object_name)

            bronze_df = to_bronze(file_bytes)
            lake.write_delta(bronze_df, _bronze_key(upload_id))

            silver_df = to_silver(bronze_df)
            lake.write_delta(silver_df, _silver_key(upload_id))
        except Exception:
            self.uploads.update_status(upload_id, UploadStatus.FAILED)
            raise

    def get_bronze_preview(self, upload_id: str, limit: int = 20) -> dict:
        return self._preview(_bronze_key(upload_id), upload_id, limit)

    def get_silver_preview(self, upload_id: str, limit: int = 20) -> dict:
        return self._preview(_silver_key(upload_id), upload_id, limit)

    def _preview(self, object_key: str, upload_id: str, limit: int) -> dict:
        df = lake.read_delta(object_key)
        return {
            "upload_id": upload_id,
            "row_count": df.height,
            "columns": df.columns,
            "preview": df.head(limit).to_dicts(),
        }
