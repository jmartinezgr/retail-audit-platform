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


# --- explain_invoice_result ----------------------------------------------


def test_explain_invoice_result_returns_full_detail(monkeypatch):
    detail = {
        "facturas": [{"numero_factura": "FAC-1"}],
        "items": [],
        "evaluaciones_cabecera": [
            {"regla": "sede_existe", "severidad": "ERROR", "paso": True},
            {"regla": "factura_total_cuadra", "severidad": "ERROR", "paso": False},
        ],
        "evaluaciones_items": [
            {"regla": "margen_no_negativo", "severidad": "WARNING", "paso": False},
        ],
        "gold_ready": True,
    }

    def fake_get(url, timeout=None, **kwargs):
        assert url.endswith("/audits/job-1/factura/FAC-1")
        return FakeResponse(detail)

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.explain_invoice_result.func("FAC-1", dataset_id="job-1")

    # el punto de esto: el conteo NO se le deja al modelo, se pre-calcula acá
    assert result["resumen"] == {
        "total_evaluaciones": 3,
        "total_fallidas": 2,
        "fallidas_error": 1,
        "fallidas_warning": 1,
    }
    assert result["violaciones"] == [
        {"regla": "factura_total_cuadra", "severidad": "ERROR", "paso": False},
        {"regla": "margen_no_negativo", "severidad": "WARNING", "paso": False},
    ]


def test_explain_invoice_result_reports_error_when_invoice_not_found(monkeypatch):
    def fake_get(url, timeout=None, **kwargs):
        return FakeResponse({"facturas": [], "items": [], "gold_ready": True})

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.explain_invoice_result.func("FAC-999", dataset_id="job-1")
    assert "error" in result


def test_explain_invoice_result_reports_error_when_gold_not_ready(monkeypatch):
    def fake_get(url, timeout=None, **kwargs):
        return FakeResponse({"facturas": [{"numero_factura": "FAC-1"}], "gold_ready": False})

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    result = tools.explain_invoice_result.func("FAC-1", dataset_id="job-1")
    assert "error" in result


# --- run_rule -------------------------------------------------------------


def test_run_rule_returns_results(monkeypatch):
    resultados = [{"regla": "item_cuadra", "item_id": 1, "paso": True}]

    def fake_post(url, params=None, timeout=None, **kwargs):
        assert url.endswith("/audits/job-1/factura/FAC-1/run-rule")
        assert params == {"regla": "item_cuadra"}
        return FakeResponse({"resultados": resultados})

    monkeypatch.setattr(tools.httpx, "post", fake_post)
    result = tools.run_rule.func("item_cuadra", "FAC-1", dataset_id="job-1")
    assert result == resultados


def test_run_rule_reports_error_when_not_found(monkeypatch):
    def fake_post(url, params=None, timeout=None, **kwargs):
        return FakeResponse({"detail": "invoice not found"}, status_code=404)

    monkeypatch.setattr(tools.httpx, "post", fake_post)
    result = tools.run_rule.func("item_cuadra", "FAC-999", dataset_id="job-1")
    assert result[0]["error"] == "invoice not found"


# --- _get_with_retry -------------------------------------------------------


