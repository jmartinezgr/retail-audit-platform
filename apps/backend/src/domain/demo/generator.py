"""
Generador de excels de ventas sintéticos para demo - genera FACTURAS
(cabecera + 1-5 ítems cada una) contra catálogos reales
(`CatalogosSnapshot`), con una probabilidad `error_rate` de inyectar UNA
violación por factura (a nivel de cabecera O de un ítem elegido al azar
dentro de ella, nunca ambos).

Los nombres de tipo de violación están alineados 1:1 con los nombres de
regla de silver/gold (`domain/pipeline/silver.py`, `domain/rules/engine.py`)
a propósito - para poder comparar "lo que se inyectó" contra "lo que gold
detectó" después de subir el excel generado. Ver docs/DATA_MODEL.md.

Pensado para generar miles de facturas: los catálogos se convierten a
listas de Python UNA sola vez (`_Prepared`) en vez de re-filtrar con
Polars en cada factura.

Nota honesta: el conteo es una aproximación por lo bajo, no un conteo
exacto garantizado. Algunas mutaciones causan cascadas lógicas reales en
otras reglas (ej. poner una sede inexistente también hace que
`trabajador_pertenece_a_sede` falle; mutar el total de un ítem también
hace que `factura_total_cuadra` dejé de cuadrar en la cabecera) - eso es
correcto, no un bug del generador.
"""

import random
from datetime import date, timedelta

import polars as pl

from src.domain.rules.types import CatalogosSnapshot
from src.domain.ventas import MetodoPago

IVA_PCT = 19


def _fmt(v) -> str:
    return "" if v is None else str(v)


class _Prepared:
    """Catálogos convertidos a listas/dicts de Python una sola vez, para
    no repetir filtros de Polars en cada factura del loop."""

    def __init__(self, catalogos: CatalogosSnapshot, hoy: date):
        self.hoy = hoy
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
        self.compradores = catalogos.compradores.to_dicts()

        self.codigos_descuento = catalogos.codigos_descuento.to_dicts()
        self.codigos_vencidos = [c for c in self.codigos_descuento if c["vigencia_fin"] < hoy]
        self.codigos_con_sede_vigentes_hoy = [
            c
            for c in self.codigos_descuento
            if c["sede_codigo"] is not None and c["vigencia_inicio"] <= hoy <= c["vigencia_fin"]
        ]
        self.codigos_con_categorias_vigentes_hoy = [
            c
            for c in self.codigos_descuento
            if c["categorias_aplicables"] and c["vigencia_inicio"] <= hoy <= c["vigencia_fin"]
        ]


def _descuento_valor(codigo: dict | None, cantidad: float, precio_unitario: float) -> float:
    if not codigo:
        return 0.0
    if codigo["tipo"] == "PORCENTAJE":
        return cantidad * precio_unitario * codigo["valor"] / 100
    return codigo["valor"]


def _recompute_total_item(item: dict, codigo: dict | None) -> float:
    cantidad = float(item["cantidad"])
    precio = float(item["precio_unitario"])
    return cantidad * precio - _descuento_valor(codigo, cantidad, precio)


def _clean_item(numero_factura: str, prep: _Prepared, rng: random.Random, sede: dict, fecha: date, producto: dict) -> dict:
    cantidad = rng.randint(1, 8)
    precio_unitario = producto["precio_lista"]

    # vigente en la FECHA DE LA VENTA, para esa sede, y aplicable a la
    # categoría del producto - si no, una fila "limpia" puede quedar con
    # un descuento que en realidad no le correspondía
    codigos_vigentes = [
        c
        for c in prep.codigos_descuento
        if c["vigencia_inicio"] <= fecha <= c["vigencia_fin"]
        and (c["sede_codigo"] is None or c["sede_codigo"] == sede["codigo"])
        and (not c["categorias_aplicables"] or producto["categoria"] in c["categorias_aplicables"])
    ]
    codigo = rng.choice(codigos_vigentes) if codigos_vigentes and rng.random() < 0.4 else None

    total = cantidad * precio_unitario - _descuento_valor(codigo, cantidad, precio_unitario)

    return {
        "numero_factura": numero_factura,
        "producto_sku": producto["sku"],
        "cantidad": _fmt(cantidad),
        "precio_unitario": _fmt(precio_unitario),
        "codigo_descuento": codigo["codigo"] if codigo else "",
        "total_item": _fmt(total),
        "_total_f": total,
    }


