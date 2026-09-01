from datetime import date

import polars as pl

from src.domain.demo.generator import generar_ventas
from src.domain.pipeline.gold import to_gold
from src.domain.pipeline.silver import to_silver
from src.domain.rules.types import CatalogosSnapshot

HOY = date(2026, 9, 1)


def _catalogos() -> CatalogosSnapshot:
    return CatalogosSnapshot(
        sedes=pl.DataFrame(
            {
                "codigo": ["S1", "S2", "S3"],
                "activa": [True, True, False],
                "fecha_apertura": [date(2020, 1, 1), date(2020, 1, 1), date(2020, 1, 1)],
            }
        ),
        trabajadores=pl.DataFrame(
            {
                "codigo": ["E1", "E2", "E3"],
                "sede_codigo": ["S1", "S2", "S1"],
                "activo": [True, True, False],
            }
        ),
        productos=pl.DataFrame(
            {"sku": ["P1", "P2"], "costo": [50.0, 20.0], "precio_lista": [100.0, 40.0]}
        ),
        codigos_descuento=pl.DataFrame(
            {
                "codigo": ["VIGENTE", "VENCIDO"],
                "tipo": ["PORCENTAJE", "PORCENTAJE"],
                "valor": [10.0, 10.0],
                "vigencia_inicio": [date(2020, 1, 1), date(2020, 1, 1)],
                "vigencia_fin": [date(2030, 1, 1), date(2021, 1, 1)],
                "sede_codigo": pl.Series([None, None], dtype=pl.Utf8),
            }
        ),
        # cobertura completa (toda combinación producto x sede activa),
        # igual que el seed real - si no, cantidad_dentro_de_transferencias
        # falla por falta de datos, no por un error inyectado de verdad
        transferencias=pl.DataFrame(
            {
                "producto_sku": ["P1", "P1", "P2", "P2"],
                "sede_destino_codigo": ["S1", "S2", "S1", "S2"],
                "cantidad": [500, 500, 500, 500],
            }
        ),
    )


def test_error_rate_zero_produces_all_clean_rows():
    catalogos = _catalogos()
    df, conteo = generar_ventas(catalogos, filas=30, error_rate=0.0, seed=1)

    assert conteo == {}
    silver = to_silver(df)
    assert silver["_es_valida"].all()

    gold = to_gold(silver, catalogos, hoy=HOY)
    assert gold["paso"].all()


def test_error_rate_one_injects_something_in_every_row():
    catalogos = _catalogos()
    df, conteo = generar_ventas(catalogos, filas=30, error_rate=1.0, seed=2)

    assert df.height == 30
    assert sum(conteo.values()) == 30


def test_injecting_errors_produces_detectable_problems():
    """No intenta cuadrar el conteo exacto (una sola mutación puede
    cascadear a varias reglas, o colapsar numero_factura entre filas -
    ver numero_factura_vacio) - solo confirma que error_rate alto
    efectivamente produce filas detectables como problemáticas."""
    catalogos = _catalogos()
    df, conteo = generar_ventas(catalogos, filas=100, error_rate=0.4, seed=3)

    silver = to_silver(df)
    gold = to_gold(silver, catalogos, hoy=HOY)

    assert sum(conteo.values()) > 0
    assert not silver["_es_valida"].all() or not gold["paso"].all()


def test_same_seed_is_reproducible():
    catalogos = _catalogos()
    df1, conteo1 = generar_ventas(catalogos, filas=20, error_rate=0.3, seed=42)
    df2, conteo2 = generar_ventas(catalogos, filas=20, error_rate=0.3, seed=42)

    assert df1.equals(df2)
    assert conteo1 == conteo2


def test_numero_factura_unico_sin_inyeccion_de_duplicados():
    catalogos = _catalogos()
    df, conteo = generar_ventas(catalogos, filas=50, error_rate=0.0, seed=5)

    assert df["numero_factura"].n_unique() == 50
