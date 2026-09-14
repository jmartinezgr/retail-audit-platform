"""Unit tests for search_rule_docs - Qdrant and the embedding model are
mocked, same standard as the other tools (no real network, no real
Qdrant/Ollama needed to run these)."""

from qdrant_client.http.exceptions import ApiException

from agent.rag import retrieve


class FakePoint:
    def __init__(self, nombre, texto, score):
        self.payload = {"nombre": nombre, "texto": texto}
        self.score = score


class FakeQueryResponse:
    def __init__(self, points):
        self.points = points


class FakeEmbeddings:
    def embed_query(self, text):
        return [0.1] * 768


def test_search_rule_docs_returns_ranked_matches(monkeypatch):
    monkeypatch.setattr(retrieve, "_embeddings", FakeEmbeddings())

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
    monkeypatch.setattr(retrieve, "_embeddings", FakeEmbeddings())

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
    monkeypatch.setattr(retrieve, "_embeddings", FakeEmbeddings())

    def fake_query_points(collection_name, query, limit):
        raise ApiException("connection refused")

    monkeypatch.setattr(retrieve._client, "query_points", fake_query_points)

    result = retrieve.search_rule_docs.func("cualquier cosa")
    assert result[0]["error"]
