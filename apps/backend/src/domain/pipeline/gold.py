"""
Capa gold: corre el motor de reglas (domain/rules) sobre silver + un
snapshot de los catálogos maestros. Ver docs/DATA_MODEL.md para el
esquema de salida.
"""

from datetime import date

import polars as pl

from src.domain.rules.engine import evaluar
from src.domain.rules.types import CatalogosSnapshot


def to_gold(silver: pl.DataFrame, catalogos: CatalogosSnapshot, hoy: date | None = None) -> pl.DataFrame:
    return evaluar(silver, catalogos, hoy)
