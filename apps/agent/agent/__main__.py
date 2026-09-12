import sys

from langchain_core.messages import HumanMessage

from agent.graph import build_graph


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m agent "your question here"')
        sys.exit(1)

    question = sys.argv[1]
    graph = build_graph()
    result = graph.invoke({"messages": [HumanMessage(content=question)], "step_count": 0})
    print(result["messages"][-1].content)


if __name__ == "__main__":
    main()
