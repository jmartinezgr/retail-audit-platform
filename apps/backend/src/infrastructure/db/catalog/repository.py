"""
Repositorio de catálogos maestros - solo acceso a datos
"""

from sqlalchemy.orm import Session

from src.infrastructure.db.catalog.models import (
    SedeModel,
    TrabajadorModel,
    ProductoModel,
    CodigoDescuentoModel,
    TransferenciaModel,
)


class CatalogRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_sedes(self) -> list[SedeModel]:
        return self.db.query(SedeModel).all()

    def list_trabajadores(self) -> list[TrabajadorModel]:
        return self.db.query(TrabajadorModel).all()

    def list_productos(self) -> list[ProductoModel]:
        return self.db.query(ProductoModel).all()

    def list_codigos_descuento(self) -> list[CodigoDescuentoModel]:
        return self.db.query(CodigoDescuentoModel).all()

    def list_transferencias(self) -> list[TransferenciaModel]:
        return self.db.query(TransferenciaModel).all()