def _clean_factura(numero: int, prep: _Prepared, rng: random.Random, hoy: date) -> tuple[dict, list[dict]]:
    sede = rng.choice(prep.sedes_activas)

    trabajadores_de_sede = prep.trabajadores_por_sede_activos.get(sede["codigo"])
    trabajador = rng.choice(trabajadores_de_sede) if trabajadores_de_sede else rng.choice(prep.trabajadores_todos)

    min_fecha = max(sede["fecha_apertura"], hoy - timedelta(days=90))
    rango_dias = max((hoy - min_fecha).days, 0)
    fecha = min_fecha + timedelta(days=rng.randint(0, rango_dias))

    # no toda venta trae comprador identificado - ventas de mostrador
    # anónimas son normales en retail
    comprador = rng.choice(prep.compradores) if prep.compradores and rng.random() < 0.6 else None

    numero_factura = f"FAC-{numero:07d}"
    # productos DISTINTOS por factura - si se eligieran con reemplazo, una
    # factura "limpia" podría repetir el mismo producto por pura
    # coincidencia y disparar item_duplicado_en_factura sin que se haya
    # inyectado ese error (mismo tipo de falso positivo que ya se corrigió
    # antes en este proyecto con cantidad_dentro_de_transferencias)
    n_items = min(rng.randint(1, 5), len(prep.productos))
    productos_elegidos = rng.sample(prep.productos, k=n_items)
    items = [_clean_item(numero_factura, prep, rng, sede, fecha, producto) for producto in productos_elegidos]

    suma_items = sum(it["_total_f"] for it in items)
    total_factura = round(suma_items * (1 + IVA_PCT / 100), 2)

    header = {
        "numero_factura": numero_factura,
        "fecha": fecha.isoformat(),
        "sede_codigo": sede["codigo"],
        "trabajador_codigo": trabajador["codigo"],
        "comprador_codigo": comprador["codigo"] if comprador else "",
        "metodo_pago": rng.choice(list(MetodoPago)).value,
        "iva_pct": _fmt(IVA_PCT),
        "total_factura": _fmt(total_factura),
    }
    items_out = [{k: v for k, v in it.items() if k != "_total_f"} for it in items]
    return header, items_out


# --- mutadores de CABECERA: reciben el dict de la factura y devuelven una
# copia mutada, o None si el catálogo no tiene datos para inyectarla (ej.
# no hay sedes inactivas) - en ese caso se prueba con otro mutador.

def _mut_numero_factura_vacio(header, prep, rng):
    header = dict(header)
    header["numero_factura"] = ""
    return header


def _mut_fecha_invalida(header, prep, rng):
    header = dict(header)
    header["fecha"] = "2026-13-45"
    return header


def _mut_iva_pct_invalido(header, prep, rng):
    header = dict(header)
    header["iva_pct"] = rng.choice(["-5", "150", "no-es-un-numero"])
    return header


def _mut_total_factura_invalido(header, prep, rng):
    header = dict(header)
    header["total_factura"] = "-100"
    return header


def _mut_metodo_pago_no_reconocido(header, prep, rng):
    header = dict(header)
    header["metodo_pago"] = "BITCOIN"
    return header


def _mut_sede_existe(header, prep, rng):
    header = dict(header)
    header["sede_codigo"] = "TDA-999"
    return header


def _mut_sede_activa(header, prep, rng):
    if not prep.sedes_inactivas:
        return None
    header = dict(header)
    header["sede_codigo"] = rng.choice(prep.sedes_inactivas)["codigo"]
    return header


def _mut_trabajador_existe(header, prep, rng):
    header = dict(header)
    header["trabajador_codigo"] = "EMP-9999"
    return header


def _mut_trabajador_activo(header, prep, rng):
    if not prep.trabajadores_inactivos:
        return None
    header = dict(header)
    header["trabajador_codigo"] = rng.choice(prep.trabajadores_inactivos)["codigo"]
    return header


def _mut_trabajador_pertenece_a_sede(header, prep, rng):
    otras = [s for s in prep.sedes_todas if s["codigo"] != header["sede_codigo"]]
    if not otras:
        return None
    header = dict(header)
    header["sede_codigo"] = rng.choice(otras)["codigo"]
    return header


def _mut_comprador_existe(header, prep, rng):
    header = dict(header)
    header["comprador_codigo"] = "CLI-NOEXISTE"
    return header


def _mut_fecha_no_futura(header, prep, rng):
    header = dict(header)
    header["fecha"] = (prep.hoy + timedelta(days=rng.randint(5, 60))).isoformat()
    return header


def _mut_fecha_posterior_a_apertura(header, prep, rng):
    sede = prep.sedes_por_codigo[header["sede_codigo"]]
    header = dict(header)
    header["fecha"] = (sede["fecha_apertura"] - timedelta(days=rng.randint(5, 60))).isoformat()
    return header


