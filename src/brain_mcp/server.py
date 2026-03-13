"""Brain MCP server entry point.

Creates and configures the FastMCP server with all tools and prompts.
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

from brain_mcp.prompts import register_prompts
from brain_mcp.tools import register_tools

# Logging — stderr only (stdio transport must keep stdout clean)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)

mcp = FastMCP(
    "brain",
    instructions=(
        "MCP server for the Brain Obsidian knowledge base. "
        "Provides tools for navigating, searching, creating, and updating notes. "
        "New notes should go to Notes/ by default and be promoted during review."
    ),
)

register_tools(mcp)
register_prompts(mcp)
