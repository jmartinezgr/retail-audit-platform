"""Wrapper del copiloto (apps/agent, LangGraph) como servicio del backend.

En local, por defecto corre 100% con Ollama (chat + embeddings) y un
Qdrant propio - ver apps/agent/README.md. En producción (Render) usa
proveedores gratuitos hosteados en vez de nada local: Groq para el chat
(LLM_PROVIDER=groq, tool-calling real, verificado en vivo) y Gemini para
embeddings (EMBED_PROVIDER=gemini, llamada HTTP directa, sin SDK
pesado), con Qdrant en modo ":memory:" (QDRANT_URL=":memory:", sin
servidor aparte, índice en RAM del propio proceso, se construye solo en
el primer uso real - ver agent/rag/retrieve.py). Si esas env vars no
están puestas en el entorno, cae a 503 con un mensaje claro en vez de
reventar - sigue siendo opcional, no una dependencia dura del backend.

Importa `agent.graph` metiendo apps/agent al sys.path en vez de
instalarlo como dependencia declarada del backend (mismo problema que el
server MCP - ver apps/agent/agent/mcp_server.py - y misma solución), así
el backend de producción solo carga lo que realmente hace falta para
correr el copiloto (ver requirements.txt - subconjunto curado, sin
langchain-ollama/mcp/pytest que ahí no pintan nada) y nada más si nadie
usa el chat.
"""

import json
import sys
from pathlib import Path

_AGENT_APP_DIR = Path(__file__).resolve().parents[4] / "agent"

_graph = None


class AgentUnavailableError(Exception):
    """El copiloto no está disponible en este entorno - dependencias de
    apps/agent no instaladas, o el proveedor configurado (Ollama local,
    o Groq/Gemini en prod) no responde. Se traduce a un 503 en el
    router."""


def _ensure_agent_importable() -> None:
    if str(_AGENT_APP_DIR) not in sys.path:
        sys.path.insert(0, str(_AGENT_APP_DIR))


def _get_graph():
    global _graph
    if _graph is None:
        _ensure_agent_importable()
        try:
            from agent.graph import build_graph
        except ImportError as e:
            raise AgentUnavailableError(
                f"el copiloto no está disponible en este entorno: {e}"
            )
        _graph = build_graph()
    return _graph


def invalidate_rag_index() -> None:
    """Mejor esfuerzo, nunca debe romper un create/update/delete de regla
    dinámica (ver api/rules/service.py) - si el copiloto no está
    configurado en este entorno, o su índice RAG ni se ha construido
    todavía, esto simplemente no hace nada. No reconstruye de una vez,
    solo marca el índice como desactualizado para la próxima pregunta
    real que use search_rule_docs (ver agent/rag/retrieve.py)."""
    try:
        _ensure_agent_importable()
        from agent.rag.retrieve import invalidate_index

        invalidate_index()
    except Exception:
        pass


def ask(question: str, session_id: str | None = None) -> dict:
    graph = _get_graph()

    # Import diferido, no a nivel de módulo: langchain_core no está en las
    # dependencias del backend a propósito (ver docstring del módulo) -
    # un import top-level acá tumbaba el arranque de TODO el backend en
    # Render (ModuleNotFoundError en el import de main.py), no solo este
    # endpoint. Para cuando _get_graph() ya construyó el grafo,
    # langchain_core ya está garantizado disponible (es dependencia
    # transitiva de agent.graph), así que esto nunca falla en la práctica.
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from agent import context

    # Contexto ambiental, no un parámetro de la tool (ver agent/context.py
    # para el porqué) - las tools que resuelven "el dataset más reciente"
    # (tools.py:_resolve_dataset_id) lo leen para saber de qué sesión de
    # verdad están hablando, en vez de caer siempre en el cajón
    # "anonymous" del backend. `reset()` en el finally: este `ask()`
    # corre en un hilo del threadpool que Starlette puede reusar para
    # otra request después - sin resetear, una pregunta sin sesión
    # heredaría la del último que sí mandó una.
    token = context.session_id.set(session_id)
    try:
        state = {"messages": [HumanMessage(content=question)], "step_count": 0}
        result = graph.invoke(state)
    except Exception as e:
        raise AgentUnavailableError(
            f"el copiloto no pudo responder - revisa que el LLM configurado "
            f"(Ollama local, o Groq/Gemini en prod) esté disponible: {e}"
        )
    finally:
        context.session_id.reset(token)

    messages = result["messages"]
    tool_calls = []
    for i, msg in enumerate(messages):
        if not (isinstance(msg, AIMessage) and msg.tool_calls):
            continue
        for call in msg.tool_calls:
            tool_result = next(
                (
                    m.content
                    for m in messages[i + 1:]
                    if isinstance(m, ToolMessage) and m.tool_call_id == call["id"]
                ),
                None,
            )
            tool_calls.append(
                {"name": call["name"], "args": call["args"], "result": _truncate(tool_result)}
            )

    final = messages[-1]
    answer = final.content if isinstance(final.content, str) else str(final.content)
    return {"answer": answer, "tool_calls": tool_calls}


def _truncate(value, limit: int = 800) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"
