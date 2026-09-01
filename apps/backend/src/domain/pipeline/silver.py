"""
Capa silver: tipa y valida ESTRUCTURALMENTE las filas de bronze contra el
esquema esperado de Venta (domain/ventas.py) - columnas presentes, tipos,
formatos, campos obligatorios no vacíos. No valida reglas de negocio
(existencia en catálogos, vigencias, márgenes) - eso es gold.

Ninguna fila se descarta: las inválidas quedan marcadas en `_errores`
(lista de mensajes) y `_es_valida` (bool), no se filtran.
"""

import polars as pl

from src.domain.ventas import (
    MetodoPago,
    VENTA_COLUMNAS_OPCIONALES,
    VENTA_COLUMNAS_REQUERIDAS,
)

_METODOS_PAGO_VALIDOS = [m.value for m in MetodoPago]


class SilverSchemaError(Exception):
    """El archivo no tiene ni las columnas mínimas esperadas - error de
    estructura del archivo completo, no de una fila puntual."""


def _is_blank(col: str) -> pl.Expr:
    return pl.col(col).is_null() | (pl.col(col).str.strip_chars() == "")


def to_silver(bronze_df: pl.DataFrame) -> pl.DataFrame:
    missing = [c for c in VENTA_COLUMNAS_REQUERIDAS if c not in bronze_df.columns]
    if missing:
        raise SilverSchemaError(f"Faltan columnas obligatorias: {', '.join(missing)}")

    df = bronze_df.select(
        VENTA_COLUMNAS_REQUERIDAS
        + [c for c in VENTA_COLUMNAS_OPCIONALES if c in bronze_df.columns]
    )
    for c in VENTA_COLUMNAS_OPCIONALES:
        if c not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=pl.Utf8).alias(c))

    cantidad_f = pl.col("cantidad").cast(pl.Float64, strict=False)
    precio_f = pl.col("precio_unitario").cast(pl.Float64, strict=False)
    total_f = pl.col("total").cast(pl.Float64, strict=False)
    fecha_d = pl.col("fecha").str.strptime(pl.Date, "%Y-%m-%d", strict=False)

    cantidad_valida = (
        cantidad_f.is_not_null() & (cantidad_f > 0) & (cantidad_f == cantidad_f.floor())
    )
    precio_valido = precio_f.is_not_null() & (precio_f > 0)
    total_valido = total_f.is_not_null() & (total_f > 0)
    fecha_valida = fecha_d.is_not_null()
    metodo_valido = pl.col("metodo_pago").is_in(_METODOS_PAGO_VALIDOS)

    df = df.with_columns(
        cantidad_f.alias("_cantidad_f"),
        precio_f.alias("_precio_f"),
        total_f.alias("_total_f"),
        fecha_d.alias("_fecha_d"),
        cantidad_valida.alias("_cantidad_valida"),
        precio_valido.alias("_precio_valida"),
        total_valido.alias("_total_valido"),
        fecha_valida.alias("_fecha_valida"),
        metodo_valido.alias("_metodo_valido"),
    )

    errores = pl.concat_list(
        [
            pl.when(_is_blank("numero_factura"))
            .then(pl.lit("numero_factura vacío"))
            .otherwise(None),
            pl.when(_is_blank("sede_codigo"))
            .then(pl.lit("sede_codigo vacío"))
            .otherwise(None),
            pl.when(_is_blank("trabajador_codigo"))
            .then(pl.lit("trabajador_codigo vacío"))
            .otherwise(None),
            pl.when(_is_blank("producto_sku"))
            .then(pl.lit("producto_sku vacío"))
            .otherwise(None),
            pl.when(~pl.col("_fecha_valida"))
            .then(pl.lit("fecha inválida (esperado YYYY-MM-DD)"))
            .otherwise(None),
            pl.when(~pl.col("_cantidad_valida"))
            .then(pl.lit("cantidad inválida (debe ser entero positivo)"))
            .otherwise(None),
            pl.when(~pl.col("_precio_valida"))
            .then(pl.lit("precio_unitario inválido (debe ser número positivo)"))
            .otherwise(None),
            pl.when(~pl.col("_total_valido"))
            .then(pl.lit("total inválido (debe ser número positivo)"))
            .otherwise(None),
            pl.when(~pl.col("_metodo_valido"))
            .then(pl.lit("metodo_pago no reconocido"))
            .otherwise(None),
        ]
    ).list.drop_nulls()

    df = df.with_columns(
        pl.when(pl.col("_cantidad_valida"))
        .then(pl.col("_cantidad_f").cast(pl.Int64))
        .otherwise(None)
        .alias("cantidad"),
        pl.when(pl.col("_precio_valida"))
        .then(pl.col("_precio_f"))
        .otherwise(None)
        .alias("precio_unitario"),
        pl.when(pl.col("_total_valido"))
        .then(pl.col("_total_f"))
        .otherwise(None)
        .alias("total"),
        pl.when(pl.col("_fecha_valida"))
        .then(pl.col("_fecha_d"))
        .otherwise(None)
        .alias("fecha"),
        errores.alias("_errores"),
    )

    df = df.with_columns((pl.col("_errores").list.len() == 0).alias("_es_valida"))

    return df.drop(
        [
            "_cantidad_f",
            "_precio_f",
            "_total_f",
            "_fecha_d",
            "_cantidad_valida",
            "_precio_valida",
            "_total_valido",
            "_fecha_valida",
            "_metodo_valido",
        ]
    )
