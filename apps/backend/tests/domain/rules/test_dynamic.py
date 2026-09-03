from datetime import date

import polars as pl

from src.domain.pipeline.gold import to_gold
from src.domain.rules.types import AmbitoRegla, CatalogosSnapshot, Operador, ReglaDinamica, Severidad, TipoReglaDinamica

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
    "total_item": 200.0,  # sin descuento: 2 * 100
}


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


def _gold(reglas: list[ReglaDinamica], facturas=None, items=None, catalogos=None) -> pl.DataFrame:
    return to_gold(
        _facturas(facturas or [CLEAN_FACTURA]),
        _items(items if items is not None else [CLEAN_ITEM]),
        catalogos or _catalogos(),
        reglas_dinamicas=reglas,
        hoy=HOY,
    )


def _paso(gold: pl.DataFrame, regla: str) -> bool:
    return gold.filter(pl.col("regla") == regla)["paso"][0]


def _umbral(**overrides) -> ReglaDinamica:
    defaults = dict(
        id=1,
        nombre="descuento_maximo_ropa",
        tipo=TipoReglaDinamica.UMBRAL,
        ambito=AmbitoRegla.ITEM,
        severidad=Severidad.WARNING,
        activa=True,
        mensaje="descuento por encima del máximo permitido",
        campo="descuento_pct",
        operador=Operador.GT,
        valor=0.20,
    )
    defaults.update(overrides)
    return ReglaDinamica(**defaults)


def _ventana(**overrides) -> ReglaDinamica:
    defaults = dict(
        id=2,
        nombre="sede_en_mantenimiento",
        tipo=TipoReglaDinamica.VENTANA_EXCLUSION,
        ambito=AmbitoRegla.CABECERA,
        severidad=Severidad.ERROR,
        activa=True,
        mensaje="la sede estaba en mantenimiento, no debería tener ventas",
        sede_codigo="S1",
        fecha_inicio=date(2026, 8, 1),
        fecha_fin=date(2026, 8, 31),
    )
    defaults.update(overrides)
    return ReglaDinamica(**defaults)


def test_umbral_item_pasa_por_debajo_del_limite():
    # CLEAN_ITEM no tiene descuento (descuento_pct = 0), 0 > 0.20 es falso
    gold = _gold([_umbral()])
    assert _paso(gold, "descuento_maximo_ropa") is True


def test_umbral_item_falla_por_encima_del_limite():
    item = {**CLEAN_ITEM, "total_item": 140.0}  # 30% de descuento sobre 200
    gold = _gold([_umbral()], items=[item])
    assert _paso(gold, "descuento_maximo_ropa") is False


def test_umbral_respeta_filtro_categoria():
    item = {**CLEAN_ITEM, "total_item": 140.0}  # violaría la regla, pero es de otra categoría
    gold = _gold([_umbral(filtro_categoria="ELECTRONICA")], items=[item])
    assert _paso(gold, "descuento_maximo_ropa") is True


def test_umbral_na_cuando_el_campo_calculado_es_null():
    # cantidad*precio_unitario = 0 -> descuento_pct es null -> N/A, pasa
    item = {**CLEAN_ITEM, "cantidad": 0, "precio_unitario": 0.0, "total_item": 0.0}
    gold = _gold([_umbral()], items=[item])
    assert _paso(gold, "descuento_maximo_ropa") is True


def test_umbral_cabecera():
    regla = _umbral(
        nombre="iva_alto", ambito=AmbitoRegla.CABECERA, campo="iva_pct", operador=Operador.GT, valor=25.0,
    )
    gold_ok = _gold([regla])
    assert _paso(gold_ok, "iva_alto") is True

    factura_iva_alto = {**CLEAN_FACTURA, "iva_pct": 30.0, "total_factura": 260.0}
    gold_fail = _gold([regla], facturas=[factura_iva_alto])
    assert _paso(gold_fail, "iva_alto") is False


def test_ventana_exclusion_falla_dentro_del_rango():
    gold = _gold([_ventana()])
    assert _paso(gold, "sede_en_mantenimiento") is False


def test_ventana_exclusion_pasa_fuera_del_rango():
    factura = {**CLEAN_FACTURA, "fecha": date(2026, 7, 1)}
    gold = _gold([_ventana()], facturas=[factura])
    assert _paso(gold, "sede_en_mantenimiento") is True


def test_ventana_exclusion_pasa_en_otra_sede():
    gold = _gold([_ventana(sede_codigo="S2")])
    assert _paso(gold, "sede_en_mantenimiento") is True


def test_regla_inactiva_no_produce_filas():
    gold = _gold([_umbral(activa=False)])
    assert gold.filter(pl.col("regla") == "descuento_maximo_ropa").height == 0


def test_reglas_estaticas_siguen_presentes_junto_a_las_dinamicas():
    gold = _gold([_umbral(), _ventana()])
    assert "sede_existe" in gold["regla"].to_list()
    assert "item_cuadra" in gold["regla"].to_list()
    assert gold.filter(pl.col("regla") == "descuento_maximo_ropa").height == 1
    assert gold.filter(pl.col("regla") == "sede_en_mantenimiento").height == 1
