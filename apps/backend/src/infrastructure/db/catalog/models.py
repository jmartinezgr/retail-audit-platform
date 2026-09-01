from datetime import date

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.db.base import Base


class SedeModel(Base):
    """Sede (tienda física) de la cadena"""

    __tablename__ = "sedes"

    codigo: Mapped[str] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    ciudad: Mapped[str]
    region: Mapped[str]
    fecha_apertura: Mapped[date]
    activa: Mapped[bool] = mapped_column(default=True)


class TrabajadorModel(Base):
    """Empleado asignado a una sede"""

    __tablename__ = "trabajadores"

    codigo: Mapped[str] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    sede_codigo: Mapped[str] = mapped_column(ForeignKey("sedes.codigo"))
    cargo: Mapped[str]
    fecha_ingreso: Mapped[date]
    activo: Mapped[bool] = mapped_column(default=True)

    sede: Mapped["SedeModel"] = relationship()


class ProductoModel(Base):
    """Producto del catálogo, identificado por su SKU interno"""

    __tablename__ = "productos"

    sku: Mapped[str] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    categoria: Mapped[str]
    precio_lista: Mapped[float]
    costo: Mapped[float]


class CodigoDescuentoModel(Base):
    """Código de descuento, vigente en un rango de fechas y opcionalmente
    restringido a una sede (sede_codigo nulo = aplica a todas)"""

    __tablename__ = "codigos_descuento"

    codigo: Mapped[str] = mapped_column(primary_key=True)
    tipo: Mapped[str]
    valor: Mapped[float]
    vigencia_inicio: Mapped[date]
    vigencia_fin: Mapped[date]
    sede_codigo: Mapped[str | None] = mapped_column(ForeignKey("sedes.codigo"))
    uso_maximo: Mapped[int | None]

    sede: Mapped["SedeModel | None"] = relationship()


class TransferenciaModel(Base):
    """Movimiento de inventario de un producto entre dos sedes"""

    __tablename__ = "transferencias"

    id: Mapped[str] = mapped_column(primary_key=True)
    producto_sku: Mapped[str] = mapped_column(ForeignKey("productos.sku"))
    sede_origen_codigo: Mapped[str] = mapped_column(ForeignKey("sedes.codigo"))
    sede_destino_codigo: Mapped[str] = mapped_column(ForeignKey("sedes.codigo"))
    cantidad: Mapped[int]
    fecha: Mapped[date]

    producto: Mapped["ProductoModel"] = relationship()
