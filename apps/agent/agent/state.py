from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """Estado que viaja entre nodos del grafo.

    `messages`: historial completo (humano, IA, y resultados de tools) -
    `add_messages` es el reducer de LangGraph que anexa en vez de
    reemplazar en cada actualización de estado.

    `step_count`: cuántas veces pasó por el nodo "agent" en este run -
    lo usa la condición de enrutamiento para forzar una respuesta parcial
    en vez de loopear indefinidamente (ver settings.MAX_STEPS).
    """

    messages: Annotated[list[AnyMessage], add_messages]
    step_count: int
