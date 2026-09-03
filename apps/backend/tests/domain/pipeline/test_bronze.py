from io import BytesIO

import polars as pl
import pytest
from xlsxwriter import Workbook

from src.domain.pipeline.bronze import HojaFaltanteError, read_columns, to_bronze

FACTURAS = pl.DataFrame({"numero_factura": ["FAC-0001", "FAC-0002"], "total_factura": [119000.0, 238000.0]})
ITEMS = pl.DataFrame({"numero_factura": ["FAC-0001", "FAC-0002"], "cantidad": [2, 1]})


def _excel_bytes(facturas: pl.DataFrame, items: pl.DataFrame) -> bytes:
    buffer = BytesIO()
    with Workbook(buffer, {"in_memory": True}) as wb:
        facturas.write_excel(workbook=wb, worksheet="facturas")
        items.write_excel(workbook=wb, worksheet="items")
    buffer.seek(0)
    return buffer.read()


def test_every_column_becomes_string_regardless_of_source_type():
    bronze_facturas, bronze_items = to_bronze(_excel_bytes(FACTURAS, ITEMS))

    assert bronze_facturas.height == 2
    assert all(dtype == pl.Utf8 for dtype in bronze_facturas.schema.values())
    assert bronze_items["cantidad"].to_list() == ["2", "1"]


def test_nothing_is_dropped_or_corrected():
    # una fila con numero_factura vacío pero otra columna con valor real,
    # para que el motor de excel no la trate como fila enteramente vacía
    # (esas sí se descartan por default al leer) y así probar de verdad
    # que bronze no filtra filas con campos vacíos
    facturas = pl.DataFrame({"numero_factura": ["FAC-0001", ""], "total_factura": [119000.0, 50000.0]})
    items = pl.DataFrame({"numero_factura": ["FAC-0001", "FAC-0001"], "cantidad": [2, -3]})

    bronze_facturas, bronze_items = to_bronze(_excel_bytes(facturas, items))

    assert bronze_facturas.height == 2
    assert bronze_facturas["numero_factura"].to_list() == ["FAC-0001", None]
    assert bronze_items["cantidad"].to_list() == ["2", "-3"]


def test_missing_sheet_raises():
    buffer = BytesIO()
    with Workbook(buffer, {"in_memory": True}) as wb:
        FACTURAS.write_excel(workbook=wb, worksheet="facturas")
    buffer.seek(0)

    with pytest.raises(HojaFaltanteError):
        to_bronze(buffer.read())


def test_read_columns_returns_both_sheets_headers():
    hojas = read_columns(_excel_bytes(FACTURAS, ITEMS))

    assert set(hojas["facturas"]) == {"numero_factura", "total_factura"}
    assert set(hojas["items"]) == {"numero_factura", "cantidad"}
