"""
Servicio de Uploads - Simple y directo
Maneja la lógica de negocio
"""

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from src.infrastructure.db.uploads.repository import UploadRepository
from src.domain.pipeline.bronze import HOJA_FACTURAS, HOJA_ITEMS, read_columns
from src.domain.uploads import UploadStatus
from src.domain.ventas import validar_columnas_factura, validar_columnas_item
from src.infrastructure.config.settings import settings
from src.infrastructure.storage.s3_client import get_s3_client, get_object_bytes


class UploadService:
    """Lógica de uploads - simple y directa"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = UploadRepository(db)
        self.s3 = get_s3_client()

    def request_upload_url(self, filename: str, session_id: str) -> dict[str, str]:
        """Generar URL presignada para upload"""
        upload_id = str(uuid.uuid4())
        object_name = f"jobs/{upload_id}/upload/{filename}"

        # Genera URL presignada
        upload_url = self.s3.presigned_put_object(
            bucket_name=settings.S3_BUCKET,
            object_name=object_name,
            expires=timedelta(minutes=30),
        )

        # Guarda en BD
        self.repo.save(upload_id, filename, object_name, session_id, UploadStatus.REQUESTED)

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

    def validate_columns(self, upload_id: str) -> dict:
        """Chequeo rápido de columnas de las 2 hojas (facturas + items) -
        NO corre bronze/silver/gold ni toca el status del job."""
        upload = self.repo.get(upload_id)
        if not upload:
            raise ValueError(f"Upload {upload_id} no encontrado")

        file_bytes = get_object_bytes(upload.object_name)
        hojas = read_columns(file_bytes)
        r_facturas = validar_columnas_factura(hojas.get(HOJA_FACTURAS, []))
        r_items = validar_columnas_item(hojas.get(HOJA_ITEMS, []))

        return {
            "upload_id": upload_id,
            "facturas": {
                "columnas_encontradas": r_facturas.columnas_encontradas,
                "columnas_faltantes": r_facturas.columnas_faltantes,
                "columnas_opcionales_presentes": r_facturas.columnas_opcionales_presentes,
                "columnas_extra": r_facturas.columnas_extra,
                "valido": r_facturas.valido,
            },
            "items": {
                "columnas_encontradas": r_items.columnas_encontradas,
                "columnas_faltantes": r_items.columnas_faltantes,
                "columnas_opcionales_presentes": r_items.columnas_opcionales_presentes,
                "columnas_extra": r_items.columnas_extra,
                "valido": r_items.valido,
            },
            "valido": r_facturas.valido and r_items.valido,
        }

    def list_recent(self, session_id: str, limit: int = 20) -> list[dict]:
        """Listar uploads recientes de la sesión"""
        uploads = self.repo.list_recent(session_id, limit)
        return [
            {
                "upload_id": u.id,
                "filename": u.filename,
                "status": u.status,
                "created_at": u.created_at.isoformat(),
            }
            for u in uploads
        ]
