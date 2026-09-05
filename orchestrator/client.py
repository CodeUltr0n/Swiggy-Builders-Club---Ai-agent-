import asyncio
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

        # Always route through the plugin so local tools (SQLite) can be intercepted
        real_client = getattr(self, "real_mcp_client", None)
        return await plugin.execute_tool(tool_name, arguments, self.env_mode, real_client)

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


# ================================================================
#  Real MCP Client — Streamable HTTP (JSON-RPC 2.0)
# ================================================================
#
# MCPClient connects to the actual Swiggy MCP servers over HTTP.
# SwiggyMCPClient (above) is kept for CLI simulation mode.
#
# Protocol:
#   - POST to server URL with JSON-RPC 2.0 body
#   - Bearer token auth (from SwiggyOAuthClient)
#   - Session management via Mcp-Session-Id header
#   - Initialize handshake before tool calls
#
# Server URLs (from Swiggy docs):
#   https://mcp.swiggy.com/servers/food
#   https://mcp.swiggy.com/servers/instamart
#   https://mcp.swiggy.com/servers/dineout
#
# One OAuth token works across all three servers.


class MCPError(Exception):
    """Error returned by the MCP server (JSON-RPC error object)."""
    def __init__(self, code: int, message: str, server: str = ""):
        self.code = code
        self.message = message
        self.server = server
        super().__init__(f"MCP Error [{server}] code={code}: {message}")


class MCPConnectionError(Exception):
    """Failed to connect to an MCP server."""
    pass


