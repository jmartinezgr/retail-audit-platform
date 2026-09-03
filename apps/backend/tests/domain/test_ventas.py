from src.domain.ventas import (
    FACTURA_COLUMNAS_REQUERIDAS,
    ITEM_COLUMNAS_REQUERIDAS,
    validar_columnas_factura,
    validar_columnas_item,
)


def test_todas_las_columnas_presentes_es_valido():
    columnas = FACTURA_COLUMNAS_REQUERIDAS + ["comprador_codigo"]
    resultado = validar_columnas_factura(columnas)

    assert resultado.valido is True
    assert resultado.columnas_faltantes == []
    assert resultado.columnas_opcionales_presentes == ["comprador_codigo"]
    assert resultado.columnas_extra == []


def test_sin_columna_opcional_sigue_siendo_valido():
    resultado = validar_columnas_factura(FACTURA_COLUMNAS_REQUERIDAS)

    assert resultado.valido is True
    assert resultado.columnas_opcionales_presentes == []


def test_columnas_faltantes_se_reportan():
    columnas = [c for c in FACTURA_COLUMNAS_REQUERIDAS if c not in ("iva_pct", "total_factura")]
    resultado = validar_columnas_factura(columnas)

    assert resultado.valido is False
    assert set(resultado.columnas_faltantes) == {"iva_pct", "total_factura"}


def test_columnas_no_esperadas_se_reportan_como_extra():
    columnas = FACTURA_COLUMNAS_REQUERIDAS + ["comentario_interno"]
    resultado = validar_columnas_factura(columnas)

    assert resultado.valido is True  # extra no invalida, solo se informa
    assert resultado.columnas_extra == ["comentario_interno"]


def test_items_todas_las_columnas_presentes_es_valido():
    columnas = ITEM_COLUMNAS_REQUERIDAS + ["codigo_descuento"]
    resultado = validar_columnas_item(columnas)

    assert resultado.valido is True
    assert resultado.columnas_opcionales_presentes == ["codigo_descuento"]


def test_items_columnas_faltantes_se_reportan():
    columnas = [c for c in ITEM_COLUMNAS_REQUERIDAS if c != "total_item"]
    resultado = validar_columnas_item(columnas)

    assert resultado.valido is False
    assert resultado.columnas_faltantes == ["total_item"]
