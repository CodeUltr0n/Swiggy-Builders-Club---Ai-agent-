import os
import yaml
import httpx
import logging
from typing import Dict, Any, Optional
from orchestrator.memory import MemoryManager
from orchestrator.plugins.food import FoodPlugin
from orchestrator.plugins.instamart import InstamartPlugin
from orchestrator.plugins.dineout import DineoutPlugin

logger = logging.getLogger(__name__)

class SwiggyMCPClient:
    def __init__(self, memory_manager: MemoryManager, config_dir: str = "config"):
        self.memory = memory_manager
        self.config_dir = config_dir
        self.load_configs()
        
        # Initialize plugins
        self.plugins = {
            "food": FoodPlugin(self.memory),
            "instamart": InstamartPlugin(self.memory),
            "dineout": DineoutPlugin(self.memory)
        }
        
        # Session tokens
        self.access_tokens = {}

    def load_configs(self):
        # Load servers config
        servers_path = os.path.join(self.config_dir, "servers.yaml")
        if os.path.exists(servers_path):
            with open(servers_path, "r") as f:
                self.servers_config = yaml.safe_load(f).get("servers", {})
        else:
            self.servers_config = {}

        # Load settings
        settings_path = os.path.join(self.config_dir, "settings.yaml")
        if os.path.exists(settings_path):
            with open(settings_path, "r") as f:
                self.settings = yaml.safe_load(f).get("settings", {})
        else:
            self.settings = {}

        self.env_mode = self.settings.get("env_mode", "simulation")

    async def get_access_token(self, server_name: str) -> str:
        """
        Retrieves or refreshes the OAuth 2.1 access token for a given server.
        """
        # If in simulation mode, return a mock token
        if self.env_mode == "simulation":
            return "mock_token_12345"

        # Check in-memory cache
        if server_name in self.access_tokens:
            return self.access_tokens[server_name]

        # Check SQLite for OAuth token (shared across all servers, stored by oauth.py)
        stored_token = self.memory.get_preference("swiggy_access_token")
        stored_expiry = self.memory.get_preference("swiggy_token_expires_at")
        if stored_token and stored_expiry:
            import time
            if time.time() < float(stored_expiry):
                self.access_tokens[server_name] = stored_token
                return stored_token
            else:
                logger.warning(f"OAuth token in SQLite is expired for '{server_name}'. Re-auth required.")

        # Fallback: check env vars
        env_token = os.environ.get(f"SWIGGY_{server_name.upper()}_TOKEN")
        if env_token:
            self.access_tokens[server_name] = env_token
            return env_token

        # Fallback to general Swiggy Token
        general_token = os.environ.get("SWIGGY_TOKEN")
        if general_token:
            self.access_tokens[server_name] = general_token
            return general_token

        # If no token is configured, raise an error indicating authentication required
        raise ValueError(
            f"Authentication token required for server '{server_name}'. "
            f"Please run the OAuth flow or set SWIGGY_{server_name.upper()}_TOKEN in your environment."
        )

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes the tool execution request to either the local simulation plugin
        or the real staging/production MCP server.
        """
        plugin = self.plugins.get(server_name)
        if not plugin:
            return {"success": False, "error": f"Server plugin '{server_name}' not registered"}

        if self.env_mode == "simulation":
            return await plugin.execute_tool(tool_name, arguments, "simulation")
        else:
            return await self.call_real_server(server_name, tool_name, arguments)

    async def call_real_server(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs the JSON-RPC call over streamable HTTP/SSE to the real staging/prod server.
        """
        config = self.servers_config.get(server_name)
        if not config:
            return {"success": False, "error": f"Configuration for server '{server_name}' not found"}

        url = config.get("production_url") if self.env_mode == "production" else config.get("staging_url")
        if not url:
            return {"success": False, "error": f"URL for server '{server_name}' under mode '{self.env_mode}' is not configured"}

        try:
            token = await self.get_access_token(server_name)
        except ValueError as e:
            return {"success": False, "error": str(e), "status": 401}

        # Structure the request as a JSON-RPC 2.0 call
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": f"tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 401:
                    # Token expired/invalid, clear it from memory and return 401 status so caller can trigger re-auth
                    if server_name in self.access_tokens:
                        del self.access_tokens[server_name]
                    return {
                        "success": False,
                        "error": "Unauthorized: Access token expired or invalid",
                        "status": 401
                    }

                response.raise_for_status()
                result = response.json()
                
                if "error" in result:
                    return {
                        "success": False,
                        "error": result["error"].get("message", "JSON-RPC Error"),
                        "code": result["error"].get("code")
                    }
                
                # Check for standard tool output content structure
                result_content = result.get("result", {}).get("content", [])
                if result_content and isinstance(result_content, list):
                    # Usually returns text content
                    text_out = result_content[0].get("text", "")
                    # Try to parse as JSON data if possible, or return raw text
                    try:
                        import json
                        parsed_data = json.loads(text_out)
                        return {"success": True, "data": parsed_data}
                    except json.JSONDecodeError:
                        return {"success": True, "raw_data": text_out}

                return {"success": True, "data": result.get("result", {})}

        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP error {e.response.status_code}: {e.response.text}",
                "status": e.response.status_code
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection error: {str(e)}"
            }
