"""
Tipos del motor de reglas - sin SQLAlchemy ni nada de infraestructura.
Quien construye un CatalogosSnapshot desde Postgres vive en
infrastructure/db/catalog/snapshot.py, no aquí.
"""

from dataclasses import dataclass
from enum import Enum

import polars as pl


class Severidad(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass
class CatalogosSnapshot:
    """Los catálogos maestros como DataFrames de Polars - lo que necesita
    el motor de reglas para evaluar una factura."""

    sedes: pl.DataFrame
    trabajadores: pl.DataFrame
    productos: pl.DataFrame
    codigos_descuento: pl.DataFrame
    transferencias: pl.DataFrame
    compradores: pl.DataFrame