def _mut_factura_total_cuadra(header, prep, rng):
    header = dict(header)
    header["total_factura"] = _fmt(float(header["total_factura"]) + 99999)
    return header


# --- mutadores de ÍTEM: reciben la lista de ítems de la factura y
# devuelven una copia con UN ítem (elegido al azar, o agregado - caso de
# item_duplicado_en_factura) mutado, o None si no aplica.

def _mut_cantidad_invalida(items, prep, rng, header):
    idx = rng.randrange(len(items))
    item = dict(items[idx])
    item["cantidad"] = rng.choice(["-3", "2.5", "0"])
    items = list(items)
    items[idx] = item
    return items


def _mut_precio_unitario_invalido(items, prep, rng, header):
    idx = rng.randrange(len(items))
    item = dict(items[idx])
    item["precio_unitario"] = "no-es-un-numero"
    items = list(items)
    items[idx] = item
    return items


def _mut_total_item_invalido(items, prep, rng, header):
    idx = rng.randrange(len(items))
    item = dict(items[idx])
    item["total_item"] = "-100"
    items = list(items)
    items[idx] = item
    return items


def _mut_producto_existe(items, prep, rng, header):
    idx = rng.randrange(len(items))
    item = dict(items[idx])
    item["producto_sku"] = "NOEX-9999"
    items = list(items)
    items[idx] = item
    return items


def _mut_codigo_descuento_existe(items, prep, rng, header):
    idx = rng.randrange(len(items))
    item = dict(items[idx])
    item["codigo_descuento"] = "NOEXISTE2099"
    # sin código real, el motor asume descuento 0 - recalculamos para que
    # item_cuadra no falle también por un total que quedó desactualizado
    item["total_item"] = _fmt(float(item["cantidad"]) * float(item["precio_unitario"]))
    items = list(items)
    items[idx] = item
    return items


def _mut_codigo_descuento_vigente(items, prep, rng, header):
    if not prep.codigos_vencidos:
        return None
    idx = rng.randrange(len(items))
    item = dict(items[idx])
    codigo = rng.choice(prep.codigos_vencidos)
    item["codigo_descuento"] = codigo["codigo"]
    item["total_item"] = _fmt(_recompute_total_item(item, codigo))
    items = list(items)
    items[idx] = item
    return items


def _mut_codigo_descuento_aplica_a_sede(items, prep, rng, header):
    de_otra_sede = [c for c in prep.codigos_con_sede_vigentes_hoy if c["sede_codigo"] != header["sede_codigo"]]
    if not de_otra_sede:
        return None
    idx = rng.randrange(len(items))
    item = dict(items[idx])
    codigo = rng.choice(de_otra_sede)
    item["codigo_descuento"] = codigo["codigo"]
    item["total_item"] = _fmt(_recompute_total_item(item, codigo))
    items = list(items)
    items[idx] = item
    return items


def _mut_codigo_descuento_aplica_a_categoria(items, prep, rng, header):
    candidatos = [
        c
        for c in prep.codigos_con_categorias_vigentes_hoy
        if c["sede_codigo"] is None or c["sede_codigo"] == header["sede_codigo"]
    ]
    if not candidatos:
        return None
    codigo = rng.choice(candidatos)
    fuera_de_categoria = [p for p in prep.productos if p["categoria"] not in codigo["categorias_aplicables"]]
    if not fuera_de_categoria:
        return None
    producto = rng.choice(fuera_de_categoria)
    idx = rng.randrange(len(items))
    item = dict(items[idx])
    item["producto_sku"] = producto["sku"]
    item["precio_unitario"] = _fmt(producto["precio_lista"])
    item["codigo_descuento"] = codigo["codigo"]
    item["total_item"] = _fmt(_recompute_total_item(item, codigo))
    items = list(items)
    items[idx] = item
    return items


def _mut_item_cuadra(items, prep, rng, header):
    idx = rng.randrange(len(items))
    item = dict(items[idx])
    item["total_item"] = _fmt(float(item["total_item"]) + 99999)
    items = list(items)
    items[idx] = item
    return items


def _mut_margen_no_negativo(items, prep, rng, header):
    idx = rng.randrange(len(items))
    item = dict(items[idx])
    precio_bajo = 1.0
    cantidad = float(item["cantidad"])
    item["precio_unitario"] = _fmt(precio_bajo)
    item["codigo_descuento"] = ""
    item["total_item"] = _fmt(cantidad * precio_bajo)
    items = list(items)
    items[idx] = item
    return items


