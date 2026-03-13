"""Entry point for running brain-mcp as a module: python -m brain_mcp."""

from brain_mcp.server import mcp

if __name__ == "__main__":
    mcp.run()
