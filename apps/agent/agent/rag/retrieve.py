"""Búsqueda semántica sobre las descripciones de reglas indexadas por
agent/rag/index.py. Expuesta como tool - docs/copilot-spec.md Fase 3:
para cuando el usuario no sabe el nombre exacto de la regla que busca,
a diferencia de get_rule (tools.py), que necesita el nombre exacto."""

from langchain_core.tools import tool
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ApiException

from agent.settings import settings

_embeddings = OllamaEmbeddings(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_EMBED_MODEL)
_client = QdrantClient(url=settings.QDRANT_URL)


@tool
def search_rule_docs(query: str, k: int = 3) -> list[dict]:
    """Semantic search over rule descriptions - finds relevant rules even
    when you don't know their exact name.

    Args:
        query: a natural-language description of what you're looking
            for, in whichever language the user asked in. Built-in
            rules (the 18 hardcoded ones) are indexed in both Spanish
            and English, so either works directly. User-defined rules
            are indexed in Spanish only (whatever the person who
            created them typed - there's no real translation of that
            text to index, so none was invented). If an English query
            comes back with only weak matches (low scores, nothing
            clearly relevant), try rephrasing it in Spanish before
            concluding there's no matching rule - it may be a
            user-defined one.
        k: how many DISTINCT rules to return (default 3) - built-in
            rules have two indexed chunks (Spanish and English) but you
            only get one entry per rule name, whichever language chunk
            scored higher.

    Returns a list of {nombre, texto, score} - `nombre` is the rule's
    real name, use it with get_rule (full definition) or
    query_gold_results (actual results) next. `texto` is the indexed
    description that matched. `score` is a similarity value (higher is
    more relevant), not a percentage or a guarantee of relevance - a low
    score on every result means none of them are a good match, say so
    instead of picking the top one anyway.

    Use this when the user describes what a rule does without knowing
    its exact name. If you already know the exact name, use get_rule
    directly instead - it's a precise lookup, not an approximate one.

    Returns a single-item list [{"error": "..."}] if the search index
    can't be reached (Qdrant not running) or hasn't been built yet
    (`python -m agent.rag.index` hasn't been run) - never guess a rule
    name from the query itself in that case.
    """
    try:
        vector = _embeddings.embed_query(query)
        # se piden más candidatos que k: cada regla estática tiene 2
        # puntos (es/en), así queda margen para deduplicar por nombre y
        # aun así devolver k reglas distintas, no la misma dos veces.
        results = _client.query_points(settings.QDRANT_COLLECTION, query=vector, limit=k * 3)
    except ApiException as e:
        return [{"error": f"couldn't search rule docs: {e}"}]

    seen: set[str] = set()
    matches: list[dict] = []
    for p in results.points:
        nombre = p.payload["nombre"]
        if nombre in seen:
            continue
        seen.add(nombre)
        matches.append({"nombre": nombre, "texto": p.payload["texto"], "score": round(p.score, 3)})
        if len(matches) >= k:
            break
    return matches
