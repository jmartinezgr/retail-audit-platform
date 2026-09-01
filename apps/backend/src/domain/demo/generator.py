"""
Generador de excels de ventas sintéticos para demo - filas basadas en
catálogos reales (`CatalogosSnapshot`), con una probabilidad `error_rate`
de inyectar UNA violación por fila.

Los nombres de tipo de violación están alineados 1:1 con los nombres de
regla de silver/gold (`domain/pipeline/silver.py`, `domain/rules/engine.py`)
a propósito - para poder comparar "lo que se inyectó" contra "lo que gold
detectó" después de subir el excel generado. Ver docs/DATA_MODEL.md.

Pensado para generar miles de filas: los catálogos se convierten a listas
de Python UNA sola vez (`_Prepared`) en vez de re-filtrar con Polars en
cada fila - una llamada de `pl.DataFrame.filter()` por fila es barata en
sí misma, pero miles de ellas en un loop de Python sí se notan.

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


class _Prepared:
    """Catálogos convertidos a listas/dicts de Python una sola vez, para
    no repetir filtros de Polars en cada fila del loop."""

    def __init__(self, catalogos: CatalogosSnapshot):
        self.sedes_todas = catalogos.sedes.to_dicts()
        self.sedes_por_codigo = {s["codigo"]: s for s in self.sedes_todas}
        self.sedes_activas = [s for s in self.sedes_todas if s["activa"]]
        self.sedes_inactivas = [s for s in self.sedes_todas if not s["activa"]]

        trabajadores_todos = catalogos.trabajadores.to_dicts()
        self.trabajadores_todos = trabajadores_todos
        self.trabajadores_inactivos = [t for t in trabajadores_todos if not t["activo"]]
        self.trabajadores_por_sede_activos: dict[str, list[dict]] = {}
        for t in trabajadores_todos:
            if t["activo"]:
                self.trabajadores_por_sede_activos.setdefault(t["sede_codigo"], []).append(t)

        self.productos = catalogos.productos.to_dicts()

        self.codigos_descuento = catalogos.codigos_descuento.to_dicts()
        hoy = date.today()
        self.codigos_vencidos = [c for c in self.codigos_descuento if c["vigencia_fin"] < hoy]
        self.codigos_con_sede_vigentes_hoy = [
            c
            for c in self.codigos_descuento
            if c["sede_codigo"] is not None and c["vigencia_inicio"] <= hoy <= c["vigencia_fin"]
        ]


def _clean_row(i: int, prep: _Prepared, rng: random.Random) -> dict:
    sede = rng.choice(prep.sedes_activas)

    trabajadores_de_sede = prep.trabajadores_por_sede_activos.get(sede["codigo"])
    trabajador = rng.choice(trabajadores_de_sede) if trabajadores_de_sede else rng.choice(prep.trabajadores_todos)

    producto = rng.choice(prep.productos)

    cantidad = rng.randint(1, 8)
    precio_unitario = producto["precio_lista"]

    hoy = date.today()
    min_fecha = max(sede["fecha_apertura"], hoy - timedelta(days=90))
    rango_dias = max((hoy - min_fecha).days, 0)
    fecha = min_fecha + timedelta(days=rng.randint(0, rango_dias))

    # vigente en la FECHA DE LA VENTA, no en la fecha de hoy - si no, una
    # fila "limpia" puede quedar con un descuento que ya no aplicaba ese día
    codigos_vigentes = [
        c
        for c in prep.codigos_descuento
        if c["vigencia_inicio"] <= fecha <= c["vigencia_fin"]
        and (c["sede_codigo"] is None or c["sede_codigo"] == sede["codigo"])
    ]
    codigo = rng.choice(codigos_vigentes) if codigos_vigentes and rng.random() < 0.4 else None

    total = cantidad * precio_unitario - _descuento_valor(codigo, cantidad, precio_unitario)

    return {
        "numero_factura": f"FAC-{i:07d}",
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

def _mut_numero_factura_vacio(row, prep, rng, previas):
    row = dict(row)
    row["numero_factura"] = ""
    return row


def _mut_fecha_invalida(row, prep, rng, previas):
    row = dict(row)
    row["fecha"] = "2026-13-45"
    return row


def _mut_cantidad_invalida(row, prep, rng, previas):
    row = dict(row)
    row["cantidad"] = rng.choice(["-3", "2.5", "0"])
    return row


def _mut_precio_unitario_invalido(row, prep, rng, previas):
    row = dict(row)
    row["precio_unitario"] = "no-es-un-numero"
    return row


def _mut_total_invalido(row, prep, rng, previas):
    row = dict(row)
    row["total"] = "-100"
    return row


def _mut_metodo_pago_no_reconocido(row, prep, rng, previas):
    row = dict(row)
    row["metodo_pago"] = "BITCOIN"
    return row


def _mut_sede_existe(row, prep, rng, previas):
    row = dict(row)
    row["sede_codigo"] = "TDA-999"
    return row


def _mut_sede_activa(row, prep, rng, previas):
    if not prep.sedes_inactivas:
        return None
    row = dict(row)
    row["sede_codigo"] = rng.choice(prep.sedes_inactivas)["codigo"]
    return row


def _mut_trabajador_existe(row, prep, rng, previas):
    row = dict(row)
    row["trabajador_codigo"] = "EMP-9999"
    return row


def _mut_trabajador_activo(row, prep, rng, previas):
    if not prep.trabajadores_inactivos:
        return None
    row = dict(row)
    row["trabajador_codigo"] = rng.choice(prep.trabajadores_inactivos)["codigo"]
    return row


def _mut_trabajador_pertenece_a_sede(row, prep, rng, previas):
    otras = [s for s in prep.sedes_todas if s["codigo"] != row["sede_codigo"]]
    if not otras:
        return None
    row = dict(row)
    row["sede_codigo"] = rng.choice(otras)["codigo"]
    return row


def _mut_producto_existe(row, prep, rng, previas):
    row = dict(row)
    row["producto_sku"] = "NOEX-9999"
    return row


def _mut_codigo_descuento_existe(row, prep, rng, previas):
    row = dict(row)
    row["codigo_descuento"] = "NOEXISTE2099"
    # sin código real, el motor asume descuento 0 - recalculamos para que
    # factura_cuadra no falle también por un total que quedó desactualizado
    row["total"] = _fmt(float(row["cantidad"]) * float(row["precio_unitario"]))
    return row


def _mut_codigo_descuento_vigente(row, prep, rng, previas):
    if not prep.codigos_vencidos:
        return None
    row = dict(row)
    codigo = rng.choice(prep.codigos_vencidos)
    row["codigo_descuento"] = codigo["codigo"]
    row["total"] = _fmt(_recompute_total(row, codigo))
    return row


def _mut_codigo_descuento_aplica_a_sede(row, prep, rng, previas):
    de_otra_sede = [c for c in prep.codigos_con_sede_vigentes_hoy if c["sede_codigo"] != row["sede_codigo"]]
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


def _mut_factura_cuadra(row, prep, rng, previas):
    row = dict(row)
    row["total"] = _fmt(float(row["total"]) + 99999)
    return row


def _mut_margen_no_negativo(row, prep, rng, previas):
    row = dict(row)
    precio_bajo = 1.0
    cantidad = float(row["cantidad"])
    row["precio_unitario"] = _fmt(precio_bajo)
    row["codigo_descuento"] = ""
    row["total"] = _fmt(cantidad * precio_bajo)
    return row


def _mut_fecha_no_futura(row, prep, rng, previas):
    row = dict(row)
    row["fecha"] = (date.today() + timedelta(days=rng.randint(5, 60))).isoformat()
    return row


def _mut_fecha_posterior_a_apertura(row, prep, rng, previas):
    sede = prep.sedes_por_codigo[row["sede_codigo"]]
    row = dict(row)
    row["fecha"] = (sede["fecha_apertura"] - timedelta(days=rng.randint(5, 60))).isoformat()
    return row


def _mut_factura_no_duplicada(row, prep, rng, previas):
    if not previas:
        return None
    row = dict(row)
    row["numero_factura"] = rng.choice(previas)
    return row


def _mut_cantidad_dentro_de_transferencias(row, prep, rng, previas):
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
    prep = _Prepared(catalogos)
    conteo: dict[str, int] = {}
    previas: list[str] = []
    generadas: list[dict] = []

    for i in range(1, filas + 1):
        row = _clean_row(i, prep, rng)

        if rng.random() < error_rate:
            candidatos = list(MUTADORES)
            rng.shuffle(candidatos)
            for tipo, mutador in candidatos:
                mutado = mutador(row, prep, rng, previas)
                if mutado is not None:
                    row = mutado
                    conteo[tipo] = conteo.get(tipo, 0) + 1
                    break

        previas.append(row["numero_factura"])
        generadas.append(row)

    return pl.DataFrame(generadas), conteo
