from datetime import date

import polars as pl

from src.domain.demo.generator import generar_ventas
from src.domain.pipeline.gold import to_gold
from src.domain.pipeline.silver import to_silver_facturas, to_silver_items
from src.domain.rules.types import CatalogosSnapshot

# Fija - generar_ventas() y to_gold() aceptan `hoy` como parámetro
# inyectable justo para que estos tests no dependan del reloj real (nos
# tocó una vez: un test con HOY fijo del día en que se escribió empezó a
# fallar días después, porque el generador seguía usando date.today()).
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
            {
                "sku": [f"P{i}" for i in range(1, 11)],
                "costo": [50.0] * 10,
                "precio_lista": [100.0] * 10,
                "categoria": (["ROPA", "ELECTRONICA"] * 5),
            }
        ),
        codigos_descuento=pl.DataFrame(
            {
                "codigo": ["VIGENTE", "VENCIDO"],
                "tipo": ["PORCENTAJE", "PORCENTAJE"],
                "valor": [10.0, 10.0],
                "vigencia_inicio": [date(2020, 1, 1), date(2020, 1, 1)],
                "vigencia_fin": [date(2030, 1, 1), date(2021, 1, 1)],
                "sede_codigo": pl.Series([None, None], dtype=pl.Utf8),
                "categorias_aplicables": pl.Series([None, None], dtype=pl.List(pl.Utf8)),
            }
        ),
        # cobertura completa (toda combinación producto x sede activa),
        # igual que el seed real - si no, cantidad_dentro_de_transferencias
        # falla por falta de datos, no por un error inyectado de verdad
        transferencias=pl.DataFrame(
            {
                "producto_sku": [f"P{i}" for i in range(1, 11) for _ in range(2)],
                "sede_destino_codigo": ["S1", "S2"] * 10,
                "cantidad": [500] * 20,
            }
        ),
        compradores=pl.DataFrame({"codigo": ["CLI-001", "CLI-002"]}),
    )


def _run_pipeline(facturas_df, items_df, catalogos):
    bronze_facturas = facturas_df.select(pl.all().cast(pl.Utf8))
    bronze_items = items_df.select(pl.all().cast(pl.Utf8))
    silver_facturas = to_silver_facturas(bronze_facturas)
    numeros_validos = set(silver_facturas["numero_factura"].drop_nulls().to_list())
    silver_items = to_silver_items(bronze_items, numeros_validos)
    gold = to_gold(silver_facturas, silver_items, catalogos, hoy=HOY)
    return silver_facturas, silver_items, gold


def test_error_rate_zero_produces_all_clean_facturas():
    catalogos = _catalogos()
    facturas_df, items_df, conteo = generar_ventas(catalogos, facturas=30, error_rate=0.0, seed=1, hoy=HOY)

    assert conteo == {}
    silver_facturas, silver_items, gold = _run_pipeline(facturas_df, items_df, catalogos)
    assert silver_facturas["_es_valida"].all()
    assert silver_items["_es_valida"].all()
    assert gold["paso"].all()


def test_error_rate_one_injects_something_in_every_factura():
    catalogos = _catalogos()
    facturas_df, items_df, conteo = generar_ventas(catalogos, facturas=30, error_rate=1.0, seed=2, hoy=HOY)

    assert facturas_df.height == 30
    assert sum(conteo.values()) == 30


def test_injecting_errors_produces_detectable_problems():
    """No intenta cuadrar el conteo exacto (una sola mutación puede
    cascadear a varias reglas - ver numero_factura_vacio orfanando sus
    ítems, o un ítem mutado dejando factura_total_cuadra sin cuadrar) -
    solo confirma que error_rate alto efectivamente produce facturas
    detectables como problemáticas."""
    catalogos = _catalogos()
    facturas_df, items_df, conteo = generar_ventas(catalogos, facturas=100, error_rate=0.4, seed=3, hoy=HOY)

    silver_facturas, silver_items, gold = _run_pipeline(facturas_df, items_df, catalogos)

    assert sum(conteo.values()) > 0
    assert not silver_facturas["_es_valida"].all() or not silver_items["_es_valida"].all() or not gold["paso"].all()


def test_same_seed_is_reproducible():
    catalogos = _catalogos()
    f1, i1, conteo1 = generar_ventas(catalogos, facturas=20, error_rate=0.3, seed=42, hoy=HOY)
    f2, i2, conteo2 = generar_ventas(catalogos, facturas=20, error_rate=0.3, seed=42, hoy=HOY)

    assert f1.equals(f2)
    assert i1.equals(i2)
    assert conteo1 == conteo2


def test_numero_factura_unico_sin_inyeccion_de_duplicados():
    catalogos = _catalogos()
    facturas_df, _, conteo = generar_ventas(catalogos, facturas=50, error_rate=0.0, seed=5, hoy=HOY)

    assert facturas_df["numero_factura"].n_unique() == 50


def test_facturas_limpias_no_repiten_producto_en_la_misma_factura():
    """Con productos elegidos sin reemplazo por factura, una factura
    limpia nunca debería disparar item_duplicado_en_factura por
    coincidencia (bug real encontrado y corregido durante esta sesión)."""
    catalogos = _catalogos()
    facturas_df, items_df, _ = generar_ventas(catalogos, facturas=200, error_rate=0.0, seed=9, hoy=HOY)

    for numero_factura, grupo in items_df.group_by("numero_factura"):
        assert grupo["producto_sku"].n_unique() == grupo.height


def test_facturas_tienen_entre_1_y_5_items():
    catalogos = _catalogos()
    _, items_df, _ = generar_ventas(catalogos, facturas=100, error_rate=0.0, seed=11, hoy=HOY)

    conteo_por_factura = items_df.group_by("numero_factura").len()
    assert conteo_por_factura["len"].min() >= 1
    assert conteo_por_factura["len"].max() <= 5
