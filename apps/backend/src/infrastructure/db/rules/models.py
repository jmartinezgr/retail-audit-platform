from datetime import date, datetime

from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base


class RuleDefinitionModel(Base):
    """Una regla dinámica configurable desde el frontend, ver
    domain/rules/dynamic.py para el evaluador y domain/rules/types.py
    para el dataclass de dominio (ReglaDinamica) al que se convierte.
    Tabla nueva, se crea sola en el próximo arranque
    (Base.metadata.create_all en main.py) - no hace falta tocar
    scripts/seed_catalog.py."""

    __tablename__ = "rule_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(unique=True)
    tipo: Mapped[str]  # "UMBRAL" | "VENTANA_EXCLUSION"
    ambito: Mapped[str]  # "CABECERA" | "ITEM"
    severidad: Mapped[str]  # "ERROR" | "WARNING"
    activa: Mapped[bool] = mapped_column(default=True)
    mensaje: Mapped[str]

    # UMBRAL
    campo: Mapped[str | None]
    operador: Mapped[str | None]
    valor: Mapped[float | None]
    filtro_categoria: Mapped[str | None]
    filtro_sede: Mapped[str | None]

    # VENTANA_EXCLUSION
    sede_codigo: Mapped[str | None]
    fecha_inicio: Mapped[date | None]
    fecha_fin: Mapped[date | None]

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
