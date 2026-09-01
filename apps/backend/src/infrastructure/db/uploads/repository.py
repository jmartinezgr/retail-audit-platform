"""
Repositorio de Uploads - Simple y directo
Solo acceso a datos
"""

from sqlalchemy.orm import Session
from src.infrastructure.db.uploads.models import UploadModel
from src.domain.uploads import UploadStatus


class UploadRepository:
    """Acceso a datos - métodos CRUD básicos"""

    def __init__(self, db: Session):
        self.db = db

    def save(
        self, upload_id: str, filename: str, status: str = UploadStatus.REQUESTED
    ) -> UploadModel:
        """Guarda un nuevo upload"""
        upload = UploadModel(id=upload_id, filename=filename, status=status)
        self.db.add(upload)
        self.db.commit()
        self.db.refresh(upload)
        return upload

    def get(self, upload_id: str) -> UploadModel | None:
        """Obtiene upload por ID"""
        return self.db.query(UploadModel).filter(UploadModel.id == upload_id).first()

    def update_status(self, upload_id: str, status: str) -> UploadModel | None:
        """Actualiza estado"""
        upload = self.get(upload_id)
        if upload:
            upload.status = status
            self.db.commit()
            self.db.refresh(upload)
        return upload

    def list_by_status(self, status: str, limit: int = 10) -> list[UploadModel]:
        """Lista por estado"""
        return (
            self.db.query(UploadModel)
            .filter(UploadModel.status == status)
            .limit(limit)
            .all()
        )

    def list_recent(self, limit: int = 20) -> list[UploadModel]:
        """Lista recientes"""
        return (
            self.db.query(UploadModel)
            .order_by(UploadModel.created_at.desc())
            .limit(limit)
            .all()
        )
