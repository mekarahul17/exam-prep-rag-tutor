"""
MCP server entrypoint.

Registers every tool from mcp_server/tools/ and serves them over stdio so
any MCP-compatible client (Claude Desktop, a custom client, etc.) can
connect and call them.

Run directly with: python -m mcp_server.server
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from common.config import configure_logging
from mcp_server.tools.explain_diagram import explain_diagram
from mcp_server.tools.generate_practice_set import generate_practice_set
from mcp_server.tools.read_handwritten_note import read_handwritten_note
from mcp_server.tools.search_curriculum import search_curriculum
from mcp_server.tools.search_past_papers import search_past_papers
from mcp_server.tools.student_profile import (
    get_student_profile,
    log_interaction,
)
from personalization_layer.database import init_db


configure_logging()
init_db()

mcp = FastMCP("exam-prep-rag-tutor")

mcp.tool()(search_curriculum)
mcp.tool()(search_past_papers)
mcp.tool()(explain_diagram)
mcp.tool()(read_handwritten_note)
mcp.tool()(get_student_profile)
mcp.tool()(log_interaction)
mcp.tool()(generate_practice_set)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")