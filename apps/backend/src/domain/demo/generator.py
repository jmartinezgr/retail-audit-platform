"""
Generador de excels de ventas sintéticos para demo - filas basadas en
catálogos reales (`CatalogosSnapshot`), con una probabilidad `error_rate`
de inyectar UNA violación por fila.

Los nombres de tipo de violación están alineados 1:1 con los nombres de
regla de silver/gold (`domain/pipeline/silver.py`, `domain/rules/engine.py`)
a propósito - para poder comparar "lo que se inyectó" contra "lo que gold
detectó" después de subir el excel generado. Ver docs/DATA_MODEL.md.

Nota honesta: el conteo es una aproximación por lo bajo, no un conteo
exacto garantizado. Algunas mutaciones causan cascadas lógicas reales en
otras reglas (ej. poner una sede inexistente también hace que
`trabajador_pertenece_a_sede` falle, porque el trabajador de verdad no
pertenece a una sede que no existe) - eso es correcto, no un bug del
generador.
"""

import random
from datetime import date, timedelta

import polars as pl

from src.domain.rules.types import CatalogosSnapshot
from src.domain.ventas import MetodoPago


def _fmt(v) -> str:
    return "" if v is None else str(v)


def _clean_row(i: int, catalogos: CatalogosSnapshot, rng: random.Random) -> dict:
    sedes_activas = catalogos.sedes.filter(pl.col("activa")).to_dicts()
    sede = rng.choice(sedes_activas)

    trabajadores_de_sede = (
        catalogos.trabajadores.filter(
            (pl.col("sede_codigo") == sede["codigo"]) & pl.col("activo")
        ).to_dicts()
    )
    trabajador = (
        rng.choice(trabajadores_de_sede)
        if trabajadores_de_sede
        else rng.choice(catalogos.trabajadores.to_dicts())
    )

    producto = rng.choice(catalogos.productos.to_dicts())

    cantidad = rng.randint(1, 8)
    precio_unitario = producto["precio_lista"]

    hoy = date.today()
    min_fecha = max(sede["fecha_apertura"], hoy - timedelta(days=90))
    rango_dias = max((hoy - min_fecha).days, 0)
    fecha = min_fecha + timedelta(days=rng.randint(0, rango_dias))

    # vigente en la FECHA DE LA VENTA, no en la fecha de hoy - si no, una
    # fila "limpia" puede quedar con un descuento que ya no aplicaba ese día
    codigos_vigentes = catalogos.codigos_descuento.filter(
        (pl.col("vigencia_inicio") <= fecha)
        & (pl.col("vigencia_fin") >= fecha)
        & (pl.col("sede_codigo").is_null() | (pl.col("sede_codigo") == sede["codigo"]))
    ).to_dicts()
    codigo = rng.choice(codigos_vigentes) if codigos_vigentes and rng.random() < 0.4 else None

    total = cantidad * precio_unitario - _descuento_valor(codigo, cantidad, precio_unitario)

    return {
        "numero_factura": f"FAC-{i:05d}",
        "fecha": fecha.isoformat(),
        "sede_codigo": sede["codigo"],
        "trabajador_codigo": trabajador["codigo"],
        "producto_sku": producto["sku"],
        "cantidad": _fmt(cantidad),
        "precio_unitario": _fmt(precio_unitario),
        "codigo_descuento": codigo["codigo"] if codigo else "",
        "total": _fmt(total),
        "metodo_pago": rng.choice(list(MetodoPago)).value,
    }


def _descuento_valor(codigo: dict | None, cantidad: float, precio_unitario: float) -> float:
    if not codigo:
        return 0.0
    if codigo["tipo"] == "PORCENTAJE":
        return cantidad * precio_unitario * codigo["valor"] / 100
    return codigo["valor"]


# --- mutadores: cada uno recibe la fila limpia y devuelve una copia con UNA
# violación inyectada, o None si el catálogo no tiene datos para inyectarla
# (ej. no hay sedes inactivas) - en ese caso se prueba con otro mutador.

def _mut_numero_factura_vacio(row, catalogos, rng, previas):
    row = dict(row)
    row["numero_factura"] = ""
    return row


