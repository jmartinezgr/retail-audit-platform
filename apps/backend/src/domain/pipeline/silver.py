"""
Capa silver: tipa y valida ESTRUCTURALMENTE las filas de bronze contra el
esquema esperado de factura/ítem (domain/ventas.py) - columnas presentes,
tipos, formatos, campos obligatorios no vacíos. No valida reglas de
negocio (existencia en catálogos, vigencias, márgenes) - eso es gold.

Ninguna fila se descarta: las inválidas quedan marcadas en `_errores`
(lista de mensajes) y `_es_valida` (bool), no se filtran. La única
excepción es la validación referencial ítem→factura (el `numero_factura`
de un ítem debe existir en la hoja de facturas): es estructural (no hay
con qué enriquecer el ítem si su factura no existe) pero no se puede
evaluar sin la otra hoja, así que to_silver_items() la recibe como
parámetro en vez de hacerla ella misma "de negocio" en gold.
"""

import polars as pl

from src.domain.ventas import (
    FACTURA_COLUMNAS_OPCIONALES,
    FACTURA_COLUMNAS_REQUERIDAS,
    ITEM_COLUMNAS_OPCIONALES,
    ITEM_COLUMNAS_REQUERIDAS,
    MetodoPago,
)

_METODOS_PAGO_VALIDOS = [m.value for m in MetodoPago]


class SilverSchemaError(Exception):
    """El archivo no tiene ni las columnas mínimas esperadas en alguna de
    las 2 hojas - error de estructura del archivo completo, no de una
    fila puntual."""


def _is_blank(col: str) -> pl.Expr:
    return pl.col(col).is_null() | (pl.col(col).str.strip_chars() == "")


def _select_con_opcionales(df: pl.DataFrame, requeridas: list[str], opcionales: list[str]) -> pl.DataFrame:
    df = df.select(requeridas + [c for c in opcionales if c in df.columns])
    for c in opcionales:
        if c not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=pl.Utf8).alias(c))
    return df


def to_silver_facturas(bronze_facturas: pl.DataFrame) -> pl.DataFrame:
    missing = [c for c in FACTURA_COLUMNAS_REQUERIDAS if c not in bronze_facturas.columns]
    if missing:
        raise SilverSchemaError(f"Faltan columnas obligatorias en la hoja 'facturas': {', '.join(missing)}")

    df = _select_con_opcionales(bronze_facturas, FACTURA_COLUMNAS_REQUERIDAS, FACTURA_COLUMNAS_OPCIONALES)

    fecha_d = pl.col("fecha").str.strptime(pl.Date, "%Y-%m-%d", strict=False)
    iva_f = pl.col("iva_pct").cast(pl.Float64, strict=False)
    total_f = pl.col("total_factura").cast(pl.Float64, strict=False)

    fecha_valida = fecha_d.is_not_null()
    iva_valido = iva_f.is_not_null() & (iva_f >= 0) & (iva_f <= 100)
    total_valido = total_f.is_not_null() & (total_f > 0)
    metodo_valido = pl.col("metodo_pago").is_in(_METODOS_PAGO_VALIDOS)

    df = df.with_columns(
        fecha_d.alias("_fecha_d"),
        iva_f.alias("_iva_f"),
        total_f.alias("_total_f"),
        fecha_valida.alias("_fecha_valida"),
        iva_valido.alias("_iva_valida"),
        total_valido.alias("_total_valido"),
        metodo_valido.alias("_metodo_valido"),
    )

    errores = pl.concat_list(
        [
            pl.when(_is_blank("numero_factura")).then(pl.lit("numero_factura vacío")).otherwise(None),
            pl.when(_is_blank("sede_codigo")).then(pl.lit("sede_codigo vacío")).otherwise(None),
            pl.when(_is_blank("trabajador_codigo")).then(pl.lit("trabajador_codigo vacío")).otherwise(None),
            pl.when(~pl.col("_fecha_valida")).then(pl.lit("fecha inválida (esperado YYYY-MM-DD)")).otherwise(None),
            pl.when(~pl.col("_iva_valida")).then(pl.lit("iva_pct inválido (debe estar entre 0 y 100)")).otherwise(None),
            pl.when(~pl.col("_total_valido")).then(pl.lit("total_factura inválido (debe ser número positivo)")).otherwise(None),
            pl.when(~pl.col("_metodo_valido")).then(pl.lit("metodo_pago no reconocido")).otherwise(None),
        ]
    ).list.drop_nulls()

    df = df.with_columns(
        pl.when(pl.col("_fecha_valida")).then(pl.col("_fecha_d")).otherwise(None).alias("fecha"),
        pl.when(pl.col("_iva_valida")).then(pl.col("_iva_f")).otherwise(None).alias("iva_pct"),
        pl.when(pl.col("_total_valido")).then(pl.col("_total_f")).otherwise(None).alias("total_factura"),
        errores.alias("_errores"),
    )
    df = df.with_columns((pl.col("_errores").list.len() == 0).alias("_es_valida"))

    return df.drop(["_fecha_d", "_iva_f", "_total_f", "_fecha_valida", "_iva_valida", "_total_valido", "_metodo_valido"])


