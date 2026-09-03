import polars as pl
import pytest

from src.domain.pipeline.silver import SilverSchemaError, to_silver_facturas, to_silver_items

VALID_FACTURA = {
    "numero_factura": "FAC-0001",
    "fecha": "2026-08-15",
    "sede_codigo": "TDA-001",
    "trabajador_codigo": "EMP-0001",
    "comprador_codigo": None,
    "metodo_pago": "TARJETA",
    "iva_pct": "19",
    "total_factura": "238000",
}

VALID_ITEM = {
    "numero_factura": "FAC-0001",
    "producto_sku": "ELEC-0001",
    "cantidad": "2",
    "precio_unitario": "100000",
    "codigo_descuento": None,
    "total_item": "200000",
}


def _bronze(rows: dict[str, list]) -> pl.DataFrame:
    """Construye un DataFrame igual de 'plano' que el que produce bronze:
    todas las columnas como texto."""
    return pl.DataFrame(rows).select(pl.all().cast(pl.Utf8))


def _bronze_facturas(row: dict) -> pl.DataFrame:
    return _bronze({k: [v] for k, v in row.items()})


def _bronze_items(row: dict) -> pl.DataFrame:
    return _bronze({k: [v] for k, v in row.items()})


class TestFacturas:
    def test_valid_row_is_typed_and_marked_valid(self):
        silver = to_silver_facturas(_bronze_facturas(VALID_FACTURA))
        row = silver.to_dicts()[0]

        assert row["_es_valida"] is True
        assert row["_errores"] == []
        assert silver.schema["iva_pct"] == pl.Float64
        assert silver.schema["total_factura"] == pl.Float64
        assert silver.schema["fecha"] == pl.Date
        assert row["iva_pct"] == 19.0

    @pytest.mark.parametrize(
        "field,bad_value,expected_error_substring",
        [
            ("numero_factura", "", "numero_factura vacío"),
            ("sede_codigo", "", "sede_codigo vacío"),
            ("trabajador_codigo", "", "trabajador_codigo vacío"),
            ("fecha", "2026-13-40", "fecha inválida"),
            ("iva_pct", "150", "iva_pct inválido"),
            ("iva_pct", "-5", "iva_pct inválido"),
            ("total_factura", "-100", "total_factura inválido"),
            ("metodo_pago", "BITCOIN", "metodo_pago no reconocido"),
        ],
    )
    def test_invalid_field_is_flagged_but_row_is_kept(self, field, bad_value, expected_error_substring):
        row = dict(VALID_FACTURA)
        row[field] = bad_value

        silver = to_silver_facturas(_bronze_facturas(row))
        result = silver.to_dicts()[0]

        assert silver.height == 1
        assert result["_es_valida"] is False
        assert any(expected_error_substring in e for e in result["_errores"])

    def test_missing_required_columns_raises_schema_error(self):
        bronze = _bronze({"numero_factura": ["FAC-0001"]})
        with pytest.raises(SilverSchemaError):
            to_silver_facturas(bronze)

    def test_missing_optional_column_defaults_to_null(self):
        row = {k: v for k, v in VALID_FACTURA.items() if k != "comprador_codigo"}
        result = to_silver_facturas(_bronze_facturas(row)).to_dicts()[0]

        assert result["_es_valida"] is True
        assert result["comprador_codigo"] is None


class TestItems:
    def test_valid_row_is_typed_and_marked_valid(self):
        silver = to_silver_items(_bronze_items(VALID_ITEM), numeros_factura_validos={"FAC-0001"})
        row = silver.to_dicts()[0]

        assert row["_es_valida"] is True
        assert row["_errores"] == []
        assert silver.schema["cantidad"] == pl.Int64
        assert silver.schema["precio_unitario"] == pl.Float64
        assert silver.schema["total_item"] == pl.Float64
        assert row["item_id"] == 1

    @pytest.mark.parametrize(
        "field,bad_value,expected_error_substring",
        [
            ("numero_factura", "", "numero_factura vacío"),
            ("producto_sku", "", "producto_sku vacío"),
            ("cantidad", "-3", "cantidad inválida"),
            ("cantidad", "2.5", "cantidad inválida"),
            ("precio_unitario", "abc", "precio_unitario inválido"),
            ("total_item", "-100", "total_item inválido"),
        ],
    )
    def test_invalid_field_is_flagged_but_row_is_kept(self, field, bad_value, expected_error_substring):
        row = dict(VALID_ITEM)
        row[field] = bad_value

        silver = to_silver_items(_bronze_items(row), numeros_factura_validos={"FAC-0001"})
        result = silver.to_dicts()[0]

        assert silver.height == 1
        assert result["_es_valida"] is False
        assert any(expected_error_substring in e for e in result["_errores"])

    def test_orphan_item_is_flagged(self):
        silver = to_silver_items(_bronze_items(VALID_ITEM), numeros_factura_validos={"FAC-9999"})
        result = silver.to_dicts()[0]

        assert result["_es_valida"] is False
        assert any("no existe en la hoja 'facturas'" in e for e in result["_errores"])

    def test_item_id_assigned_sequentially_per_factura(self):
        bronze = _bronze(
            {
                "numero_factura": ["FAC-0001", "FAC-0001", "FAC-0002"],
                "producto_sku": ["P1", "P2", "P1"],
                "cantidad": ["1", "1", "1"],
                "precio_unitario": ["10", "10", "10"],
                "codigo_descuento": [None, None, None],
                "total_item": ["10", "10", "10"],
            }
        )
        silver = to_silver_items(bronze, numeros_factura_validos={"FAC-0001", "FAC-0002"})
        by_factura = {r["numero_factura"]: [] for r in silver.to_dicts()}
        for r in silver.to_dicts():
            by_factura[r["numero_factura"]].append(r["item_id"])

        assert by_factura["FAC-0001"] == [1, 2]
        assert by_factura["FAC-0002"] == [1]

    def test_missing_required_columns_raises_schema_error(self):
        bronze = _bronze({"numero_factura": ["FAC-0001"]})
        with pytest.raises(SilverSchemaError):
            to_silver_items(bronze, numeros_factura_validos=set())
