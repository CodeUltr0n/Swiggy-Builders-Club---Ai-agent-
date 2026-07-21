"""MCP client adapters for Swiggy MCP servers with example integration.

The client reads config from a dict or config/servers.yaml and supports safe mocked
responses when real API credentials are not provided (useful for development).
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import yaml

try:
    import requests
except Exception:  # pragma: no cover - requests may not be available in some test envs
    requests = None  # type: ignore


DEFAULT_CONFIG_PATH = os.path.join("config", "servers.yaml")


class MCPClient:
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None) -> None:
        self._config = config or {}
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        if not config and os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception:
                self._config = {}

    def get_server_config(self, name: str) -> Dict[str, Any]:
        servers = self._config.get("servers") if isinstance(self._config, dict) else None
        if not servers:
            return {}
        return servers.get(name, {}) or {}

    def _has_valid_key(self, cfg: Dict[str, Any]) -> bool:
        key = cfg.get("api_key")
        return bool(key) and "REPLACE" not in str(key).upper()

    def request(self, server_name: str, path: str = "", method: str = "GET", params: Optional[Dict[str, Any]] = None, json: Optional[Any] = None) -> Dict[str, Any]:
        cfg = self.get_server_config(server_name)
        url_base = cfg.get("url")

        # If no config or missing credentials, return a safe mocked response for development
        if not url_base or not self._has_valid_key(cfg):
            return {
                "mock": True,
                "server": server_name,
                "path": path,
                "params": params,
                "json": json,
                "note": "No API key or server URL configured — this is a mocked response for local development.",
            }

        # Make a real HTTP request when possible
        headers = {"Authorization": f"Bearer {cfg.get('api_key')}"}
        url = url_base.rstrip("/") + "/" + path.lstrip("/")

        if requests is None:
            return {"error": "requests library not available"}

        try:
            resp = requests.request(method, url, params=params, json=json, headers=headers, timeout=5)
            try:
                data = resp.json()
            except Exception:
                data = {"text": resp.text}
            return {"status_code": resp.status_code, "data": data}
        except Exception as exc:
            return {"error": str(exc)}

    # Example convenience method
    def search_restaurants(self, query: str, server_name: str = "food") -> Dict[str, Any]:
        return self.request(server_name, path="search", params={"q": query})
