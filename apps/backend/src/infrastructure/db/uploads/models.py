from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base
from src.domain.uploads import UploadStatus


class UploadModel(Base):
    """Modelo de Base de Datos para Uploads"""

    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(primary_key=True)
    filename: Mapped[str]
    object_name: Mapped[str]
    status: Mapped[str] = mapped_column(default=UploadStatus.REQUESTED.value)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
