"""Switch de proveedor de embeddings - Ollama (local, gratis, necesita
Ollama corriendo) o Gemini (API gratuita de Google AI Studio, sin
tarjeta). Independiente del LLM_PROVIDER del chat: Groq no ofrece
embeddings propios, así que producción mezcla Groq (chat) + Gemini
(embeddings).

Gemini va por `httpx` crudo, no por `langchain-google-genai` - una
llamada HTTP, y así el backend de producción no carga ese SDK completo
(protobuf/grpc incluidos) solo para esto - ver apps/agent/README.md.
Forma del endpoint y dimensión real (3072, no asumida) verificadas en
vivo contra la API antes de escribir esto, mismo principio que ya se
aplicó con LangChain/LangGraph/MCP en este proyecto.
"""

import httpx

from agent.settings import settings

_GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
_GEMINI_BATCH_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"


def _gemini_embed_one(text: str, task_type: str) -> list[float]:
    resp = httpx.post(
        _GEMINI_EMBED_URL.format(model=settings.GEMINI_EMBED_MODEL),
        params={"key": settings.GOOGLE_API_KEY},
        json={
            "model": f"models/{settings.GEMINI_EMBED_MODEL}",
            "content": {"parts": [{"text": text}]},
            "taskType": task_type,
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


def _gemini_embed_batch(texts: list[str], task_type: str) -> list[list[float]]:
    """Una sola llamada HTTP para todos los textos (batchEmbedContents),
    no una por texto - indexar ~40 chunks uno a la vez tardaba ~45s
    (reconstrucción perezosa real en producción, un usuario esperando
    una respuesta HTTP) y en lote baja a ~2.5s, verificado en vivo con
    45 textos antes de escribir esto. El orden de `embeddings` en la
    respuesta corresponde 1:1 al orden de `requests` enviado."""
    resp = httpx.post(
        _GEMINI_BATCH_EMBED_URL.format(model=settings.GEMINI_EMBED_MODEL),
        params={"key": settings.GOOGLE_API_KEY},
        json={
            "requests": [
                {
                    "model": f"models/{settings.GEMINI_EMBED_MODEL}",
                    "content": {"parts": [{"text": text}]},
                    "taskType": task_type,
                }
                for text in texts
            ]
        },
        timeout=30,
    )
    resp.raise_for_status()
    return [e["values"] for e in resp.json()["embeddings"]]


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Para indexar (RAG, build_index) - en Gemini usa el task_type
    RETRIEVAL_DOCUMENT, pensado para el lado "corpus" de una búsqueda
    asimétrica (ver embed_query), y la llamada en lote (ver
    _gemini_embed_batch) porque acá sí hay muchos textos a la vez.
    Ollama no tiene concepto de task_type ni de lote."""
    if settings.EMBED_PROVIDER == "gemini":
        return _gemini_embed_batch(texts, "RETRIEVAL_DOCUMENT")
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_EMBED_MODEL).embed_documents(
        texts
    )


def embed_query(text: str) -> list[float]:
    """Para buscar (search_rule_docs) - un solo texto, RETRIEVAL_QUERY en
    Gemini - no hace falta el endpoint en lote acá."""
    if settings.EMBED_PROVIDER == "gemini":
        return _gemini_embed_one(text, "RETRIEVAL_QUERY")
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_EMBED_MODEL).embed_query(text)