def _mut_fecha_invalida(row, catalogos, rng, previas):
    row = dict(row)
    row["fecha"] = "2026-13-45"
    return row


def _mut_cantidad_invalida(row, catalogos, rng, previas):
    row = dict(row)
    row["cantidad"] = rng.choice(["-3", "2.5", "0"])
    return row


def _mut_precio_unitario_invalido(row, catalogos, rng, previas):
    row = dict(row)
    row["precio_unitario"] = "no-es-un-numero"
    return row


def _mut_total_invalido(row, catalogos, rng, previas):
    row = dict(row)
    row["total"] = "-100"
    return row


def _mut_metodo_pago_no_reconocido(row, catalogos, rng, previas):
    row = dict(row)
    row["metodo_pago"] = "BITCOIN"
    return row


def _mut_sede_existe(row, catalogos, rng, previas):
    row = dict(row)
    row["sede_codigo"] = "TDA-999"
    return row


def _mut_sede_activa(row, catalogos, rng, previas):
    inactivas = catalogos.sedes.filter(~pl.col("activa")).to_dicts()
    if not inactivas:
        return None
    row = dict(row)
    row["sede_codigo"] = rng.choice(inactivas)["codigo"]
    return row


def _mut_trabajador_existe(row, catalogos, rng, previas):
    row = dict(row)
    row["trabajador_codigo"] = "EMP-9999"
    return row


def _mut_trabajador_activo(row, catalogos, rng, previas):
    inactivos = catalogos.trabajadores.filter(~pl.col("activo")).to_dicts()
    if not inactivos:
        return None
    row = dict(row)
    row["trabajador_codigo"] = rng.choice(inactivos)["codigo"]
    return row


def _mut_trabajador_pertenece_a_sede(row, catalogos, rng, previas):
    otras = catalogos.sedes.filter(pl.col("codigo") != row["sede_codigo"]).to_dicts()
    if not otras:
        return None
    row = dict(row)
    row["sede_codigo"] = rng.choice(otras)["codigo"]
    return row


def _mut_producto_existe(row, catalogos, rng, previas):
    row = dict(row)
    row["producto_sku"] = "NOEX-9999"
    return row


def _mut_codigo_descuento_existe(row, catalogos, rng, previas):
    row = dict(row)
    row["codigo_descuento"] = "NOEXISTE2099"
    # sin código real, el motor asume descuento 0 - recalculamos para que
    # factura_cuadra no falle también por un total que quedó desactualizado
    row["total"] = _fmt(float(row["cantidad"]) * float(row["precio_unitario"]))
    return row


def _mut_codigo_descuento_vigente(row, catalogos, rng, previas):
    hoy = date.today()
    vencidos = catalogos.codigos_descuento.filter(pl.col("vigencia_fin") < hoy).to_dicts()
    if not vencidos:
        return None
    row = dict(row)
    codigo = rng.choice(vencidos)
    row["codigo_descuento"] = codigo["codigo"]
    row["total"] = _fmt(_recompute_total(row, codigo))
    return row


def _mut_codigo_descuento_aplica_a_sede(row, catalogos, rng, previas):
    hoy = date.today()
    de_otra_sede = catalogos.codigos_descuento.filter(
        pl.col("sede_codigo").is_not_null()
        & (pl.col("sede_codigo") != row["sede_codigo"])
        & (pl.col("vigencia_inicio") <= hoy)
        & (pl.col("vigencia_fin") >= hoy)
    ).to_dicts()
    if not de_otra_sede:
        return None
    row = dict(row)
    codigo = rng.choice(de_otra_sede)
    row["codigo_descuento"] = codigo["codigo"]
    row["total"] = _fmt(_recompute_total(row, codigo))
    return row


def _recompute_total(row: dict, codigo: dict) -> float:
    cantidad = float(row["cantidad"])
    precio = float(row["precio_unitario"])
    return cantidad * precio - _descuento_valor(codigo, cantidad, precio)


def _mut_factura_cuadra(row, catalogos, rng, previas):
    row = dict(row)
    row["total"] = _fmt(float(row["total"]) + 99999)
    return row


