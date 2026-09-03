from datetime import date

import polars as pl
import pytest

from src.domain.pipeline.gold import to_gold
from src.domain.rules.types import CatalogosSnapshot

HOY = date(2026, 9, 1)

CLEAN_FACTURA = {
    "numero_factura": "FAC-0001",
    "fecha": date(2026, 8, 15),
    "sede_codigo": "S1",
    "trabajador_codigo": "E1",
    "comprador_codigo": None,
    "metodo_pago": "TARJETA",
    "iva_pct": 19.0,
    "total_factura": 238.0,  # 200 * 1.19
}

CLEAN_ITEM = {
    "numero_factura": "FAC-0001",
    "item_id": 1,
    "producto_sku": "P1",
    "cantidad": 2,
    "precio_unitario": 100.0,
    "codigo_descuento": None,
    "total_item": 200.0,
}

HEADER_REGLAS = [
    "sede_existe", "sede_activa", "trabajador_existe", "trabajador_activo",
    "trabajador_pertenece_a_sede", "comprador_existe", "fecha_no_futura",
    "fecha_posterior_a_apertura", "factura_total_cuadra",
]
ITEM_REGLAS = [
    "producto_existe", "codigo_descuento_existe", "codigo_descuento_vigente",
    "codigo_descuento_aplica_a_sede", "codigo_descuento_aplica_a_categoria",
    "item_cuadra", "margen_no_negativo", "cantidad_dentro_de_transferencias",
    "item_duplicado_en_factura",
]


