"""Unit tests for search_rule_docs - Qdrant and the embedding model are
mocked, same standard as the other tools (no real network, no real
Qdrant/Ollama/Gemini needed to run these)."""

import pytest
from qdrant_client.http.exceptions import ApiException

from agent.rag import retrieve


@pytest.fixture(autouse=True)
def _index_already_built(monkeypatch):
    """La mayoría de los tests acá prueban la búsqueda, no la
    construcción perezosa del índice - sin esto, cada uno dispararía
    _ensure_index() -> build_index(), que hace HTTP real al backend."""
    monkeypatch.setattr(retrieve, "_index_ready", True)


class FakePoint:
    def __init__(self, nombre, texto, score):
        self.payload = {"nombre": nombre, "texto": texto}
        self.score = score


class FakeQueryResponse:
    def __init__(self, points):
        self.points = points


def test_search_rule_docs_returns_ranked_matches(monkeypatch):
    monkeypatch.setattr(retrieve, "embed_query", lambda text: [0.1] * 768)

    fake_points = [
        FakePoint("fecha_no_futura", "fecha_no_futura: la factura no es futura.", 0.75),
        FakePoint("fecha_posterior_a_apertura", "fecha_posterior_a_apertura: ...", 0.67),
    ]

    def fake_query_points(collection_name, query, limit):
        assert query == [0.1] * 768
        assert limit == 6  # k * 3, para tener margen de deduplicar por nombre
        return FakeQueryResponse(fake_points)

    monkeypatch.setattr(retrieve._client, "query_points", fake_query_points)

    result = retrieve.search_rule_docs.func("una regla sobre fechas futuras", k=2)
    assert result == [
        {"nombre": "fecha_no_futura", "texto": "fecha_no_futura: la factura no es futura.", "score": 0.75},
        {"nombre": "fecha_posterior_a_apertura", "texto": "fecha_posterior_a_apertura: ...", "score": 0.67},
    ]


def test_search_rule_docs_deduplicates_by_rule_name(monkeypatch):
    """Una regla estática tiene un punto en español y uno en inglés - si
    ambos matchean, solo debe devolverse una vez (el de mejor score)."""
    monkeypatch.setattr(retrieve, "embed_query", lambda text: [0.1] * 768)

    fake_points = [
        FakePoint("fecha_no_futura", "fecha_no_futura: (en) the invoice date isn't in the future.", 0.7),
        FakePoint("fecha_no_futura", "fecha_no_futura: la factura no es futura.", 0.65),
        FakePoint("fecha_posterior_a_apertura", "fecha_posterior_a_apertura: ...", 0.6),
    ]

    def fake_query_points(collection_name, query, limit):
        return FakeQueryResponse(fake_points)

    monkeypatch.setattr(retrieve._client, "query_points", fake_query_points)

    result = retrieve.search_rule_docs.func("cualquier cosa", k=2)
    assert [r["nombre"] for r in result] == ["fecha_no_futura", "fecha_posterior_a_apertura"]
    assert result[0]["score"] == 0.7  # se queda con el de mejor score, no el primero que aparezca


def test_search_rule_docs_reports_error_when_qdrant_unreachable(monkeypatch):
    monkeypatch.setattr(retrieve, "embed_query", lambda text: [0.1] * 768)

    def fake_query_points(collection_name, query, limit):
        raise ApiException("connection refused")

    monkeypatch.setattr(retrieve._client, "query_points", fake_query_points)

    result = retrieve.search_rule_docs.func("cualquier cosa")
    assert result[0]["error"]


def test_search_rule_docs_builds_index_lazily_once(monkeypatch):
    """Sin índice listo (caso real: primera pregunta en un proceso nuevo,
    o justo después de invalidate_index()), la primera búsqueda debe
    construirlo antes de buscar; la segunda no debe reconstruirlo."""
    monkeypatch.setattr(retrieve, "_index_ready", False)
    monkeypatch.setattr(retrieve, "embed_query", lambda text: [0.1] * 768)
    monkeypatch.setattr(retrieve._client, "query_points", lambda *a, **k: FakeQueryResponse([]))

    calls = {"n": 0}

    def fake_build_index(client):
        calls["n"] += 1
        assert client is retrieve._client  # mismo cliente, no uno nuevo (ver docstring de build_index)

    import agent.rag.index as index_module

    monkeypatch.setattr(index_module, "build_index", fake_build_index)

    retrieve.search_rule_docs.func("primera pregunta")
    retrieve.search_rule_docs.func("segunda pregunta")
    assert calls["n"] == 1
    assert retrieve._index_ready is True


def test_ensure_index_is_safe_under_concurrent_calls(monkeypatch):
    """Dos preguntas con RAG llegando casi a la vez, mientras el índice
    todavía no existe, no deben disparar build_index() dos veces -
    reproducido en vivo (dos lotes a Gemini corriendo en paralelo) antes
    de agregar el lock, no solo una preocupación teórica."""
    import threading
    import time

    monkeypatch.setattr(retrieve, "_index_ready", False)
    calls = {"n": 0}

    def slow_build_index(client):
        time.sleep(0.05)  # simula la llamada real de red a Gemini
        calls["n"] += 1

    import agent.rag.index as index_module

    monkeypatch.setattr(index_module, "build_index", slow_build_index)

    threads = [threading.Thread(target=retrieve._ensure_index) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert calls["n"] == 1


def test_invalidate_index_forces_a_rebuild_on_the_next_search(monkeypatch):
    monkeypatch.setattr(retrieve, "embed_query", lambda text: [0.1] * 768)
    monkeypatch.setattr(retrieve._client, "query_points", lambda *a, **k: FakeQueryResponse([]))

    calls = {"n": 0}
    import agent.rag.index as index_module

    monkeypatch.setattr(index_module, "build_index", lambda client: calls.__setitem__("n", calls["n"] + 1))

    retrieve.search_rule_docs.func("una pregunta")  # ya "listo" por el fixture autouse
    assert calls["n"] == 0

    retrieve.invalidate_index()
    retrieve.search_rule_docs.func("otra pregunta, tras invalidar")
    assert calls["n"] == 1
