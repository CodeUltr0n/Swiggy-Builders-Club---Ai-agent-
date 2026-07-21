"""Simple router placeholder to choose a server/plugin for a task."""
from typing import Dict, Any


class Router:
    def __init__(self):
        self.plugins = {}

    def register(self, name: str, plugin) -> None:
        self.plugins[name] = plugin

    def route(self, task: Dict[str, Any]) -> str:
        # Naive routing: choose plugin name declared in task or 'food' fallback
        return task.get("preferred_server", "food")
