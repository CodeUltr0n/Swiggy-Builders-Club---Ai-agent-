"""Placeholder for MCP client connections."""

class MCPClient:
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    def connect(self) -> None:
        print("MCPClient: connect (placeholder)")

    def close(self) -> None:
        print("MCPClient: close (placeholder)")
