import polars as pl
import pytest

from src.domain.pipeline.silver import SilverSchemaError, to_silver

VALID_ROW = {
    "numero_factura": "FAC-0001",
    "fecha": "2026-08-15",
    "sede_codigo": "TDA-001",
    "trabajador_codigo": "EMP-0001",
    "producto_sku": "ELEC-0001",
    "cantidad": "2",
    "precio_unitario": "180000",
    "codigo_descuento": None,
    "total": "360000",
    "metodo_pago": "TARJETA",
}


def _bronze(rows: dict[str, list]) -> pl.DataFrame:
    """Construye un DataFrame igual de 'plano' que el que produce bronze:
    todas las columnas como texto."""
    return pl.DataFrame(rows).select(pl.all().cast(pl.Utf8))


def test_valid_row_is_typed_and_marked_valid():
    bronze = _bronze({k: [v] for k, v in VALID_ROW.items()})

    silver = to_silver(bronze)
    row = silver.to_dicts()[0]

    assert row["_es_valida"] is True
    assert row["_errores"] == []
    assert silver.schema["cantidad"] == pl.Int64
    assert silver.schema["precio_unitario"] == pl.Float64
    assert silver.schema["total"] == pl.Float64
    assert silver.schema["fecha"] == pl.Date
    assert row["cantidad"] == 2
    assert row["precio_unitario"] == 180000.0


@pytest.mark.parametrize(
    "field,bad_value,expected_error_substring",
    [
        ("numero_factura", "", "numero_factura vacío"),
        ("sede_codigo", "", "sede_codigo vacío"),
        ("trabajador_codigo", "", "trabajador_codigo vacío"),
        ("producto_sku", "", "producto_sku vacío"),
        ("fecha", "2026-13-40", "fecha inválida"),
        ("cantidad", "-3", "cantidad inválida"),
        ("cantidad", "2.5", "cantidad inválida"),
        ("cantidad", "", "cantidad inválida"),
        ("precio_unitario", "abc", "precio_unitario inválido"),
        ("total", "-100", "total inválido"),
        ("metodo_pago", "BITCOIN", "metodo_pago no reconocido"),
    ],
)
def test_invalid_field_is_flagged_but_row_is_kept(field, bad_value, expected_error_substring):
    row = dict(VALID_ROW)
    row[field] = bad_value
    bronze = _bronze({k: [v] for k, v in row.items()})

    silver = to_silver(bronze)
    result = silver.to_dicts()[0]

    assert silver.height == 1  # la fila no se descarta
    assert result["_es_valida"] is False
    assert any(expected_error_substring in e for e in result["_errores"])


def test_bad_string_field_keeps_original_value_for_review():
    row = dict(VALID_ROW)
    row["metodo_pago"] = "BITCOIN"
    bronze = _bronze({k: [v] for k, v in row.items()})

    result = to_silver(bronze).to_dicts()[0]

    assert result["metodo_pago"] == "BITCOIN"


def test_bad_numeric_field_becomes_null_not_the_raw_value():
    row = dict(VALID_ROW)
    row["cantidad"] = "-3"
    bronze = _bronze({k: [v] for k, v in row.items()})

    result = to_silver(bronze).to_dicts()[0]

    assert result["cantidad"] is None


def test_missing_required_columns_raises_schema_error():
    bronze = _bronze({"numero_factura": ["FAC-0001"], "fecha": ["2026-08-15"]})

    with pytest.raises(SilverSchemaError):
        to_silver(bronze)


def test_missing_optional_column_defaults_to_null_not_an_error():
    row = {k: v for k, v in VALID_ROW.items() if k != "codigo_descuento"}
    bronze = _bronze({k: [v] for k, v in row.items()})

    result = to_silver(bronze).to_dicts()[0]

    assert result["_es_valida"] is True
    assert result["codigo_descuento"] is None
