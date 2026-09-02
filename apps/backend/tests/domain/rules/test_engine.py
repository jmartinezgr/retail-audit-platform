from datetime import date

import polars as pl
import pytest

from src.domain.pipeline.gold import to_gold
from src.domain.rules.types import CatalogosSnapshot

HOY = date(2026, 9, 1)

CLEAN_SILVER_ROW = {
    "numero_factura": "FAC-0001",
    "fecha": date(2026, 8, 15),
    "sede_codigo": "S1",
    "trabajador_codigo": "E1",
    "producto_sku": "P1",
    "cantidad": 2,
    "precio_unitario": 100.0,
    "total": 200.0,
    "metodo_pago": "TARJETA",
    "codigo_descuento": None,
    "_errores": [],
    "_es_valida": True,
}


def _silver(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(
        rows,
        schema={
            "numero_factura": pl.Utf8,
            "fecha": pl.Date,
            "sede_codigo": pl.Utf8,
            "trabajador_codigo": pl.Utf8,
            "producto_sku": pl.Utf8,
            "cantidad": pl.Int64,
            "precio_unitario": pl.Float64,
            "total": pl.Float64,
            "metodo_pago": pl.Utf8,
            "codigo_descuento": pl.Utf8,
            "_errores": pl.List(pl.Utf8),
            "_es_valida": pl.Boolean,
        },
    )


def _catalogos(**overrides) -> CatalogosSnapshot:
    defaults = dict(
        sedes=pl.DataFrame({"codigo": ["S1"], "activa": [True], "fecha_apertura": [date(2020, 1, 1)]}),
        trabajadores=pl.DataFrame({"codigo": ["E1"], "sede_codigo": ["S1"], "activo": [True]}),
        productos=pl.DataFrame({"sku": ["P1"], "costo": [50.0]}),
        codigos_descuento=pl.DataFrame(
            schema={
                "codigo": pl.Utf8,
                "tipo": pl.Utf8,
                "valor": pl.Float64,
                "vigencia_inicio": pl.Date,
                "vigencia_fin": pl.Date,
                "sede_codigo": pl.Utf8,
            }
        ),
        transferencias=pl.DataFrame({"producto_sku": ["P1"], "sede_destino_codigo": ["S1"], "cantidad": [100]}),
    )
    defaults.update(overrides)
    return CatalogosSnapshot(**defaults)


def _paso(gold: pl.DataFrame, regla: str) -> bool:
    return gold.filter(pl.col("regla") == regla)["paso"][0]


def test_clean_row_passes_every_rule():
    gold = to_gold(_silver([CLEAN_SILVER_ROW]), _catalogos(), hoy=HOY)

    assert gold.height == 15
    assert gold["paso"].all()


def test_output_has_one_row_per_factura_per_rule():
    rows = [dict(CLEAN_SILVER_ROW, numero_factura=f"FAC-000{i}") for i in range(1, 4)]
    gold = to_gold(_silver(rows), _catalogos(), hoy=HOY)

    assert gold.height == 3 * 15


def test_sede_inexistente_falla_y_no_penaliza_dos_veces():
    row = dict(CLEAN_SILVER_ROW, sede_codigo="NO-EXISTE")
    gold = to_gold(_silver([row]), _catalogos(), hoy=HOY)

    assert not _paso(gold, "sede_existe")
    # sede_activa no debe fallar también por el mismo motivo - pasa vacío
    assert _paso(gold, "sede_activa")


def test_sede_inactiva_falla():
    row = dict(CLEAN_SILVER_ROW)
    catalogos = _catalogos(sedes=pl.DataFrame({"codigo": ["S1"], "activa": [False], "fecha_apertura": [date(2020, 1, 1)]}))
    gold = to_gold(_silver([row]), catalogos, hoy=HOY)

    assert _paso(gold, "sede_existe")
    assert not _paso(gold, "sede_activa")


def test_trabajador_de_otra_sede_falla():
    row = dict(CLEAN_SILVER_ROW, sede_codigo="S2")
    catalogos = _catalogos(
        sedes=pl.DataFrame({"codigo": ["S1", "S2"], "activa": [True, True], "fecha_apertura": [date(2020, 1, 1)] * 2})
    )
    gold = to_gold(_silver([row]), catalogos, hoy=HOY)

    assert not _paso(gold, "trabajador_pertenece_a_sede")


def test_producto_inexistente_falla():
    row = dict(CLEAN_SILVER_ROW, producto_sku="NO-EXISTE")
    gold = to_gold(_silver([row]), _catalogos(), hoy=HOY)

    assert not _paso(gold, "producto_existe")


def test_sin_codigo_descuento_pasa_vacio():
    gold = to_gold(_silver([CLEAN_SILVER_ROW]), _catalogos(), hoy=HOY)

    for regla in ("codigo_descuento_existe", "codigo_descuento_vigente", "codigo_descuento_aplica_a_sede"):
        assert _paso(gold, regla)


def test_codigo_descuento_inexistente_falla():
    row = dict(CLEAN_SILVER_ROW, codigo_descuento="NO-EXISTE")
    gold = to_gold(_silver([row]), _catalogos(), hoy=HOY)

    assert not _paso(gold, "codigo_descuento_existe")


def test_codigo_descuento_vencido_falla():
    row = dict(CLEAN_SILVER_ROW, codigo_descuento="D1")
    catalogos = _catalogos(
        codigos_descuento=pl.DataFrame(
            {
                "codigo": ["D1"],
                "tipo": ["PORCENTAJE"],
                "valor": [10.0],
                "vigencia_inicio": [date(2020, 1, 1)],
                "vigencia_fin": [date(2020, 12, 31)],
                "sede_codigo": pl.Series([None], dtype=pl.Utf8),
            }
        )
    )
    gold = to_gold(_silver([row]), catalogos, hoy=HOY)

    assert not _paso(gold, "codigo_descuento_vigente")


def test_fecha_invalida_con_codigo_real_no_produce_paso_nulo():
    """fecha=None (silver ya la marcó inválida) + un código de descuento
    real: la comparación de vigencia contra una fecha nula da null en
    Polars (ni true ni false) - descuento_vigente debe pasar vacío, no
    quedar en null."""
    row = dict(CLEAN_SILVER_ROW, fecha=None, codigo_descuento="D1")
    catalogos = _catalogos(
        codigos_descuento=pl.DataFrame(
            {
                "codigo": ["D1"],
                "tipo": ["PORCENTAJE"],
                "valor": [10.0],
                "vigencia_inicio": [date(2020, 1, 1)],
                "vigencia_fin": [date(2030, 1, 1)],
                "sede_codigo": pl.Series([None], dtype=pl.Utf8),
            }
        )
    )
    gold = to_gold(_silver([row]), catalogos, hoy=HOY)

    assert _paso(gold, "codigo_descuento_vigente") is True


def test_codigo_descuento_de_otra_sede_falla():
    row = dict(CLEAN_SILVER_ROW, codigo_descuento="D1")
    catalogos = _catalogos(
        codigos_descuento=pl.DataFrame(
            {
                "codigo": ["D1"],
                "tipo": ["PORCENTAJE"],
                "valor": [10.0],
                "vigencia_inicio": [date(2020, 1, 1)],
                "vigencia_fin": [date(2030, 1, 1)],
                "sede_codigo": ["S2"],
            }
        )
    )
    gold = to_gold(_silver([row]), catalogos, hoy=HOY)

    assert not _paso(gold, "codigo_descuento_aplica_a_sede")


def test_factura_no_cuadra_falla():
    row = dict(CLEAN_SILVER_ROW, total=999.0)
    gold = to_gold(_silver([row]), _catalogos(), hoy=HOY)

    assert not _paso(gold, "factura_cuadra")


def test_factura_con_descuento_porcentaje_cuadra():
    row = dict(CLEAN_SILVER_ROW, codigo_descuento="D1", total=180.0)  # 200 - 10%
    catalogos = _catalogos(
        codigos_descuento=pl.DataFrame(
            {
                "codigo": ["D1"],
                "tipo": ["PORCENTAJE"],
                "valor": [10.0],
                "vigencia_inicio": [date(2020, 1, 1)],
                "vigencia_fin": [date(2030, 1, 1)],
                "sede_codigo": pl.Series([None], dtype=pl.Utf8),
            }
        )
    )
    gold = to_gold(_silver([row]), catalogos, hoy=HOY)

    assert _paso(gold, "factura_cuadra")


def test_margen_negativo_falla():
    row = dict(CLEAN_SILVER_ROW, precio_unitario=10.0, total=20.0)  # costo del producto es 50
    gold = to_gold(_silver([row]), _catalogos(), hoy=HOY)

    assert not _paso(gold, "margen_no_negativo")


def test_fecha_futura_falla():
    row = dict(CLEAN_SILVER_ROW, fecha=date(2026, 12, 25))
    gold = to_gold(_silver([row]), _catalogos(), hoy=HOY)

    assert not _paso(gold, "fecha_no_futura")


def test_fecha_anterior_a_apertura_falla():
    row = dict(CLEAN_SILVER_ROW, fecha=date(2019, 1, 1))
    gold = to_gold(_silver([row]), _catalogos(), hoy=HOY)

    assert not _paso(gold, "fecha_posterior_a_apertura")


def test_factura_duplicada_falla_en_ambas_filas():
    rows = [dict(CLEAN_SILVER_ROW), dict(CLEAN_SILVER_ROW)]  # mismo numero_factura
    gold = to_gold(_silver(rows), _catalogos(), hoy=HOY)

    resultado = gold.filter(pl.col("regla") == "factura_no_duplicada")
    assert resultado.height == 2
    assert not resultado["paso"].any()


def test_cantidad_excede_transferencias_falla():
    row = dict(CLEAN_SILVER_ROW, cantidad=999)
    gold = to_gold(_silver([row]), _catalogos(), hoy=HOY)

    assert not _paso(gold, "cantidad_dentro_de_transferencias")


def test_silver_invalida_no_rompe_gold():
    """Una fila que silver ya marcó como inválida (numérico nulo) no debe
    hacer que gold explote - las reglas que dependen de esos campos pasan
    de forma vacía en vez de fallar con un error de tipos."""
    row = dict(CLEAN_SILVER_ROW, cantidad=None, precio_unitario=None, total=None)
    gold = to_gold(_silver([row]), _catalogos(), hoy=HOY)

    assert gold.height == 15
    assert _paso(gold, "factura_cuadra")
    assert _paso(gold, "margen_no_negativo")
    assert _paso(gold, "cantidad_dentro_de_transferencias")


@pytest.mark.parametrize("regla", [
    "sede_existe", "sede_activa", "trabajador_existe", "trabajador_activo",
    "trabajador_pertenece_a_sede", "producto_existe", "codigo_descuento_existe",
    "codigo_descuento_vigente", "codigo_descuento_aplica_a_sede", "factura_cuadra",
    "margen_no_negativo", "fecha_no_futura", "fecha_posterior_a_apertura",
    "factura_no_duplicada", "cantidad_dentro_de_transferencias",
])
def test_todas_las_reglas_existen_en_una_fila_limpia(regla):
    gold = to_gold(_silver([CLEAN_SILVER_ROW]), _catalogos(), hoy=HOY)
    assert gold.filter(pl.col("regla") == regla).height == 1