def _mut_margen_no_negativo(row, catalogos, rng, previas):
    row = dict(row)
    precio_bajo = 1.0
    cantidad = float(row["cantidad"])
    row["precio_unitario"] = _fmt(precio_bajo)
    row["codigo_descuento"] = ""
    row["total"] = _fmt(cantidad * precio_bajo)
    return row


def _mut_fecha_no_futura(row, catalogos, rng, previas):
    row = dict(row)
    row["fecha"] = (date.today() + timedelta(days=rng.randint(5, 60))).isoformat()
    return row


def _mut_fecha_posterior_a_apertura(row, catalogos, rng, previas):
    sede = catalogos.sedes.filter(pl.col("codigo") == row["sede_codigo"]).to_dicts()[0]
    row = dict(row)
    row["fecha"] = (sede["fecha_apertura"] - timedelta(days=rng.randint(5, 60))).isoformat()
    return row


def _mut_factura_no_duplicada(row, catalogos, rng, previas):
    if not previas:
        return None
    row = dict(row)
    row["numero_factura"] = rng.choice(previas)
    return row


def _mut_cantidad_dentro_de_transferencias(row, catalogos, rng, previas):
    row = dict(row)
    row["cantidad"] = _fmt(999999)
    row["codigo_descuento"] = ""
    row["total"] = _fmt(999999 * float(row["precio_unitario"]))
    return row


MUTADORES: list[tuple[str, object]] = [
    ("numero_factura_vacio", _mut_numero_factura_vacio),
    ("fecha_invalida", _mut_fecha_invalida),
    ("cantidad_invalida", _mut_cantidad_invalida),
    ("precio_unitario_invalido", _mut_precio_unitario_invalido),
    ("total_invalido", _mut_total_invalido),
    ("metodo_pago_no_reconocido", _mut_metodo_pago_no_reconocido),
    ("sede_existe", _mut_sede_existe),
    ("sede_activa", _mut_sede_activa),
    ("trabajador_existe", _mut_trabajador_existe),
    ("trabajador_activo", _mut_trabajador_activo),
    ("trabajador_pertenece_a_sede", _mut_trabajador_pertenece_a_sede),
    ("producto_existe", _mut_producto_existe),
    ("codigo_descuento_existe", _mut_codigo_descuento_existe),
    ("codigo_descuento_vigente", _mut_codigo_descuento_vigente),
    ("codigo_descuento_aplica_a_sede", _mut_codigo_descuento_aplica_a_sede),
    ("factura_cuadra", _mut_factura_cuadra),
    ("margen_no_negativo", _mut_margen_no_negativo),
    ("fecha_no_futura", _mut_fecha_no_futura),
    ("fecha_posterior_a_apertura", _mut_fecha_posterior_a_apertura),
    ("factura_no_duplicada", _mut_factura_no_duplicada),
    ("cantidad_dentro_de_transferencias", _mut_cantidad_dentro_de_transferencias),
]


def generar_ventas(
    catalogos: CatalogosSnapshot,
    filas: int = 50,
    error_rate: float = 0.1,
    seed: int | None = None,
) -> tuple[pl.DataFrame, dict[str, int]]:
    """Genera `filas` ventas contra `catalogos`. Cada fila tiene
    probabilidad `error_rate` de recibir UNA violación inyectada. `seed`
    es opcional - sin él, cada llamada genera datos distintos."""
    rng = random.Random(seed)
    conteo: dict[str, int] = {}
    previas: list[str] = []
    generadas: list[dict] = []

    for i in range(1, filas + 1):
        row = _clean_row(i, catalogos, rng)

        if rng.random() < error_rate:
            candidatos = list(MUTADORES)
            rng.shuffle(candidatos)
            for tipo, mutador in candidatos:
                mutado = mutador(row, catalogos, rng, previas)
                if mutado is not None:
                    row = mutado
                    conteo[tipo] = conteo.get(tipo, 0) + 1
                    break

        previas.append(row["numero_factura"])
        generadas.append(row)

    return pl.DataFrame(generadas), conteo
