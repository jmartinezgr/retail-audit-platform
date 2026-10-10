"""Búsqueda semántica sobre las descripciones de reglas indexadas por
agent/rag/index.py. Expuesta como tool - docs/copilot-spec.md Fase 3:
para cuando el usuario no sabe el nombre exacto de la regla que busca,
a diferencia de get_rule (tools.py), que necesita el nombre exacto."""

import threading

from langchain_core.tools import tool
from qdrant_client import QdrantClient

from agent.rag.embeddings import embed_query
from agent.settings import settings

# `location`, no `url` - ver el comentario equivalente en index.py.
_client = QdrantClient(location=settings.QDRANT_URL)

# Se construye perezosamente, en la primera búsqueda real, no al
# importar el módulo - el backend necesita estar arriba para que
# _fetch_rules() (index.py) pueda leer las reglas, y en producción
# (QDRANT_URL=":memory:") no hay ningún paso manual de indexado
# posible, tiene que pasar solo. Reusa SIEMPRE este mismo `_client`
# (ver index.py: en modo ":memory:" cada QdrantClient nuevo es una base
# en RAM aislada - confirmado en vivo).
_index_ready = False
# El backend sirve /agent/ask con un endpoint `def` (threadpool, no
# async) para no bloquear el event loop (ver apps/agent/README.md) - eso
# significa que SÍ puede haber varias preguntas corriendo en hilos
# distintos al mismo tiempo, aunque Render use WEB_CONCURRENCY=1 (un
# solo proceso, no un solo hilo). Sin este lock, dos preguntas con RAG
# que llegan mientras el índice todavía no existe disparan cada una su
# propio build_index() en paralelo - reproducido en vivo (dos llamadas
# en lote a Gemini pisándose), no solo teórico.
_index_lock = threading.Lock()


def _ensure_index() -> None:
    global _index_ready
    if _index_ready:
        return
    with _index_lock:
        if _index_ready:  # otro hilo ya lo construyó mientras esperábamos el lock
            return
        from agent.rag.index import build_index

        build_index(client=_client)
        _index_ready = True


def invalidate_index() -> None:
    """Llamar cuando se crea/edita/borra una regla dinámica (ver
    apps/backend/src/api/rules/service.py) - no reconstruye ahora mismo,
    solo marca el índice como desactualizado para que la próxima
    búsqueda real lo reconstruya con las reglas vigentes."""
    global _index_ready
    _index_ready = False


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
        _ensure_index()
        vector = embed_query(query)
        # se piden más candidatos que k: cada regla estática tiene 2
        # puntos (es/en), así queda margen para deduplicar por nombre y
        # aun así devolver k reglas distintas, no la misma dos veces.
        results = _client.query_points(settings.QDRANT_COLLECTION, query=vector, limit=k * 3)
    except Exception as e:
        # Exception a propósito, no solo ApiException (lo que atrapaba
        # antes) - _ensure_index() (build/re-index perezoso) y
        # embed_query() pueden fallar por motivos nuevos que antes no
        # existían acá (Qdrant no alcanzable, el backend no responde al
        # indexar, la API de embeddings sin cuota o caída): ninguno debe
        # tumbar el agente, todos se reportan igual - que no se pudo
        # buscar.
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
