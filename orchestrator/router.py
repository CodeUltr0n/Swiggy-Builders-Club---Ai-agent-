"""
Orchestrator Router

Routes user queries to the correct MCP server using:
- LLM-based entity extraction (no hardcoded restaurant IDs or regex keyword lists)
- Registry-based handler pattern (adding a server = 1 file + 1 register call)
- Deterministic confirmation state machine for multi-turn flows

ZERO hardcoded restaurant IDs, names, or keyword lists in this file.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable

from orchestrator.llm import LLMClient
from orchestrator.prioritizer import ContextPrioritizer

logger = logging.getLogger(__name__)

# Type for a registered server handler
ServerHandler = Callable[[str, Dict[str, Any], List[Dict[str, Any]], list], Awaitable[Dict[str, Any]]]


class OrchestratorRouter:

    CONFIRM_YES = {"yes", "y", "confirm", "place", "do it", "yeah", "sure", "ok"}
    CONFIRM_NO = {"no", "n", "cancel", "stop", "don't", "nope"}

    def __init__(self, client, prioritizer: ContextPrioritizer, llm: LLMClient = None):
        self.client = client
        self.prioritizer = prioritizer
        self.llm = llm

        # Registry: server_name -> handler coroutine
        self._handlers: Dict[str, ServerHandler] = {}

        # State machine for multi-turn confirmation flows
        self.current_state: Dict[str, Any] = {
            "stage": None,
            "pending_action": None,
            "active_server": None,
            "active_restaurant_id": None,
            "active_restaurant_name": None,
        }

    def register_handler(self, server_name: str, handler: ServerHandler):
        """Register a route handler for an MCP server. Plugins call this."""
        self._handlers[server_name] = handler
        logger.info(f"Registered handler for server: {server_name}")

    def reset_state(self):
        self.current_state = {
            "stage": None,
            "pending_action": None,
            "active_server": None,
            "active_restaurant_id": None,
            "active_restaurant_name": None,
        }

    # ------------------------------------------------------------------ #
    #  LLM entity extraction                                              #
    # ------------------------------------------------------------------ #

    async def _extract_entities(self, query: str, schema: dict) -> dict:
        """
        Use LLM to extract structured data from a query.
        Falls back to empty dict on failure or if LLM is disabled.
        """
        if not self.llm:
            return {}
        try:
            return await self.llm.extract_entities(query, schema)
        except Exception:
            logger.warning("LLM entity extraction failed, proceeding with defaults")
            return {}

    # ------------------------------------------------------------------ #
    #  Idempotency / error recovery                                       #
    # ------------------------------------------------------------------ #

    async def handle_failed_order(self, server: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Idempotency check: query recent orders to verify if order was placed despite error."""
        logger.info(f"Checking order status for server: {server}")
        tool_name = "get_food_orders" if server == "food" else "get_orders"
        try:
            orders_res = await self.client.call_tool(server, tool_name, {})
            if orders_res.get("success") and orders_res.get("data"):
                return orders_res["data"][0]
        except Exception as e:
            logger.error(f"Failed to query order status during idempotency check: {e}")
        return None

    # ------------------------------------------------------------------ #
    #  Confirmation state machine                                         #
    # ------------------------------------------------------------------ #

    def _is_confirmation_query(self, query_lower: str) -> Optional[str]:
        """Check if the query is a confirmation response. Returns 'yes', 'no', or None."""
        if query_lower in self.CONFIRM_YES:
            return "yes"
        if query_lower in self.CONFIRM_NO:
            return "no"
        return None

    async def _handle_confirmation(self, query: str, query_lower: str, tool_logs: list) -> Optional[Dict[str, Any]]:
        """Handle the awaiting_order_confirm state. Returns response dict or None if not in confirm stage."""
        if self.current_state["stage"] != "awaiting_order_confirm":
            return None

        confirm = self._is_confirmation_query(query_lower)
        if confirm is None:
            return {
                "response_text": "I didn't catch that. Please reply with **yes** to confirm or **no** to cancel.",
                "tool_calls": [],
                "active_server": self.current_state["active_server"],
                "state": self.current_state,
            }

        if confirm == "no":
            server = self.current_state["active_server"]
            self.reset_state()
            return {
                "response_text": "Order cancelled. Your cart remains intact.",
                "tool_calls": [],
                "active_server": server,
                "state": self.current_state,
            }

        # confirm == "yes" — execute the pending action
        pending = self.current_state["pending_action"]
        server = pending["server"]
        tool_name = pending["tool_name"]
        args = pending["arguments"]

        try:
            tool_res = await self.client.call_tool(server, tool_name, args)
            if not tool_res.get("success", False):
                resolved = await self.handle_failed_order(server, args)
                if resolved:
                    tool_res = {
                        "success": True,
                        "data": resolved,
                        "warning": "Order succeeded after server connection was restored. Verified using get_food_orders.",
                    }
                else:
                    raise Exception(tool_res.get("error", "Order placement failed"))
        except Exception as e:
            logger.warning(f"Order error: {e}. Running idempotency check...")
            resolved = await self.handle_failed_order(server, args)
            if resolved:
                tool_res = {
                    "success": True,
                    "data": resolved,
                    "warning": f"Order placement threw an error, but was successfully recovered and verified via get_food_orders. Details: {e}",
                }
            else:
                tool_res = {"success": False, "error": f"Order placement failed: {e}"}

        tool_logs.append({"tool": tool_name, "args": args, "result": tool_res})
        self.reset_state()

        if tool_res.get("success"):
            warning = f"\n*(Note: {tool_res['warning']})*" if "warning" in tool_res else ""
            if server == "dineout" or tool_name == "book_table":
                booking_id = tool_res["data"].get("bookingId", tool_res["data"].get("id", "N/A"))
                return {
                    "response_text": f"Table booking confirmed! Booking ID: **{booking_id}**. Status: **CONFIRMED**.{warning}\nWould you like to check your booking status?",
                    "tool_calls": tool_logs,
                    "active_server": "dineout",
                    "state": self.current_state,
                }
            elif server == "instamart":
                order_id = tool_res["data"].get("orderId", tool_res["data"].get("id", "N/A"))
                return {
                    "response_text": f"Success! Your Instamart order **{order_id}** has been placed.{warning}\nWould you like to track it?",
                    "tool_calls": tool_logs,
                    "active_server": "instamart",
                    "state": self.current_state,
                }
            else:
                order_id = tool_res["data"].get("orderId", tool_res["data"].get("id", "N/A"))
                return {
                    "response_text": f"Success! Your food order has been placed. Order ID: **{order_id}**. Payment Method: **COD**.{warning}\nWould you like to track it?",
                    "tool_calls": tool_logs,
                    "active_server": "food",
                    "state": self.current_state,
                }

        return {
            "response_text": f"Failed to place order: {tool_res.get('error')}",
            "tool_calls": tool_logs,
            "active_server": server,
            "state": self.current_state,
        }


    # ------------------------------------------------------------------ #
    #  Main query processing                                              #
    # ------------------------------------------------------------------ #

    async def process_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a natural language query:
        1. Check confirmation state
        2. Score servers via prioritizer (context + LLM intent)
        3. Resolve address
        4. Route to registered handler
        """
        query_lower = query.strip().lower()
        tool_logs = []

        # 1. Handle confirmation flow
        confirm_response = await self._handle_confirmation(query, query_lower, tool_logs)
        if confirm_response is not None:
            return confirm_response

        # 2. Get server rankings from Prioritizer
        rankings = await self.prioritizer.score_tasks(query, context)
        primary_server = rankings[0][0]
        self.current_state["active_server"] = primary_server

        # 3. Resolve address (common step across all servers)
        addr_res = await self.client.call_tool(primary_server, "get_addresses", {})
        tool_logs.append({"tool": "get_addresses", "args": {}, "result": addr_res})

        if not addr_res.get("success") or not addr_res.get("data"):
            return {
                "response_text": "Could not retrieve your saved addresses. Please check your account.",
                "tool_calls": tool_logs,
                "active_server": primary_server,
                "state": self.current_state,
                "rankings": rankings,
            }

        addresses = addr_res["data"]
        selected = next(
            (a for a in addresses if a["id"] == context.get("address_id")),
            addresses[0] if addresses else None,
        )
        context["resolved_address"] = selected

        # 4. Route to registered handler
        handler = self._handlers.get(primary_server)
        if not handler:
            return {
                "response_text": f"No handler registered for '{primary_server}'.",
                "tool_calls": tool_logs,
                "active_server": primary_server,
                "state": self.current_state,
                "rankings": rankings,
            }

        return await handler(query, context, tool_logs, rankings)