class MCPClient:
    """
    Streamable HTTP MCP client for Swiggy servers.

    Usage:
        client = MCPClient(
            oauth_client=oauth_client,
            server_urls={
                "food": "https://mcp.swiggy.com/servers/food",
                "instamart": "https://mcp.swiggy.com/servers/instamart",
                "dineout": "https://mcp.swiggy.com/servers/dineout",
            },
        )

        await client.initialize_all()
        result = await client.call_tool("food", "search_restaurants", {"query": "biryani"})
    """

    DEFAULT_SERVERS = {
        "food": "https://mcp.swiggy.com/food",
        "instamart": "https://mcp.swiggy.com/im",
        "dineout": "https://mcp.swiggy.com/dineout",
    }

    _request_id = 0

    def __init__(
        self,
        oauth_client,
        server_urls: Optional[Dict[str, str]] = None,
        memory_manager=None,
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        self.oauth_client = oauth_client
        self.server_urls = server_urls or self.DEFAULT_SERVERS
        self.memory = memory_manager
        self.timeout = timeout
        self.max_retries = max_retries

        self._sessions: Dict[str, Dict[str, Any]] = {
            name: {
                "session_id": None,
                "initialized": False,
                "capabilities": {},
                "tools_cache": None,
            }
            for name in self.server_urls
        }

        self._http: Optional[httpx.AsyncClient] = None

    # ---- HTTP Client ----

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    # ---- Auth Headers ----

    def _get_headers(self, server_name: str = "") -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        try:
            auth_headers = self.oauth_client.get_auth_headers()
            headers.update(auth_headers)
        except RuntimeError:
            logger.error("No valid OAuth token available")
            raise

        session_id = self._sessions.get(server_name, {}).get("session_id")
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        return headers

    # ---- JSON-RPC 2.0 Transport ----

    def _next_id(self) -> int:
        MCPClient._request_id += 1
        return MCPClient._request_id

    async def _jsonrpc(
        self,
        server_name: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a JSON-RPC 2.0 request with retry logic."""
        server_url = self.server_urls.get(server_name)
        if not server_url:
            raise MCPConnectionError(f"Unknown server: {server_name}")

        payload = {"jsonrpc": "2.0", "id": self._next_id(), "method": method}
        if params is not None:
            payload["params"] = params

        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                headers = self._get_headers(server_name)
                client = await self._get_http_client()

                logger.debug(f"MCP → [{server_name}] {method} (attempt {attempt + 1})")
                resp = await client.post(server_url, json=payload, headers=headers)

                if resp.status_code == 401:
                    raise MCPError(code=401, message="Token expired. Re-authentication required.", server=server_name)

                if resp.status_code >= 500:
                    last_error = f"Server error {resp.status_code}"
                    logger.warning(f"MCP [{server_name}] {resp.status_code} (attempt {attempt + 1}/{self.max_retries + 1})")
                    if attempt < self.max_retries:
                        await self._backoff(attempt)
                        continue

                if resp.status_code != 200:
                    raise MCPConnectionError(f"HTTP {resp.status_code} from {server_name}: {resp.text[:500]}")

                data = resp.json()
                if "error" in data:
                    err = data["error"]
                    raise MCPError(code=err.get("code", -1), message=err.get("message", "Unknown MCP error"), server=server_name)

                session_header = resp.headers.get("mcp-session-id")
                if session_header and server_name in self._sessions:
                    self._sessions[server_name]["session_id"] = session_header

                return data.get("result", {})

            except httpx.TimeoutException:
                last_error = f"Timeout after {self.timeout}s"
                logger.warning(f"MCP [{server_name}] timeout (attempt {attempt + 1}/{self.max_retries + 1})")
                if attempt < self.max_retries:
                    await self._backoff(attempt)
                    continue

            except httpx.ConnectError as e:
                last_error = f"Connection failed: {e}"
                logger.error(f"MCP [{server_name}] connection error: {e}")
                if attempt < self.max_retries:
                    await self._backoff(attempt + 1)
                    continue

        raise MCPConnectionError(
            f"Failed to reach {server_name} after {self.max_retries + 1} attempts. Last error: {last_error}"
        )

    @staticmethod
    async def _backoff(attempt: int, base: float = 1.0):
        delay = base * (2 ** attempt) + 0.1 * attempt
        await asyncio.sleep(min(delay, 10.0))

    # ---- MCP Protocol — Initialize ----

    async def initialize(self, server_name: str) -> Dict[str, Any]:
        logger.info(f"MCP [{server_name}] Initializing session...")

        init_result = await self._jsonrpc(server_name, "initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {"client": {"tools": {}, "resources": {}}},
            "clientInfo": {"name": "Swiggy MCP Orchestrator", "version": "1.0.0"},
        })

        self._sessions[server_name]["initialized"] = True
        self._sessions[server_name]["capabilities"] = init_result.get("capabilities", {})

        # Send initialized notification (no response expected)
        try:
            headers = self._get_headers(server_name)
            client = await self._get_http_client()
            await client.post(
                self.server_urls[server_name],
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers=headers,
            )
        except Exception as e:
            logger.warning(f"Failed to send initialized notification: {e}")

        logger.info(f"MCP [{server_name}] Initialized. Capabilities: {list(self._sessions[server_name]['capabilities'].keys())}")
        return init_result

    async def initialize_all(self) -> Dict[str, bool]:
        results = {}
        for server_name in self.server_urls:
            try:
                await self.initialize(server_name)
                results[server_name] = True
            except Exception as e:
                logger.error(f"MCP [{server_name}] Init failed: {e}")
                results[server_name] = False
        return results

    # ---- MCP Protocol — Tools ----

    async def list_tools(self, server_name: str) -> list:
        cached = self._sessions[server_name].get("tools_cache")
        if cached is not None:
            return cached

        if not self._sessions[server_name]["initialized"]:
            await self.initialize(server_name)

        result = await self._jsonrpc(server_name, "tools/list", {})
        tools = result.get("tools", [])
        self._sessions[server_name]["tools_cache"] = tools
        logger.info(f"MCP [{server_name}] {len(tools)} tools available")
        return tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Call a tool on an MCP server.

        Returns same format as SwiggyMCPClient for compatibility:
            {"success": True/False, "data": {...}, "error": "..."}
        """
        if not self._sessions.get(server_name, {}).get("initialized"):
            try:
                await self.initialize(server_name)
            except Exception as e:
                return {"success": False, "error": f"Failed to initialize {server_name}: {e}", "tool_name": tool_name, "server": server_name}

        logger.info(f"MCP [{server_name}] Calling tool: {tool_name}")

        try:
            result = await self._jsonrpc(server_name, "tools/call", {
                "name": tool_name,
                "arguments": arguments,
            })

            logger.info(f"MCP [{server_name}] Raw result type: {type(result).__name__}, keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")

            content = result.get("content", []) if isinstance(result, dict) else result
            parsed_data = self._parse_mcp_content(content)

            logger.info(f"MCP [{server_name}] Parsed data type: {type(parsed_data).__name__}, preview: {str(parsed_data)[:300]}")

            # If the parsed data is itself a Swiggy {success, data} envelope, return it directly
            # Otherwise wrap it in our standard format
            if isinstance(parsed_data, dict) and "success" in parsed_data:
                parsed_data["tool_name"] = tool_name
                parsed_data["server"] = server_name
                parsed_data["raw_content"] = content
                return parsed_data

            return {"success": True, "data": parsed_data, "raw_content": content, "tool_name": tool_name, "server": server_name}

        except MCPError as e:
            return {"success": False, "error": e.message, "error_code": e.code, "tool_name": tool_name, "server": server_name}
        except MCPConnectionError as e:
            return {"success": False, "error": str(e), "tool_name": tool_name, "server": server_name}
        except Exception as e:
            logger.error(f"MCP [{server_name}] Unexpected error calling {tool_name}: {e}")
            return {"success": False, "error": f"Unexpected error: {e}", "tool_name": tool_name, "server": server_name}

    # ---- Helpers ----

    def get_status(self) -> Dict[str, Any]:
        status = {}
        for name in self.server_urls:
            session = self._sessions[name]
            status[name] = {
                "url": self.server_urls[name],
                "initialized": session["initialized"],
                "session_id": session["session_id"],
                "tools_count": len(session["tools_cache"]) if session["tools_cache"] else None,
            }
        return status

    def reset_session(self, server_name: str = None):
        targets = [server_name] if server_name else list(self._sessions.keys())
        for name in targets:
            if name in self._sessions:
                self._sessions[name] = {"session_id": None, "initialized": False, "capabilities": {}, "tools_cache": None}
        logger.info(f"Session reset: {server_name or 'all servers'}")

    @staticmethod
    def _parse_mcp_content(content) -> Any:
        """Parse MCP content into usable data.

        Handles multiple formats:
        - list of {"type": "text", "text": "..."} dicts (standard MCP)
        - list of plain strings
        - a single string
        - a dict (already parsed)
        """
        if content is None:
            return {}

        # Already a dict — return as-is
        if isinstance(content, dict):
            return content

        # Single string — try JSON parse
        if isinstance(content, str):
            try:
                import json as _json
                return _json.loads(content)
            except Exception:
                return content

        # List
        if isinstance(content, list):
            if not content:
                return {}

            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    text_parts.append(item.get("text", str(item)))
                elif isinstance(item, str):
                    text_parts.append(item)
                else:
                    text_parts.append(str(item))

            combined = "\n".join(text_parts)

            try:
                import json as _json
                return _json.loads(combined)
            except Exception:
                pass

            return text_parts[0] if len(text_parts) == 1 else combined

        # Fallback
        return content

