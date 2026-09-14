"""MCP server exposing the same tools the LangGraph agent uses
(agent/tools.py) - one definition, two consumers (docs/copilot-spec.md
Fase 4). Doesn't redefine any tool: registers the exact same functions
already wired into graph.py, just under the MCP protocol instead of
LangGraph's. If a tool's behavior changes in tools.py, both consumers
see the change automatically - nothing to keep in sync by hand.

Run as a local MCP server (stdio transport, for a local MCP client like
Claude Desktop or Claude Code - see apps/agent/README.md for exact setup):

    python -m agent.mcp_server

Requires the backend running (same as the LangGraph agent) - the tools
themselves are unchanged, still HTTP calls to apps/backend.
"""

from mcp.server.mcpserver import MCPServer

from agent.tools import TOOLS

mcp = MCPServer(
    name="auditlake-copilot",
    version="0.1.0",
    instructions=(
        "Tools over AuditLake's retail invoice audit pipeline: rule "
        "definitions (built-in and user-defined), real gold-table "
        "results, per-invoice explanations, live single-rule "
        "re-evaluation, and semantic search over rule descriptions. "
        "Every factual claim about a rule or an invoice must come from "
        "a tool call - never guess one."
    ),
)

for _tool in TOOLS:
    mcp.add_tool(_tool.func, name=_tool.name, description=_tool.description)


if __name__ == "__main__":
    mcp.run()
