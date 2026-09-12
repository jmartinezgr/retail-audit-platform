"""
Tipos del motor de reglas - sin SQLAlchemy ni nada de infraestructura.
Quien construye un CatalogosSnapshot desde Postgres vive en
infrastructure/db/catalog/snapshot.py, y quien construye ReglaDinamica
desde Postgres vive en infrastructure/db/rules/snapshot.py - ninguno de
los dos aquí.
"""

from dataclasses import dataclass
from datetime import date
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


class TipoReglaDinamica(str, Enum):
    UMBRAL = "UMBRAL"
    VENTANA_EXCLUSION = "VENTANA_EXCLUSION"


class AmbitoRegla(str, Enum):
    CABECERA = "CABECERA"
    ITEM = "ITEM"


class Operador(str, Enum):
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="
    NEQ = "!="


@dataclass
class ReglaDinamica:
    """Una regla configurable desde el frontend, sin tocar código. Los
    campos específicos de un tipo quedan en None en el otro:
    UMBRAL usa campo/operador/valor(/filtro_categoria/filtro_sede),
    VENTANA_EXCLUSION usa sede_codigo/fecha_inicio/fecha_fin (siempre
    ámbito CABECERA). Ver domain/rules/dynamic.py para el evaluador."""

    id: int
    nombre: str
    tipo: TipoReglaDinamica
    ambito: AmbitoRegla
    severidad: Severidad
    activa: bool
    mensaje: str
    campo: str | None = None
    operador: Operador | None = None
    valor: float | None = None
    filtro_categoria: str | None = None
    filtro_sede: str | None = None
    sede_codigo: str | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None


def construir_resultado(
    df: pl.DataFrame,
    regla: str,
    severidad: Severidad,
    paso: pl.Expr,
    mensaje_falla: str,
    mensaje_pasa: str = "OK",
    item_id: pl.Expr | None = None,
) -> pl.DataFrame:
    """Construye filas del esquema de gold (numero_factura, item_id,
    sede_codigo, fecha, regla, severidad, paso, mensaje) - lo comparten
    el motor estático (engine.py) y el dinámico (dynamic.py) para que
    ambos produzcan exactamente la misma forma de fila."""
    return df.select(
        pl.col("numero_factura"),
        (item_id if item_id is not None else pl.lit(None, dtype=pl.Int64)).alias("item_id"),
        pl.col("sede_codigo"),
        pl.col("fecha"),
        pl.lit(regla).alias("regla"),
        pl.lit(severidad.value).alias("severidad"),
        paso.alias("paso"),
        pl.when(paso).then(pl.lit(mensaje_pasa)).otherwise(pl.lit(mensaje_falla)).alias("mensaje"),
    )
