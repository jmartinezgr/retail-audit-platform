"""Wrapper del copiloto (apps/agent, LangGraph + Ollama) como servicio del
backend - demo local únicamente (ver apps/agent/README.md y el README
raíz): necesita Ollama y Qdrant corriendo en la máquina, algo que no
existe en el deploy de Render. Importa `agent.graph` metiendo apps/agent
al sys.path en vez de instalar apps/agent como dependencia del backend
(mismo problema que el server MCP - ver apps/agent/agent/mcp_server.py -
y misma solución), así el backend de producción no carga langgraph,
langchain-ollama, qdrant-client, etc. si nadie usa el chat. El import
real solo ocurre la primera vez que se llama a este endpoint.
"""

import json
import sys
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

_AGENT_APP_DIR = Path(__file__).resolve().parents[4] / "agent"

_graph = None


class AgentUnavailableError(Exception):
    """El copiloto local no está disponible en este entorno - o no están
    instaladas las dependencias de apps/agent, o Ollama/Qdrant no están
    corriendo. Se traduce a un 503 en el router."""


def _get_graph():
    global _graph
    if _graph is None:
        if str(_AGENT_APP_DIR) not in sys.path:
            sys.path.insert(0, str(_AGENT_APP_DIR))
        try:
            from agent.graph import build_graph
        except ImportError as e:
            raise AgentUnavailableError(
                f"el copiloto local no está disponible en este entorno: {e}"
            )
        _graph = build_graph()
    return _graph


def ask(question: str) -> dict:
    graph = _get_graph()
    state = {"messages": [HumanMessage(content=question)], "step_count": 0}
    try:
        result = graph.invoke(state)
    except Exception as e:
        raise AgentUnavailableError(
            f"el copiloto no pudo responder - ¿está Ollama corriendo? ({e})"
        )

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
