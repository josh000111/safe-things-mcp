"""FastMCP entrypoint."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .state.db import init_state_db
from .tools import confirm, meta, propose, read, undo, write


def build_server() -> FastMCP:
    init_state_db()
    mcp = FastMCP("things-mcp")
    read.register(mcp)
    write.register(mcp)
    propose.register(mcp)
    confirm.register(mcp)
    undo.register(mcp)
    meta.register(mcp)
    return mcp


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
