"""LangGraph state graph - the orchestrator. Nodes: `agent` (the LLM,
tools bound) and `tools` (executes whatever the LLM asked for). The
graph bounces `agent -> tools -> agent -> ...` until the LLM answers
without asking for another tool call, or until `settings.MAX_STEPS` is
hit - at which point `finalize` forces one last answer instead of
letting the loop continue (see docs/copilot-spec.md, restriction #4).
"""

from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from agent.settings import settings
from agent.state import AgentState
from agent.tools import TOOLS

SYSTEM_PROMPT = SystemMessage(content="""\
You are AuditLake's copilot. You answer questions about a retail invoice \
audit pipeline - which rules exist, what they check, and what actually \
happened to real invoices in a given run.

Hard rule: you never compute or guess an audit result yourself. Every \
factual claim about a rule's definition or an invoice's outcome must come \
from a tool call. If a tool returns an error or you can't back a claim \
with a tool result, say plainly that you don't know or couldn't check - \
never fill the gap with a plausible-sounding guess.

If a tool result includes a pre-counted field (anything named like \
"resumen", "total_*", or "count") always use that number exactly as \
given. Never state a different count of your own by re-scanning a list \
- if you do this, double-check it actually matches before writing it \
down.""")

_llm = ChatOllama(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL, temperature=0)
_llm_with_tools = _llm.bind_tools(TOOLS)


def agent_node(state: AgentState) -> dict:
    messages = state["messages"]
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SYSTEM_PROMPT, *messages]
    response = _llm_with_tools.invoke(messages)
    return {"messages": [response], "step_count": state["step_count"] + 1}


def finalize_node(state: AgentState) -> dict:
    """Se llama solo cuando se llegó a MAX_STEPS con la última respuesta
    del LLM todavía pidiendo otra tool call - sin esto, el grafo
    terminaría en un AIMessage vacío (solo tool_calls, sin texto). Se
    corre el modelo una vez más, sin tools, forzado a resumir en texto
    lo que ya se sabe."""
    nudge = SystemMessage(
        content=(
            "You've reached the step limit for this question. Do not request "
            "any more tool calls. Answer now, in plain text, using only what "
            "the tool results above already told you. If that's not enough "
            "to fully answer, say what you found and what's still unknown."
        )
    )
    response = _llm.invoke([*state["messages"], nudge])
    return {"messages": [response]}


def route_after_agent(state: AgentState) -> Literal["tools", "finalize", "__end__"]:
    last = state["messages"][-1]
    has_tool_calls = isinstance(last, AIMessage) and bool(last.tool_calls)
    if not has_tool_calls:
        return "__end__"
    if state["step_count"] >= settings.MAX_STEPS:
        return "finalize"
    return "tools"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "finalize": "finalize", "__end__": END},
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("finalize", END)

    return graph.compile()