def _mut_item_duplicado_en_factura(items, prep, rng, header):
    items = list(items)
    items.append(dict(rng.choice(items)))
    return items


def _mut_cantidad_dentro_de_transferencias(items, prep, rng, header):
    idx = rng.randrange(len(items))
    item = dict(items[idx])
    item["cantidad"] = _fmt(999999)
    item["codigo_descuento"] = ""
    item["total_item"] = _fmt(999999 * float(item["precio_unitario"]))
    items = list(items)
    items[idx] = item
    return items


MUTADORES_CABECERA: list[tuple[str, object]] = [
    ("numero_factura_vacio", _mut_numero_factura_vacio),
    ("fecha_invalida", _mut_fecha_invalida),
    ("iva_pct_invalido", _mut_iva_pct_invalido),
    ("total_factura_invalido", _mut_total_factura_invalido),
    ("metodo_pago_no_reconocido", _mut_metodo_pago_no_reconocido),
    ("sede_existe", _mut_sede_existe),
    ("sede_activa", _mut_sede_activa),
    ("trabajador_existe", _mut_trabajador_existe),
    ("trabajador_activo", _mut_trabajador_activo),
    ("trabajador_pertenece_a_sede", _mut_trabajador_pertenece_a_sede),
    ("comprador_existe", _mut_comprador_existe),
    ("fecha_no_futura", _mut_fecha_no_futura),
    ("fecha_posterior_a_apertura", _mut_fecha_posterior_a_apertura),
    ("factura_total_cuadra", _mut_factura_total_cuadra),
]

MUTADORES_ITEM: list[tuple[str, object]] = [
    ("cantidad_invalida", _mut_cantidad_invalida),
    ("precio_unitario_invalido", _mut_precio_unitario_invalido),
    ("total_item_invalido", _mut_total_item_invalido),
    ("producto_existe", _mut_producto_existe),
    ("codigo_descuento_existe", _mut_codigo_descuento_existe),
    ("codigo_descuento_vigente", _mut_codigo_descuento_vigente),
    ("codigo_descuento_aplica_a_sede", _mut_codigo_descuento_aplica_a_sede),
    ("codigo_descuento_aplica_a_categoria", _mut_codigo_descuento_aplica_a_categoria),
    ("item_cuadra", _mut_item_cuadra),
    ("margen_no_negativo", _mut_margen_no_negativo),
    ("item_duplicado_en_factura", _mut_item_duplicado_en_factura),
    ("cantidad_dentro_de_transferencias", _mut_cantidad_dentro_de_transferencias),
]


def generar_ventas(
    catalogos: CatalogosSnapshot,
    facturas: int = 50,
    error_rate: float = 0.1,
    seed: int | None = None,
    hoy: date | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """Genera `facturas` facturas (cada una con 1-5 ítems) contra
    `catalogos`. Cada factura tiene probabilidad `error_rate` de recibir
    UNA violación inyectada, a nivel de cabecera o de un ítem elegido al
    azar. `seed` y `hoy` son opcionales - sin ellos, cada llamada genera
    datos distintos contra la fecha real (igual que `to_gold`, `hoy` es
    inyectable para que los tests no dependan del reloj del sistema).
    Devuelve (facturas_df, items_df, conteo_por_tipo)."""
    rng = random.Random(seed)
    hoy = hoy or date.today()
    prep = _Prepared(catalogos, hoy)
    conteo: dict[str, int] = {}
    facturas_out: list[dict] = []
    items_out: list[dict] = []

    candidatos_base = [(n, m, "cabecera") for n, m in MUTADORES_CABECERA] + [
        (n, m, "item") for n, m in MUTADORES_ITEM
    ]

    for i in range(1, facturas + 1):
        header, factura_items = _clean_factura(i, prep, rng, hoy)

        if rng.random() < error_rate:
            candidatos = list(candidatos_base)
            rng.shuffle(candidatos)
            for tipo, mutador, ambito in candidatos:
                if ambito == "cabecera":
                    mutado = mutador(header, prep, rng)
                    if mutado is not None:
                        header = mutado
                        conteo[tipo] = conteo.get(tipo, 0) + 1
                        break
                else:
                    mutado = mutador(factura_items, prep, rng, header)
                    if mutado is not None:
                        factura_items = mutado
                        conteo[tipo] = conteo.get(tipo, 0) + 1
                        break

        facturas_out.append(header)
        items_out.extend(factura_items)

    return pl.DataFrame(facturas_out), pl.DataFrame(items_out), conteo