def to_silver_items(bronze_items: pl.DataFrame, numeros_factura_validos: set[str]) -> pl.DataFrame:
    missing = [c for c in ITEM_COLUMNAS_REQUERIDAS if c not in bronze_items.columns]
    if missing:
        raise SilverSchemaError(f"Faltan columnas obligatorias en la hoja 'items': {', '.join(missing)}")

    df = _select_con_opcionales(bronze_items, ITEM_COLUMNAS_REQUERIDAS, ITEM_COLUMNAS_OPCIONALES)

    cantidad_f = pl.col("cantidad").cast(pl.Float64, strict=False)
    precio_f = pl.col("precio_unitario").cast(pl.Float64, strict=False)
    total_f = pl.col("total_item").cast(pl.Float64, strict=False)

    cantidad_valida = cantidad_f.is_not_null() & (cantidad_f > 0) & (cantidad_f == cantidad_f.floor())
    precio_valido = precio_f.is_not_null() & (precio_f > 0)
    total_valido = total_f.is_not_null() & (total_f > 0)
    factura_existe = pl.col("numero_factura").is_in(list(numeros_factura_validos))

    df = df.with_columns(
        cantidad_f.alias("_cantidad_f"),
        precio_f.alias("_precio_f"),
        total_f.alias("_total_f"),
        cantidad_valida.alias("_cantidad_valida"),
        precio_valido.alias("_precio_valida"),
        total_valido.alias("_total_valido"),
        factura_existe.alias("_factura_existe"),
    )

    errores = pl.concat_list(
        [
            pl.when(_is_blank("numero_factura")).then(pl.lit("numero_factura vacío")).otherwise(None),
            pl.when(_is_blank("producto_sku")).then(pl.lit("producto_sku vacío")).otherwise(None),
            pl.when(~pl.col("_cantidad_valida")).then(pl.lit("cantidad inválida (debe ser entero positivo)")).otherwise(None),
            pl.when(~pl.col("_precio_valida")).then(pl.lit("precio_unitario inválido (debe ser número positivo)")).otherwise(None),
            pl.when(~pl.col("_total_valido")).then(pl.lit("total_item inválido (debe ser número positivo)")).otherwise(None),
            pl.when(~_is_blank("numero_factura") & ~pl.col("_factura_existe"))
            .then(pl.lit("numero_factura no existe en la hoja 'facturas'"))
            .otherwise(None),
        ]
    ).list.drop_nulls()

    df = df.with_columns(
        pl.when(pl.col("_cantidad_valida")).then(pl.col("_cantidad_f").cast(pl.Int64)).otherwise(None).alias("cantidad"),
        pl.when(pl.col("_precio_valida")).then(pl.col("_precio_f")).otherwise(None).alias("precio_unitario"),
        pl.when(pl.col("_total_valido")).then(pl.col("_total_f")).otherwise(None).alias("total_item"),
        errores.alias("_errores"),
    )
    df = df.with_columns((pl.col("_errores").list.len() == 0).alias("_es_valida"))
    df = df.with_columns(pl.int_range(1, pl.len() + 1).over("numero_factura").alias("item_id"))

    return df.drop(["_cantidad_f", "_precio_f", "_total_f", "_cantidad_valida", "_precio_valida", "_total_valido", "_factura_existe"])
