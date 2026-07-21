"""Example plugin adapter for Swiggy Food MCP server (placeholder)."""


def register(config: dict | None = None):
    print("food plugin: registered (placeholder)")


def handle_task(task: dict) -> dict:
    return {"status": "ok", "task": task, "result": "handled by food plugin"}
