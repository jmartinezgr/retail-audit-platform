"""Unit tests for the embedding provider switch - no real network, no
real Ollama/Gemini needed to run these."""

from agent import settings as settings_module
from agent.rag import embeddings


def test_embed_query_uses_gemini_httpx_when_configured(monkeypatch):
    monkeypatch.setattr(settings_module.settings, "EMBED_PROVIDER", "gemini")
    monkeypatch.setattr(settings_module.settings, "GOOGLE_API_KEY", "fake-key")
    monkeypatch.setattr(settings_module.settings, "GEMINI_EMBED_MODEL", "gemini-embedding-001")

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embedding": {"values": [0.1, 0.2, 0.3]}}

    def fake_post(url, params, json, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(embeddings.httpx, "post", fake_post)

    vector = embeddings.embed_query("una pregunta")

    assert vector == [0.1, 0.2, 0.3]
    assert captured["params"] == {"key": "fake-key"}
    assert captured["json"]["taskType"] == "RETRIEVAL_QUERY"
    assert captured["json"]["content"]["parts"][0]["text"] == "una pregunta"
    assert "gemini-embedding-001" in captured["url"]


def test_embed_documents_uses_batch_endpoint_with_document_task_type(monkeypatch):
    """Un solo POST para todos los textos (batchEmbedContents), no uno
    por texto - indexar ~40 chunks uno a la vez tardaba ~45s reales en
    producción (reconstrucción perezosa del índice, ver
    agent/rag/retrieve.py), un usuario esperando una respuesta HTTP."""
    monkeypatch.setattr(settings_module.settings, "EMBED_PROVIDER", "gemini")
    monkeypatch.setattr(settings_module.settings, "GOOGLE_API_KEY", "fake-key")

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embeddings": [{"values": [0.1, 0.2]}, {"values": [0.3, 0.4]}]}

    def fake_post(url, params, json, timeout):
        captured["url"] = url
        captured["requests"] = json["requests"]
        return FakeResponse()

    monkeypatch.setattr(embeddings.httpx, "post", fake_post)

    vectors = embeddings.embed_documents(["texto uno", "texto dos"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert "batchEmbedContents" in captured["url"]
    assert len(captured["requests"]) == 2
    assert all(r["taskType"] == "RETRIEVAL_DOCUMENT" for r in captured["requests"])
    assert captured["requests"][0]["content"]["parts"][0]["text"] == "texto uno"
    assert captured["requests"][1]["content"]["parts"][0]["text"] == "texto dos"


def test_embed_query_uses_ollama_by_default(monkeypatch):
    """EMBED_PROVIDER="ollama" (default) no debe tocar httpx/Gemini para
    nada - el import de OllamaEmbeddings es perezoso, mockeado acá vía el
    propio langchain_ollama para no necesitar Ollama corriendo."""
    assert settings_module.settings.EMBED_PROVIDER == "ollama"

    import langchain_ollama

    class FakeOllamaEmbeddings:
        def __init__(self, base_url, model):
            pass

        def embed_query(self, text):
            return [9.9]

    monkeypatch.setattr(langchain_ollama, "OllamaEmbeddings", FakeOllamaEmbeddings)

    assert embeddings.embed_query("hola") == [9.9]
