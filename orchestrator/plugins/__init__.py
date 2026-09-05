from typing import Dict, Any, List, Optional
import os
import logging

logger = logging.getLogger(__name__)

class BasePlugin:
    def __init__(self, name: str, memory_manager):
        self.name = name
        self.memory = memory_manager
        # Simulated states for local testing
        self.simulated_cart: Dict[str, Any] = self._initial_cart_state()
        self.simulated_orders: List[Dict[str, Any]] = []

    def _initial_cart_state(self) -> Dict[str, Any]:
        return {"items": [], "total": 0.0, "applied_coupon": None, "restaurant_id": None}

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], mode: str, real_client=None) -> Dict[str, Any]:
        """
        Executes a tool. If mode is simulation, routes to local simulation handler.
        Otherwise, routes to real Swiggy MCP server via the real_client.
        """
        if mode == "simulation":
            sim_handler = getattr(self, f"sim_{tool_name}", None)
            if sim_handler:
                try:
                    return await sim_handler(arguments)
                except Exception as e:
                    return {"success": False, "error": str(e)}
            return {"success": False, "error": f"Tool '{tool_name}' not implemented in simulation mode"}
        else:
            if not real_client:
                raise ValueError(f"Real client connection missing for executing {tool_name}")

            # Execute against real MCP server - NO mock fallback
            return await real_client.call_tool(self.name, tool_name, arguments)
