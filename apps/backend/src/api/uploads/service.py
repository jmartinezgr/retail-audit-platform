"""
Servicio de Uploads - Simple y directo
Maneja la lógica de negocio
"""

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from src.infrastructure.db.uploads.repository import UploadRepository
from src.domain.uploads import UploadStatus
from src.infrastructure.config.settings import settings
from src.infrastructure.storage.minio_client import get_minio_client


class UploadService:
    """Lógica de uploads - simple y directa"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = UploadRepository(db)
        self.minio = get_minio_client()

    def request_upload_url(self, filename: str) -> dict[str, str]:
        """Generar URL presignada para upload"""
        upload_id = str(uuid.uuid4())
        object_name = f"jobs/{upload_id}/bronze/{filename}"

        # Genera URL presignada
        upload_url = self.minio.presigned_put_object(
            bucket_name=settings.MINIO_BUCKET,
            object_name=object_name,
            expires=timedelta(minutes=30),
        )

        # Guarda en BD
        self.repo.save(upload_id, filename, object_name, UploadStatus.REQUESTED)

        return {
            "upload_url": upload_url,
            "object_name": object_name,
            "upload_id": upload_id,
        }

    def confirm_upload(self, upload_id: str) -> dict:
        """Confirmar que upload terminó"""
        upload = self.repo.update_status(upload_id, UploadStatus.UPLOADED)
        if not upload:
            raise ValueError(f"Upload {upload_id} no encontrado")
        return {"upload_id": upload_id, "status": upload.status}

    def get_upload_status(self, upload_id: str) -> dict:
        """Obtener estado de un upload"""
        upload = self.repo.get(upload_id)
        if not upload:
            raise ValueError(f"Upload {upload_id} no encontrado")
        return {
            "upload_id": upload.id,
            "filename": upload.filename,
            "status": upload.status,
            "created_at": upload.created_at.isoformat(),
        }

    def list_recent(self, limit: int = 20) -> list[dict]:
        """Listar uploads recientes"""
        uploads = self.repo.list_recent(limit)
        return [
            {
                "upload_id": u.id,
                "filename": u.filename,
                "status": u.status,
                "created_at": u.created_at.isoformat(),
            }
            for u in uploads
        ]