def test_get_with_retry_retries_on_timeout_then_succeeds(monkeypatch):
    """Caso real visto en vivo más de una vez: /healthz respondía en
    <1s (no estaba dormido) pero la siguiente llamada real daba
    "timed out" - un reintento simple la resolvía."""
    monkeypatch.setattr(tools.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.TimeoutException("timed out")
        return FakeResponse({"ok": True})

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    resp = tools._get_with_retry("http://backend/x")
    assert resp.json() == {"ok": True}
    assert calls["n"] == 2


def test_get_with_retry_retries_on_5xx_then_succeeds(monkeypatch):
    monkeypatch.setattr(tools.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResponse({"detail": "bad gateway"}, status_code=502)
        return FakeResponse({"ok": True})

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    resp = tools._get_with_retry("http://backend/x")
    assert resp.json() == {"ok": True}
    assert calls["n"] == 2


def test_get_with_retry_gives_up_after_exhausting_attempts(monkeypatch):
    monkeypatch.setattr(tools.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    with pytest.raises(httpx.ConnectError):
        tools._get_with_retry("http://backend/x", retries=2)
    assert calls["n"] == 3  # intento original + 2 reintentos, no más


def test_get_with_retry_does_not_retry_a_4xx(monkeypatch):
    """Un 404 (ej. "gold todavía no existe") es un estado real del
    backend, no un problema de red - reintentarlo no cambiaría nada."""
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        return FakeResponse({"detail": "not found"}, status_code=404)

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    resp = tools._get_with_retry("http://backend/x")
    assert resp.status_code == 404
    assert calls["n"] == 1


def test_run_rule_does_not_retry_its_post(monkeypatch):
    """La escritura (POST) nunca debe reintentarse sola - a diferencia
    de las lecturas de arriba, repetirla sí tendría un efecto real."""
    calls = {"n": 0}

    def fake_post(url, params=None, timeout=None, **kwargs):
        calls["n"] += 1
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(tools.httpx, "post", fake_post)
    result = tools.run_rule.func("item_cuadra", "FAC-1", dataset_id="job-1")
    assert "error" in result[0]
    assert calls["n"] == 1


# --- _resolve_dataset_id / contexto de sesión -----------------------------


def test_resolve_dataset_id_sends_session_header_when_set(monkeypatch):
    """Bug real: sin esto, 'el dataset más reciente' siempre caía en el
    cajón "anonymous" del backend (ver api/uploads/router.py), nunca en
    el de quien de verdad está chateando - encontrado probando el chat
    en vivo, no en un test."""
    seen_headers = {}

    def fake_get(url, headers=None, timeout=None, **kwargs):
        seen_headers.update(headers or {})
        return FakeResponse({"uploads": [{"upload_id": "session-job"}]})

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    token = tools.context.session_id.set("visitor-abc123")
    try:
        result = tools._resolve_dataset_id(None)
    finally:
        tools.context.session_id.reset(token)

    assert result == "session-job"
    assert seen_headers == {"X-Client-Id": "visitor-abc123"}


def test_resolve_dataset_id_sends_no_session_header_by_default(monkeypatch):
    """CLI y MCP (Claude Desktop, etc.) no tienen concepto de sesión de
    navegador - deben seguir cayendo en "anonymous" en el backend, igual
    que siempre, sin mandar el header."""
    seen_headers = {}

    def fake_get(url, headers=None, timeout=None, **kwargs):
        seen_headers.update(headers or {})
        return FakeResponse({"uploads": [{"upload_id": "anon-job"}]})

    monkeypatch.setattr(tools.httpx, "get", fake_get)
    assert tools.context.session_id.get() is None  # nadie lo seteó en este test
    result = tools._resolve_dataset_id(None)

    assert result == "anon-job"
    assert seen_headers == {}


def test_resolve_dataset_id_is_isolated_across_concurrent_sessions(monkeypatch):
    """El contexto es por hilo, no un global compartido - dos 'sesiones'
    distintas resolviendo 'el dataset más reciente' al mismo tiempo no
    deben verse la una a la otra, ni mezclarse. Esto es justo lo que un
    único threadpool de FastAPI puede producir bajo tráfico real (dos
    visitantes preguntando casi a la vez) - se prueba con hilos reales,
    no solo llamadas secuenciales."""
    import threading

    def fake_get(url, headers=None, timeout=None, **kwargs):
        sid = (headers or {}).get("X-Client-Id", "anonymous")
        return FakeResponse({"uploads": [{"upload_id": f"job-for-{sid}"}]})

    monkeypatch.setattr(tools.httpx, "get", fake_get)

    results: dict[str, str] = {}

    def worker(session: str):
        token = tools.context.session_id.set(session)
        try:
            results[session] = tools._resolve_dataset_id(None)
        finally:
            tools.context.session_id.reset(token)

    sessions = [f"visitor-{i}" for i in range(8)]
    threads = [threading.Thread(target=worker, args=(s,)) for s in sessions]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for s in sessions:
        assert results[s] == f"job-for-{s}"
