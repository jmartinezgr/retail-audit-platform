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
    # ID anónimo por navegador (localStorage, sin login) - para que la
    # lista de uploads de la demo pública no se mezcle entre visitantes.
    # No es control de acceso: quien tenga el upload_id igual puede
    # consultarlo directo por los otros endpoints.
    session_id: Mapped[str] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(default=UploadStatus.REQUESTED.value)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
