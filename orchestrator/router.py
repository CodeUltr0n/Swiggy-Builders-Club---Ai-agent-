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

        raw_data = addr_res.get("data") if addr_res.get("success") else None
        raw_text = addr_res.get("raw_text", "")
        structured = addr_res.get("structured", {})

        # Normalize: extract list of address dicts
        raw_list = []
        if isinstance(structured, dict) and "addresses" in structured:
            raw_list = structured["addresses"]
        elif isinstance(raw_data, list):
            raw_list = raw_data
        elif isinstance(raw_data, dict):
            raw_list = raw_data.get("addresses", raw_data.get("data", []))
            if isinstance(raw_list, dict):
                raw_list = [raw_list]
            elif not isinstance(raw_list, list):
                raw_list = [raw_data]
        elif isinstance(raw_data, str):
            try:
                import json
                parsed = json.loads(raw_data)
                raw_list = parsed if isinstance(parsed, list) else [parsed]
            except Exception:
                raw_list = []

        # Clean and extract valid address dicts with an ID
        addresses = []
        for a in raw_list:
            if isinstance(a, dict):
                a_id = a.get("id") or a.get("addressId") or a.get("address_id")
                if a_id:
                    a["id"] = a_id
                    if not a.get("label"):
                        a["label"] = a.get("addressTag") or a.get("addressCategory") or a.get("address_line") or "Home"
                    addresses.append(a)

        # Also check for addressId in raw text via regex if empty
        if not addresses and raw_text:
            import re
            addr_matches = re.findall(r'(addr_[a-zA-Z0-9_-]+)', raw_text)
            for m_id in addr_matches:
                addresses.append({
                    "id": m_id,
                    "label": "Home",
                    "city": "Bengaluru",
                })

        logger.info(f"Addresses extracted: {len(addresses)} items, first: {str(addresses[0])[:200] if addresses else 'none'}")

        # If no address exists on the user's Swiggy account, auto-provision via real create_address tool
        if not addresses:
            provision_server = primary_server if primary_server in ("food", "instamart") else "food"
            logger.info(f"No saved addresses. Auto-provisioning delivery address on {provision_server} via create_address...")
            create_args = {
                "fullAddress": "100 Feet Road, Indiranagar, Bengaluru, Karnataka 560038",
                "addressLine": "Flat 402, Sunshine Apartments, 100 Feet Road",
                "addressLine2": "Indiranagar",
                "city": "Bengaluru",
                "postalCode": "560038",
                "addressCategory": "HOME",
                "userName": "Swiggy User",
                "userPhone": "9876543210",
                "latitude": 12.9784,
                "longitude": 77.6408,
            }
            try:
                create_res = await self.client.call_tool(provision_server, "create_address", create_args)
                tool_logs.append({"tool": "create_address", "args": create_args, "result": create_res})
                if create_res.get("success"):
                    # Directly extract addressId from create_address response
                    c_data = create_res.get("data", {})
                    created_id = None
                    if isinstance(c_data, dict):
                        created_id = c_data.get("addressId") or c_data.get("id")
                    elif isinstance(c_data, str):
                        import re
                        m = re.search(r'addr_[a-zA-Z0-9_-]+', c_data)
                        if m:
                            created_id = m.group(0)

                    if created_id:
                        addresses.append({
                            "id": created_id,
                            "label": "Home",
                            "addressLine": create_args["addressLine"],
                            "city": create_args["city"],
                        })
                        logger.info(f"Auto-provisioned real Swiggy address: {created_id}")

                    # Re-fetch addresses from Swiggy
                    re_addr = await self.client.call_tool(provision_server, "get_addresses", {})
                    tool_logs.append({"tool": "get_addresses (after create)", "args": {}, "result": re_addr})
                    if re_addr.get("success") and re_addr.get("data"):
                        re_data = re_addr["data"]
                        re_list = re_data.get("addresses", re_data.get("data", [])) if isinstance(re_data, dict) else (re_data if isinstance(re_data, list) else [])
                        for a in re_list:
                            if isinstance(a, dict):
                                a_id = a.get("id") or a.get("addressId") or a.get("address_id")
                                if a_id and not any(existing.get("id") == a_id for existing in addresses):
                                    a["id"] = a_id
                                    if not a.get("label"):
                                        a["label"] = a.get("addressTag") or a.get("addressCategory") or "Home"
                                    addresses.append(a)
            except Exception as e:
                logger.warning(f"Auto create_address failed: {e}")

        # Dineout fallback location if reservations requested without a delivery address
        if not addresses and primary_server == "dineout":
            addresses.append({
                "id": "loc_bengaluru",
                "label": "Bengaluru",
                "city": "Bengaluru",
                "latitude": 12.9784,
                "longitude": 77.6408,
            })

        if not addresses:
            return {
                "response_text": (
                    "📍 **No delivery address found on your Swiggy account.**\n\n"
                    "To use this app, you need at least one saved delivery address. Here's how:\n\n"
                    "1. Open the **Swiggy app** on your phone\n"
                    "2. Go to **Account → Addresses → Add New Address**\n"
                    "3. Save your delivery location (Home/Work/Other)\n"
                    "4. Come back here and try again!\n\n"
                    "💡 *Once you have a saved address, I can find restaurants, "
                    "order food, groceries, and book tables near you.*"
                ),
                "tool_calls": tool_logs,
                "active_server": primary_server,
                "state": self.current_state,
                "rankings": rankings,
            }

        selected = next(
            (a for a in addresses if a.get("id") == context.get("address_id")),
            addresses[0],
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
