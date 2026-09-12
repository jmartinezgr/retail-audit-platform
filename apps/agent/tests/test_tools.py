"""Unit tests for the tool wrappers - the backend is mocked at the
httpx boundary, same standard as the domain package's 97 tests (no real
network, no real Postgres/R2, no real Ollama)."""

import httpx
import pytest

from agent import tools


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


# --- get_rule ---------------------------------------------------------


def test_get_rule_finds_dynamic_rule(monkeypatch):
    dynamic_rule = {"nombre": "descuento_maximo_ropa", "tipo": "UMBRAL", "severidad": "WARNING"}

    def fake_get(url, timeout=None, **kwargs):
        assert url.endswith("/rules/")
        return FakeResponse([dynamic_rule])

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.get_rule.func("descuento_maximo_ropa")
    assert result == dynamic_rule


def test_get_rule_falls_back_to_static_rule(monkeypatch):
    static_rule = {"nombre": "sede_existe", "severidad": "ERROR", "ambito": "CABECERA"}

    def fake_get(url, timeout=None, **kwargs):
        if url.endswith("/rules/"):
            return FakeResponse([])  # no dynamic rules match
        assert url.endswith("/rules/static/sede_existe")
        return FakeResponse(static_rule)

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.get_rule.func("sede_existe")
    assert result == static_rule


def test_get_rule_reports_error_when_name_does_not_exist(monkeypatch):
    def fake_get(url, timeout=None, **kwargs):
        if url.endswith("/rules/"):
            return FakeResponse([])
        return FakeResponse({"detail": "not found"}, status_code=404)

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.get_rule.func("no_existe")
    assert "error" in result


def test_get_rule_reports_error_when_backend_unreachable(monkeypatch):
    def fake_get(url, timeout=None, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.get_rule.func("sede_existe")
    assert "error" in result


# --- query_gold_results -------------------------------------------------


def test_query_gold_results_with_explicit_dataset_id(monkeypatch):
    rows = [{"numero_factura": "FAC-0000001", "regla": "sede_existe", "paso": True}]

    def fake_get(url, params=None, timeout=None, **kwargs):
        assert url.endswith("/audits/job-1/gold/query")
        assert params["regla"] == "sede_existe"
        return FakeResponse({"rows": rows})

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.query_gold_results.func(rule_id="sede_existe", dataset_id="job-1", limit=20)
    assert result == rows


def test_query_gold_results_defaults_to_latest_dataset(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None, **kwargs):
        calls.append(url)
        if "/uploads/" in url:
            return FakeResponse({"uploads": [{"upload_id": "latest-job"}]})
        assert url.endswith("/audits/latest-job/gold/query")
        return FakeResponse({"rows": []})

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    tools.query_gold_results.func(dataset_id=None)
    assert any("/uploads/" in c for c in calls)
    assert any(c.endswith("/audits/latest-job/gold/query") for c in calls)


def test_query_gold_results_reports_error_when_no_datasets_exist(monkeypatch):
    def fake_get(url, params=None, timeout=None, **kwargs):
        return FakeResponse({"uploads": []})

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.query_gold_results.func(dataset_id=None)
    assert result[0]["error"]


def test_query_gold_results_reports_error_when_gold_not_ready(monkeypatch):
    def fake_get(url, params=None, timeout=None, **kwargs):
        return FakeResponse({"detail": "not ready"}, status_code=404)

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.query_gold_results.func(dataset_id="job-1")
    assert result[0]["error"]


# --- summarize_dataset --------------------------------------------------


def test_summarize_dataset_truncates_to_top_n(monkeypatch):
    reglas = [{"regla": f"regla_{i}", "facturas_afectadas": 10 - i} for i in range(10)]

    def fake_get(url, timeout=None, **kwargs):
        return FakeResponse({"total_facturas": 100, "reglas": reglas})

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.summarize_dataset.func(dataset_id="job-1", top_n=3)
    assert len(result["reglas"]) == 3
    assert result["reglas"] == reglas[:3]


def test_summarize_dataset_reports_error_when_gold_not_ready(monkeypatch):
    def fake_get(url, timeout=None, **kwargs):
        return FakeResponse({"detail": "not ready"}, status_code=404)

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.summarize_dataset.func(dataset_id="job-1")
    assert "error" in result