def _facturas(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(
        rows,
        schema={
            "numero_factura": pl.Utf8,
            "fecha": pl.Date,
            "sede_codigo": pl.Utf8,
            "trabajador_codigo": pl.Utf8,
            "comprador_codigo": pl.Utf8,
            "metodo_pago": pl.Utf8,
            "iva_pct": pl.Float64,
            "total_factura": pl.Float64,
        },
    )


def _items(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(
        rows,
        schema={
            "numero_factura": pl.Utf8,
            "item_id": pl.Int64,
            "producto_sku": pl.Utf8,
            "cantidad": pl.Int64,
            "precio_unitario": pl.Float64,
            "codigo_descuento": pl.Utf8,
            "total_item": pl.Float64,
        },
    )


def _catalogos(**overrides) -> CatalogosSnapshot:
    defaults = dict(
        sedes=pl.DataFrame({"codigo": ["S1"], "activa": [True], "fecha_apertura": [date(2020, 1, 1)]}),
        trabajadores=pl.DataFrame({"codigo": ["E1"], "sede_codigo": ["S1"], "activo": [True]}),
        productos=pl.DataFrame({"sku": ["P1"], "costo": [50.0], "precio_lista": [100.0], "categoria": ["ROPA"]}),
        codigos_descuento=pl.DataFrame(
            schema={
                "codigo": pl.Utf8, "tipo": pl.Utf8, "valor": pl.Float64,
                "vigencia_inicio": pl.Date, "vigencia_fin": pl.Date,
                "sede_codigo": pl.Utf8, "categorias_aplicables": pl.List(pl.Utf8),
            }
        ),
        transferencias=pl.DataFrame({"producto_sku": ["P1"], "sede_destino_codigo": ["S1"], "cantidad": [100]}),
        compradores=pl.DataFrame({"codigo": ["CLI-001"]}),
    )
    defaults.update(overrides)
    return CatalogosSnapshot(**defaults)


def _codigo(**overrides) -> pl.DataFrame:
    defaults = dict(
        codigo="D1", tipo="PORCENTAJE", valor=10.0,
        vigencia_inicio=date(2020, 1, 1), vigencia_fin=date(2030, 1, 1),
        sede_codigo=None, categorias_aplicables=None,
    )
    defaults.update(overrides)
    return pl.DataFrame(
        [defaults],
        schema={
            "codigo": pl.Utf8, "tipo": pl.Utf8, "valor": pl.Float64,
            "vigencia_inicio": pl.Date, "vigencia_fin": pl.Date,
            "sede_codigo": pl.Utf8, "categorias_aplicables": pl.List(pl.Utf8),
        },
    )


def _gold(facturas=None, items=None, catalogos=None):
    return to_gold(
        _facturas(facturas or [CLEAN_FACTURA]),
        _items(items if items is not None else [CLEAN_ITEM]),
        catalogos or _catalogos(),
        hoy=HOY,
    )


def _paso(gold: pl.DataFrame, regla: str) -> bool:
    """Asume que hay una sola fila para esa regla (un solo item por
    factura en la mayoría de los tests) - los tests con varios items
    filtran gold directamente en vez de usar este helper."""
    return gold.filter(pl.col("regla") == regla)["paso"][0]


def test_clean_factura_passes_every_rule():
    gold = _gold()
    assert gold.height == len(HEADER_REGLAS) + len(ITEM_REGLAS)
    assert gold["paso"].all()


def test_header_rules_have_item_id_null():
    gold = _gold()
    for regla in HEADER_REGLAS:
        assert gold.filter(pl.col("regla") == regla)["item_id"].is_null().all()


def test_item_rules_have_item_id_set():
    gold = _gold()
    for regla in ITEM_REGLAS:
        assert gold.filter(pl.col("regla") == regla)["item_id"].is_not_null().all()


def test_output_scales_with_facturas_and_items():
    facturas = [dict(CLEAN_FACTURA, numero_factura=f"FAC-000{i}") for i in range(1, 4)]
    items = [dict(CLEAN_ITEM, numero_factura=f"FAC-000{i}") for i in range(1, 4)]
    gold = _gold(facturas=facturas, items=items)

    assert gold.height == 3 * (len(HEADER_REGLAS) + len(ITEM_REGLAS))


def test_multi_item_factura_evaluates_each_item():
    items = [
        dict(CLEAN_ITEM, item_id=1, producto_sku="P1", total_item=200.0),
        dict(CLEAN_ITEM, item_id=2, producto_sku="P2", total_item=100.0),
    ]
    catalogos = _catalogos(
        productos=pl.DataFrame(
            {"sku": ["P1", "P2"], "costo": [50.0, 50.0], "precio_lista": [100.0, 100.0], "categoria": ["ROPA", "ROPA"]}
        )
    )
    gold = _gold(items=items, catalogos=catalogos)

    item_rules_rows = gold.filter(pl.col("regla").is_in(ITEM_REGLAS))
    assert item_rules_rows.height == 2 * len(ITEM_REGLAS)


# --- reglas de cabecera ---

def test_sede_inexistente_falla_y_no_penaliza_dos_veces():
    row = dict(CLEAN_FACTURA, sede_codigo="NO-EXISTE")
    gold = _gold(facturas=[row])

    assert not _paso(gold, "sede_existe")
    assert _paso(gold, "sede_activa")  # N/A, pasa vacío


def test_sede_inactiva_falla():
    catalogos = _catalogos(sedes=pl.DataFrame({"codigo": ["S1"], "activa": [False], "fecha_apertura": [date(2020, 1, 1)]}))
    gold = _gold(catalogos=catalogos)

    assert _paso(gold, "sede_existe")
    assert not _paso(gold, "sede_activa")


def test_trabajador_de_otra_sede_falla():
    row = dict(CLEAN_FACTURA, sede_codigo="S2")
    catalogos = _catalogos(
        sedes=pl.DataFrame({"codigo": ["S1", "S2"], "activa": [True, True], "fecha_apertura": [date(2020, 1, 1)] * 2})
    )
    gold = _gold(facturas=[row], catalogos=catalogos)

    assert not _paso(gold, "trabajador_pertenece_a_sede")


def test_sin_comprador_pasa_vacio():
    assert _paso(_gold(), "comprador_existe")


def test_comprador_inexistente_falla():
    row = dict(CLEAN_FACTURA, comprador_codigo="CLI-NO-EXISTE")
    gold = _gold(facturas=[row])

    assert not _paso(gold, "comprador_existe")


def test_comprador_existente_pasa():
    row = dict(CLEAN_FACTURA, comprador_codigo="CLI-001")
    assert _paso(_gold(facturas=[row]), "comprador_existe")


def test_fecha_futura_falla():
    row = dict(CLEAN_FACTURA, fecha=date(2026, 12, 25))
    assert not _paso(_gold(facturas=[row]), "fecha_no_futura")


def test_fecha_anterior_a_apertura_falla():
    row = dict(CLEAN_FACTURA, fecha=date(2019, 1, 1))
    assert not _paso(_gold(facturas=[row]), "fecha_posterior_a_apertura")


def test_factura_total_cuadra_con_iva():
    row = dict(CLEAN_FACTURA, total_factura=200 * 1.19)
    assert _paso(_gold(facturas=[row]), "factura_total_cuadra")


def test_factura_total_no_cuadra_falla():
    row = dict(CLEAN_FACTURA, total_factura=999.0)
    assert not _paso(_gold(facturas=[row]), "factura_total_cuadra")


def test_factura_total_cuadra_con_varios_items():
    items = [
        dict(CLEAN_ITEM, item_id=1, producto_sku="P1", total_item=200.0),
        dict(CLEAN_ITEM, item_id=2, producto_sku="P2", total_item=100.0),
    ]
    row = dict(CLEAN_FACTURA, total_factura=(200 + 100) * 1.19)
    catalogos = _catalogos(
        productos=pl.DataFrame(
            {"sku": ["P1", "P2"], "costo": [50.0, 50.0], "precio_lista": [100.0, 50.0], "categoria": ["ROPA", "ROPA"]}
        )
    )
    gold = _gold(facturas=[row], items=items, catalogos=catalogos)

    assert _paso(gold, "factura_total_cuadra")


# --- reglas de ítem ---

def test_producto_inexistente_falla():
    row = dict(CLEAN_ITEM, producto_sku="NO-EXISTE")
    assert not _paso(_gold(items=[row]), "producto_existe")


def test_sin_codigo_descuento_pasa_vacio():
    gold = _gold()
    for regla in ("codigo_descuento_existe", "codigo_descuento_vigente", "codigo_descuento_aplica_a_sede", "codigo_descuento_aplica_a_categoria"):
        assert _paso(gold, regla)


def test_codigo_descuento_inexistente_falla():
    row = dict(CLEAN_ITEM, codigo_descuento="NO-EXISTE")
    assert not _paso(_gold(items=[row]), "codigo_descuento_existe")


def test_codigo_descuento_vencido_falla():
    row = dict(CLEAN_ITEM, codigo_descuento="D1")
    catalogos = _catalogos(codigos_descuento=_codigo(vigencia_inicio=date(2020, 1, 1), vigencia_fin=date(2020, 12, 31)))
    gold = _gold(items=[row], catalogos=catalogos)

    assert not _paso(gold, "codigo_descuento_vigente")


def test_fecha_invalida_con_codigo_real_no_produce_paso_nulo():
    """fecha=None (silver ya la marcó inválida) + un código de descuento
    real: la comparación de vigencia contra una fecha nula da null en
    Polars (ni true ni false) - descuento_vigente debe pasar vacío, no
    quedar en null."""
    factura = dict(CLEAN_FACTURA, fecha=None)
    item = dict(CLEAN_ITEM, codigo_descuento="D1")
    catalogos = _catalogos(codigos_descuento=_codigo())
    gold = _gold(facturas=[factura], items=[item], catalogos=catalogos)

    assert _paso(gold, "codigo_descuento_vigente") is True


def test_codigo_descuento_de_otra_sede_falla():
    row = dict(CLEAN_ITEM, codigo_descuento="D1")
    catalogos = _catalogos(codigos_descuento=_codigo(sede_codigo="S2"))
    gold = _gold(items=[row], catalogos=catalogos)

    assert not _paso(gold, "codigo_descuento_aplica_a_sede")


def test_codigo_descuento_fuera_de_categoria_falla():
    row = dict(CLEAN_ITEM, codigo_descuento="D1")  # producto es categoría ROPA
    catalogos = _catalogos(codigos_descuento=_codigo(categorias_aplicables=["ELECTRONICA"]))
    gold = _gold(items=[row], catalogos=catalogos)

    assert not _paso(gold, "codigo_descuento_aplica_a_categoria")


def test_codigo_descuento_dentro_de_categoria_pasa():
    row = dict(CLEAN_ITEM, codigo_descuento="D1")
    catalogos = _catalogos(codigos_descuento=_codigo(categorias_aplicables=["ROPA", "DEPORTES"]))
    gold = _gold(items=[row], catalogos=catalogos)

    assert _paso(gold, "codigo_descuento_aplica_a_categoria")


def test_item_no_cuadra_falla():
    row = dict(CLEAN_ITEM, total_item=999.0)
    assert not _paso(_gold(items=[row]), "item_cuadra")


def test_item_con_descuento_porcentaje_cuadra():
    item = dict(CLEAN_ITEM, codigo_descuento="D1", total_item=180.0)  # 200 - 10%
    catalogos = _catalogos(codigos_descuento=_codigo())
    gold = _gold(items=[item], catalogos=catalogos)

    assert _paso(gold, "item_cuadra")


def test_margen_negativo_falla():
    row = dict(CLEAN_ITEM, precio_unitario=10.0, total_item=20.0)  # costo del producto es 50
    assert not _paso(_gold(items=[row]), "margen_no_negativo")


def test_cantidad_excede_transferencias_falla():
    row = dict(CLEAN_ITEM, cantidad=999)
    assert not _paso(_gold(items=[row]), "cantidad_dentro_de_transferencias")


def test_item_duplicado_en_factura_falla_en_ambas_filas():
    items = [dict(CLEAN_ITEM, item_id=1), dict(CLEAN_ITEM, item_id=2)]  # mismo producto_sku
    gold = _gold(items=items)

    resultado = gold.filter(pl.col("regla") == "item_duplicado_en_factura")
    assert resultado.height == 2
    assert not resultado["paso"].any()


def test_item_no_duplicado_entre_facturas_distintas():
    """El mismo producto en 2 facturas DISTINTAS no es un duplicado -
    item_duplicado_en_factura es dentro de la misma factura."""
    facturas = [dict(CLEAN_FACTURA, numero_factura="FAC-0001"), dict(CLEAN_FACTURA, numero_factura="FAC-0002")]
    items = [
        dict(CLEAN_ITEM, numero_factura="FAC-0001"),
        dict(CLEAN_ITEM, numero_factura="FAC-0002"),
    ]
    gold = _gold(facturas=facturas, items=items)

    assert gold.filter(pl.col("regla") == "item_duplicado_en_factura")["paso"].all()


def test_silver_invalida_no_rompe_gold():
    """Una factura/ítem que silver ya marcó como inválida (numérico nulo)
    no debe hacer que gold explote - las reglas que dependen de esos
    campos pasan de forma vacía en vez de fallar con un error de tipos."""
    factura = dict(CLEAN_FACTURA, total_factura=None, iva_pct=None)
    item = dict(CLEAN_ITEM, cantidad=None, precio_unitario=None, total_item=None)
    gold = _gold(facturas=[factura], items=[item])

    assert gold.height == len(HEADER_REGLAS) + len(ITEM_REGLAS)
    assert _paso(gold, "factura_total_cuadra")
    assert _paso(gold, "item_cuadra")
    assert _paso(gold, "margen_no_negativo")
    assert _paso(gold, "cantidad_dentro_de_transferencias")


@pytest.mark.parametrize("regla", HEADER_REGLAS + ITEM_REGLAS)
def test_todas_las_reglas_existen_en_una_factura_limpia(regla):
    gold = _gold()
    esperado = 1
    assert gold.filter(pl.col("regla") == regla).height == esperado
