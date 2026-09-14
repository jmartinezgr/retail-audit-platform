"""mcp_server.py no redefine tools, solo registra las mismas funciones de
tools.py bajo el protocolo MCP - esta prueba confirma que el registro
incluye las 6, con nombre y descripción reales (no que MCP en sí
funcione end-to-end, eso ya se verificó a mano con un cliente MCP real,
ver apps/agent/README.md)."""

import asyncio

from agent import mcp_server, tools


def test_all_tools_are_registered_under_their_real_names_and_descriptions():
    registered = asyncio.run(mcp_server.mcp.list_tools())
    registered_by_name = {t.name: t for t in registered}

    assert set(registered_by_name) == {t.name for t in tools.TOOLS}
    for tool in tools.TOOLS:
        assert registered_by_name[tool.name].description == tool.description
