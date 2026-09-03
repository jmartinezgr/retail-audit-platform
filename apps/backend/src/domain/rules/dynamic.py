"""
Motor de reglas DINÁMICAS de gold - reglas configurables desde el
frontend (tabla `rule_definitions` en Postgres, ver
infrastructure/db/rules/), sin tocar código ni redeploy. DSL tabular
propio de dos tipos, no JSONLogic - se traduce 1:1 a expresiones de
Polars, igual que domain/rules/engine.py:

- UMBRAL: compara un campo (de una whitelist fija, CAMPOS_CABECERA /
  CAMPOS_ITEM más abajo) contra un valor con un operador. El
  operador+valor describe la CONDICIÓN DE VIOLACIÓN (ej. "descuento_pct
  > 0.20"), no la de paso - así el formulario del frontend pregunta "¿A
  partir de cuándo es un problema?", no lo inverso.
- VENTANA_EXCLUSION: una sede no debería tener ventas en un rango de
  fechas (ej. "sede en mantenimiento"). Siempre ámbito CABECERA.

Produce filas con el mismo esquema que engine.py (via
types.construir_resultado), así conviven en la misma tabla de gold sin
que el resto del backend/frontend necesite saber que existen dos
motores.
"""

from collections.abc import Callable

import polars as pl

from src.domain.rules.types import AmbitoRegla, Operador, ReglaDinamica, TipoReglaDinamica, construir_resultado

# Campos permitidos por ámbito para reglas UMBRAL. `descuento_pct` y
# `margen_pct` son calculados acá mismo (no viven en engine.py - son
# solo para el evaluador dinámico), el resto son columnas que ya trae el
# dataframe enriquecido (engine.enriquecer()).
CAMPOS_CABECERA = {"total_factura", "iva_pct"}
CAMPOS_ITEM = {"cantidad", "precio_unitario", "total_item", "descuento_pct", "margen_pct"}

OPERADORES: dict[Operador, Callable[[pl.Expr, float], pl.Expr]] = {
    Operador.GT: lambda col, v: col > v,
    Operador.GTE: lambda col, v: col >= v,
    Operador.LT: lambda col, v: col < v,
    Operador.LTE: lambda col, v: col <= v,
    Operador.EQ: lambda col, v: col == v,
    Operador.NEQ: lambda col, v: col != v,
}


def _con_campos_calculados(items_enr: pl.DataFrame) -> pl.DataFrame:
    """`descuento_pct`/`margen_pct` son null (→ la regla pasa, N/A) cuando
    el denominador es 0 - mismo patrón que las reglas estáticas usan para
    "el prerequisito no aplica"."""
    subtotal_bruto = pl.col("cantidad") * pl.col("precio_unitario")
    return items_enr.with_columns(
        pl.when(subtotal_bruto > 0)
        .then(1 - pl.col("total_item") / subtotal_bruto)
        .otherwise(None)
        .alias("descuento_pct"),
        pl.when(pl.col("precio_unitario") > 0)
        .then((pl.col("precio_unitario") - pl.col("_producto_costo")) / pl.col("precio_unitario"))
        .otherwise(None)
        .alias("margen_pct"),
    )


def _evaluar_umbral(regla: ReglaDinamica, df: pl.DataFrame) -> pl.DataFrame:
    campo = pl.col(regla.campo)
    aplica = pl.lit(True)
    if regla.filtro_categoria:
        aplica = aplica & (pl.col("_producto_categoria") == regla.filtro_categoria)
    if regla.filtro_sede:
        aplica = aplica & (pl.col("sede_codigo") == regla.filtro_sede)

    violacion = OPERADORES[regla.operador](campo, regla.valor)
    paso = campo.is_null() | ~aplica | ~violacion

    item_id = pl.col("item_id") if regla.ambito == AmbitoRegla.ITEM else None
    return construir_resultado(df, regla.nombre, regla.severidad, paso, regla.mensaje, item_id=item_id)


def _evaluar_ventana(regla: ReglaDinamica, facturas_enr: pl.DataFrame) -> pl.DataFrame:
    violacion = (
        (pl.col("sede_codigo") == regla.sede_codigo)
        & pl.col("fecha").is_not_null()
        & (pl.col("fecha") >= regla.fecha_inicio)
        & (pl.col("fecha") <= regla.fecha_fin)
    )
    return construir_resultado(facturas_enr, regla.nombre, regla.severidad, ~violacion, regla.mensaje)


def evaluar_dinamicas(
    facturas_enr: pl.DataFrame, items_enr: pl.DataFrame, reglas: list[ReglaDinamica]
) -> list[pl.DataFrame]:
    """`reglas` puede traer inactivas (infra siempre carga todas, igual
    que load_catalog_snapshot) - se filtran acá, no en infraestructura."""
    activas = [r for r in reglas if r.activa]
    if not activas:
        return []

    items_calc = _con_campos_calculados(items_enr)

    resultados: list[pl.DataFrame] = []
    for regla in activas:
        if regla.tipo == TipoReglaDinamica.UMBRAL:
            df = facturas_enr if regla.ambito == AmbitoRegla.CABECERA else items_calc
            resultados.append(_evaluar_umbral(regla, df))
        else:
            resultados.append(_evaluar_ventana(regla, facturas_enr))
    return resultados
