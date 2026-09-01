"""
Convierte los catálogos de Postgres a un CatalogosSnapshot de Polars - lo
que consume el motor de reglas (domain/rules), que no sabe nada de
SQLAlchemy. Se lee en vivo cada vez que se llama - así una corrida de
gold siempre ve el estado ACTUAL de los catálogos, aunque hayan cambiado
después de que se generó silver.
"""

import polars as pl
from sqlalchemy.orm import Session

from src.domain.rules.types import CatalogosSnapshot
from src.infrastructure.db.catalog.repository import CatalogRepository


def load_catalog_snapshot(db: Session) -> CatalogosSnapshot:
    repo = CatalogRepository(db)

    sedes = pl.DataFrame(
        [
            {"codigo": s.codigo, "activa": s.activa, "fecha_apertura": s.fecha_apertura}
            for s in repo.list_sedes()
        ]
    )
    trabajadores = pl.DataFrame(
        [
            {"codigo": t.codigo, "sede_codigo": t.sede_codigo, "activo": t.activo}
            for t in repo.list_trabajadores()
        ]
    )
    productos = pl.DataFrame(
        [
            {"sku": p.sku, "costo": p.costo, "precio_lista": p.precio_lista}
            for p in repo.list_productos()
        ]
    )
    codigos_descuento = pl.DataFrame(
        [
            {
                "codigo": c.codigo,
                "tipo": c.tipo,
                "valor": c.valor,
                "vigencia_inicio": c.vigencia_inicio,
                "vigencia_fin": c.vigencia_fin,
                "sede_codigo": c.sede_codigo,
            }
            for c in repo.list_codigos_descuento()
        ]
    )
    transferencias = pl.DataFrame(
        [
            {
                "producto_sku": t.producto_sku,
                "sede_destino_codigo": t.sede_destino_codigo,
                "cantidad": t.cantidad,
            }
            for t in repo.list_transferencias()
        ]
    )

    return CatalogosSnapshot(
        sedes=sedes,
        trabajadores=trabajadores,
        productos=productos,
        codigos_descuento=codigos_descuento,
        transferencias=transferencias,
    )
