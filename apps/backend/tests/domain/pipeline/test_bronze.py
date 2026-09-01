from io import BytesIO

import polars as pl

from src.domain.pipeline.bronze import to_bronze


def _excel_bytes(df: pl.DataFrame) -> bytes:
    buffer = BytesIO()
    df.write_excel(buffer)
    buffer.seek(0)
    return buffer.read()


def test_every_column_becomes_string_regardless_of_source_type():
    source = pl.DataFrame(
        {
            "numero_factura": ["FAC-0001", "FAC-0002"],
            "cantidad": [2, 1],
            "precio_unitario": [180000.0, 190000.0],
        }
    )

    bronze = to_bronze(_excel_bytes(source))

    assert bronze.height == 2
    assert all(dtype == pl.Utf8 for dtype in bronze.schema.values())
    assert bronze["cantidad"].to_list() == ["2", "1"]


def test_nothing_is_dropped_or_corrected():
    source = pl.DataFrame(
        {
            "numero_factura": ["FAC-0001", ""],
            "cantidad": [2, -3],
        }
    )

    bronze = to_bronze(_excel_bytes(source))

    assert bronze.height == 2
    assert bronze["numero_factura"].to_list() == ["FAC-0001", None]
    assert bronze["cantidad"].to_list() == ["2", "-3"]
