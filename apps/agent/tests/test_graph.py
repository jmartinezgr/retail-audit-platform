"""Integration test for the graph's plumbing - routing, step counting,
the tool-call loop, and the step cap. The LLM is scripted (not a real
Ollama call) and the tool's HTTP call is mocked, so this asserts on the
tool-call sequence and message shape, never on the model's actual
wording (per docs/copilot-spec.md's testing section)."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import graph as graph_module
from agent import tools


class FakeResponse:
    def __init__(self, json_data):
        self._json = json_data
        self.status_code = 200

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


def fake_get_rule_response(url, timeout=None, **kwargs):
    if url.endswith("/rules/"):
        return FakeResponse([])  # no dynamic rules match -> falls back to static
    return FakeResponse({"nombre": "sede_existe", "severidad": "ERROR"})


def test_graph_calls_tool_then_answers(monkeypatch):
    monkeypatch.setattr(tools.httpx, "get", fake_get_rule_response)

    responses = [
        AIMessage(
            content="",
            tool_calls=[{"name": "get_rule", "args": {"rule_id": "sede_existe"}, "id": "call_1", "type": "tool_call"}],
        ),
        AIMessage(content="sede_existe checks that the store code exists in the master catalog."),
    ]
    call_count = {"n": 0}

    class FakeLLM:
        def invoke(self, messages):
            response = responses[call_count["n"]]
            call_count["n"] += 1
            return response

    monkeypatch.setattr(graph_module, "_llm_with_tools", FakeLLM())

    app = graph_module.build_graph()
    result = app.invoke({"messages": [HumanMessage(content="what does sede_existe check?")], "step_count": 0})

    assert call_count["n"] == 2
    assert result["step_count"] == 2
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert result["messages"][-1].content == "sede_existe checks that the store code exists in the master catalog."


def test_graph_stops_at_step_cap_with_a_partial_answer(monkeypatch):
    """Un LLM que nunca deja de pedir tools no debe loopear para siempre -
    al llegar a MAX_STEPS, el grafo debe forzar una respuesta en texto
    vía finalize_node en vez de seguir rebotando."""
    monkeypatch.setattr(tools.httpx, "get", fake_get_rule_response)

    class FakeLLMWithTools:
        def invoke(self, messages):
            return AIMessage(
                content="",
                tool_calls=[{"name": "get_rule", "args": {"rule_id": "sede_existe"}, "id": "call_x", "type": "tool_call"}],
            )

    class FakeLLM:
        def invoke(self, messages):
            return AIMessage(content="Here's a partial answer based on what I found so far.")

    monkeypatch.setattr(graph_module, "_llm_with_tools", FakeLLMWithTools())
    monkeypatch.setattr(graph_module, "_llm", FakeLLM())
    monkeypatch.setattr(graph_module.settings, "MAX_STEPS", 3)

    app = graph_module.build_graph()
    result = app.invoke({"messages": [HumanMessage(content="loop forever")], "step_count": 0})

    assert result["step_count"] == 3
    assert result["messages"][-1].content == "Here's a partial answer based on what I found so far."
