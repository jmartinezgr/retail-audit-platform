"""Tests del router del copiloto - solo el rate limit y la extracción de
IP real (lo único con lógica propia acá; `ask()` en sí ya se prueba
manualmente contra Ollama/Groq reales, ver apps/agent/README.md). Monta
solo este router en una FastAPI mínima, no src.main:app completo - no
hace falta Postgres/MinIO para esto."""

from collections import defaultdict

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.agent import router as router_module
from src.api.agent.router import router


def _make_client(monkeypatch, ask_result=None, ask_error=None, captured_calls=None):
    def fake_ask(question: str, session_id: str | None = None) -> dict:
        if captured_calls is not None:
            captured_calls.append({"question": question, "session_id": session_id})
        if ask_error:
            raise ask_error
        return ask_result or {"answer": "ok", "tool_calls": []}

    monkeypatch.setattr(router_module, "ask", fake_ask)
    monkeypatch.setattr(router_module, "_requests_by_ip", defaultdict(list))

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_allows_up_to_the_limit_then_429s(monkeypatch):
    client = _make_client(monkeypatch)

    for _ in range(router_module._RATE_LIMIT):
        res = client.post("/agent/ask", json={"question": "hola"})
        assert res.status_code == 200

    res = client.post("/agent/ask", json={"question": "una de más"})
    assert res.status_code == 429
    assert "limit" in res.json()["detail"].lower()


def test_rate_limit_is_per_ip_not_global(monkeypatch):
    client = _make_client(monkeypatch)

    for _ in range(router_module._RATE_LIMIT):
        res = client.post(
            "/agent/ask", json={"question": "hola"}, headers={"X-Forwarded-For": "1.1.1.1"}
        )
        assert res.status_code == 200

    # misma IP ya agotó su cupo
    assert client.post(
        "/agent/ask", json={"question": "otra"}, headers={"X-Forwarded-For": "1.1.1.1"}
    ).status_code == 429

    # una IP distinta no debe verse afectada
    res = client.post(
        "/agent/ask", json={"question": "hola"}, headers={"X-Forwarded-For": "2.2.2.2"}
    )
    assert res.status_code == 200


def test_uses_x_forwarded_for_over_the_proxy_connection_ip(monkeypatch):
    client = _make_client(monkeypatch)
    client.post("/agent/ask", json={"question": "hola"}, headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.1"})
    assert "9.9.9.9" in router_module._requests_by_ip
    assert "10.0.0.1" not in router_module._requests_by_ip


def test_translates_agent_unavailable_to_503(monkeypatch):
    from src.api.agent.service import AgentUnavailableError

    client = _make_client(monkeypatch, ask_error=AgentUnavailableError("no configurado"))
    res = client.post("/agent/ask", json={"question": "hola"})
    assert res.status_code == 503
    assert res.json()["detail"] == "no configurado"


def test_forwards_x_client_id_to_ask_as_session_id(monkeypatch):
    """Bug real: sin esto, el copiloto de un visitante siempre resolvía
    'el dataset más reciente' contra el cajón "anonymous" del backend,
    nunca contra los datasets reales de esa sesión - ver
    apps/agent/agent/tools.py:_resolve_dataset_id."""
    calls = []
    client = _make_client(monkeypatch, captured_calls=calls)

    client.post("/agent/ask", json={"question": "hola"}, headers={"X-Client-Id": "visitor-abc123"})

    assert calls == [{"question": "hola", "session_id": "visitor-abc123"}]


def test_session_id_is_none_without_the_header(monkeypatch):
    """Sin header (CLI, scripts, un cliente viejo) -> None, que en
    tools.py cae al comportamiento de siempre ("anonymous" en el
    backend) - no un string vacío ni "anonymous" puesto a mano acá."""
    calls = []
    client = _make_client(monkeypatch, captured_calls=calls)

    client.post("/agent/ask", json={"question": "hola"})

    assert calls == [{"question": "hola", "session_id": None}]
