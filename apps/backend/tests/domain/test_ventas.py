from src.domain.ventas import VENTA_COLUMNAS_REQUERIDAS, validar_columnas


def test_todas_las_columnas_presentes_es_valido():
    columnas = VENTA_COLUMNAS_REQUERIDAS + ["codigo_descuento"]
    resultado = validar_columnas(columnas)

    assert resultado.valido is True
    assert resultado.columnas_faltantes == []
    assert resultado.columnas_opcionales_presentes == ["codigo_descuento"]
    assert resultado.columnas_extra == []


def test_sin_columna_opcional_sigue_siendo_valido():
    resultado = validar_columnas(VENTA_COLUMNAS_REQUERIDAS)

    assert resultado.valido is True
    assert resultado.columnas_opcionales_presentes == []


def test_columnas_faltantes_se_reportan():
    columnas = [c for c in VENTA_COLUMNAS_REQUERIDAS if c not in ("cantidad", "total")]
    resultado = validar_columnas(columnas)

    assert resultado.valido is False
    assert set(resultado.columnas_faltantes) == {"cantidad", "total"}


def test_columnas_no_esperadas_se_reportan_como_extra():
    columnas = VENTA_COLUMNAS_REQUERIDAS + ["comentario_interno"]
    resultado = validar_columnas(columnas)

    assert resultado.valido is True  # extra no invalida, solo se informa
    assert resultado.columnas_extra == ["comentario_interno"]
