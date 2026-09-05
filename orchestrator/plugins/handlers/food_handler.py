"""
Food server plugin handler.

Registers a handler with the OrchestratorRouter.
Uses LLM for entity extraction and dynamic contextual reasoning (demand, location, open options).
ZERO hardcoded restaurant IDs or rigid template strings.
"""

import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def register(router, client):
    """Register food handler with router."""
    handler = create_handler(client, router)
    router.register_handler("food", handler)


def create_handler(client, router):
    """Factory that returns a handler coroutine bound to client + router."""

    async def handle(query: str, context: Dict[str, Any], tool_logs: List[Dict[str, Any]], rankings: list) -> Dict[str, Any]:
        query_lower = query.lower()
        address = context["resolved_address"]

        # ---- Scenario 1: Track order ----
        if any(w in query_lower for w in ["track", "status", "where is"]):
            return await _track_order(client, router, tool_logs)

        # ---- Scenario 2: Add to cart / Place order ----
        if any(w in query_lower for w in ["add", "cart", "order", "place", "buy"]):
            return await _add_to_cart(client, router, query, address, tool_logs)

        # ---- Scenario 3: Search / Browse (default for food) ----
        return await _search_restaurants(client, router, query, address, tool_logs, rankings)

    return handle


async def _track_order(client, router, tool_logs):
    orders_res = await client.call_tool("food", "get_food_orders", {})
    tool_logs.append({"tool": "get_food_orders", "args": {}, "result": orders_res})

    if orders_res.get("success") and orders_res.get("data"):
        latest = orders_res["data"][0]
        order_id = latest["id"]
        track_res = await client.call_tool("food", "track_food_order", {"orderId": order_id})
        tool_logs.append({"tool": "track_food_order", "args": {"orderId": order_id}, "result": track_res})

        if track_res.get("success"):
            d = track_res["data"]
            return {
                "response_text": (
                    f"Tracking **{order_id}** from **{latest['merchant_name']}**:\n"
                    f"Status: **{d['status']}**\n"
                    f"Delivery: **{d['deliveryPartnerName']}** ({d['deliveryPartnerPhone']})\n"
                    f"ETA: **{d['etaMinutes']} min**"
                ),
                "tool_calls": tool_logs,
                "active_server": "food",
                "state": router.current_state,
            }

    return {
        "response_text": "No active food orders to track.",
        "tool_calls": tool_logs,
        "active_server": "food",
        "state": router.current_state,
    }


async def _search_restaurants(client, router, query, address, tool_logs, rankings):
    """
    Search restaurants and synthesize a dynamic response via LLM reasoning
    considering user demand, location, time-of-day, and available open venues/menus.
    """
    search_query = ""

    if router.llm:
        entities = await router._extract_entities(query, {
            "search_query": "string or null — what food/cuisine/item user wants to find",
            "restaurant_name": "string or null — specific restaurant name mentioned",
        })
        search_query = entities.get("search_query") or entities.get("restaurant_name") or ""
    else:
        match = re.search(
            r'(?:search for|find|get|show|want|crave|cravings for)\s+(.+?)(?:\s*(?:near|for|please)|$)',
            query.lower()
        )
        if match:
            search_query = match.group(1).strip()

    generic = {"to eat something", "something to eat", "something", "food", "some food", "hungry", "eat", "anything", "me"}
    if search_query.lower() in generic:
        search_query = ""

    # Search for matching open restaurants first
    rest_res = await client.call_tool("food", "search_restaurants", {
        "addressId": address["id"], "query": search_query
    })
    tool_logs.append({
        "tool": "search_restaurants",
        "args": {"addressId": address["id"], "query": search_query},
        "result": rest_res
    })

    restaurants = rest_res.get("data", {}).get("restaurants", []) if rest_res.get("success") else []

    # If specific query returned 0 restaurants, fetch all open restaurants as options
    if not restaurants:
        all_open_res = await client.call_tool("food", "search_restaurants", {
            "addressId": address["id"], "query": ""
        })
        tool_logs.append({
            "tool": "search_restaurants",
            "args": {"addressId": address["id"], "query": ""},
            "result": all_open_res
        })
        if all_open_res.get("success"):
            restaurants = all_open_res["data"].get("restaurants", [])

    # If search calls failed entirely (e.g. auth/MCP error), tell the user why
    if not restaurants and not rest_res.get("success"):
        error_msg = rest_res.get("error", "Unknown error connecting to Swiggy servers")
        return {
            "response_text": (
                f"⚠️ **Could not fetch restaurants from Swiggy.**\n\n"
                f"Error: `{error_msg}`\n\n"
                f"This usually means the OAuth session needs to be refreshed. "
                f"Please try [re-authenticating](/auth/start)."
            ),
            "tool_calls": tool_logs,
            "active_server": "food",
            "state": router.current_state,
        }

    # Fetch menu items for top open restaurants to provide rich LLM context
    restaurant_options = []
    for r in restaurants[:3]:
        menu_res = await client.call_tool("food", "get_restaurant_menu", {"restaurantId": r["id"]})
        tool_logs.append({"tool": "get_restaurant_menu", "args": {"restaurantId": r["id"]}, "result": menu_res})
        items = menu_res.get("data", {}).get("items", []) if menu_res.get("success") else []
        restaurant_options.append({
            "id": r["id"],
            "name": r["name"],
            "cuisine": r["cuisine"],
            "rating": r["rating"],
            "distance_km": r["distance_km"],
            "menu_highlights": [f"{it['name']} (Rs.{it['price']})" for it in items[:4]]
        })

    if restaurant_options:
        first = restaurant_options[0]
        router.current_state["active_restaurant_id"] = first["id"]
        router.current_state["active_restaurant_name"] = first["name"]

    # LLM Dynamic Reasoning & Response Generation
    if router.llm and router.llm.api_key:
        llm_response = await router.llm.generate_response(
            query=query,
            context={
                "user_location": address.get("label", "Home"),
                "time_of_day": rankings[0][2] if rankings else "current time",
                "demand": "food request",
                "priority_server": rankings[0][0] if rankings else "food",
                "priority_score": rankings[0][1] if rankings else 1.0,
            },
            data={
                "search_query": search_query,
                "open_restaurants": restaurant_options,
            },
            system_instruction=(
                "You are the Swiggy MCP Food Orchestrator. "
                "The user is asking for food/sweets/meals. "
                "Analyze their request based on their location, time of day/demand, and the retrieved open restaurants and menus. "
                "If the specific item requested (e.g. sweets/desserts) is not directly available from open restaurants, "
                "explain why politely, evaluate the best available open alternatives or dishes, and suggest how to order them. "
                "Format cleanly using GitHub Markdown with bold restaurant names and prices."
            )
        )

        if llm_response:
            return {
                "response_text": llm_response,
                "tool_calls": tool_logs,
                "active_server": "food",
                "state": router.current_state,
            }

    # Standard fallback formatting if LLM is disabled
    text = f"**Food Server** (Priority Score: {rankings[0][1]}):\n\n"
    text += f"Open restaurants near **{address['label']}**:\n"
    for i, r in enumerate(restaurant_options):
        text += f"  {i + 1}. **{r['name']}** — {r['cuisine']} ({r['rating']}★)\n"

    if restaurant_options and restaurant_options[0]["menu_highlights"]:
        text += f"\nPopular items at **{restaurant_options[0]['name']}**:\n"
        for item_str in restaurant_options[0]["menu_highlights"]:
            text += f"  • {item_str}\n"

    return {
        "response_text": text,
        "tool_calls": tool_logs,
        "active_server": "food",
        "state": router.current_state,
    }


async def _add_to_cart(client, router, query, address, tool_logs):
    """Add items to cart. Supports multi-item, multi-quantity, case-insensitive orders."""
    restaurant_name = ""
    raw_items = []

    if router.llm:
        entities = await router._extract_entities(query, {
            "restaurant_name": "string or null — name of the restaurant if mentioned",
            "items": "list of objects or strings — items requested, e.g. [{'name': 'Special Chicken Biryani', 'quantity': 1}]",
            "item_name": "string or null — single item name if only one item requested",
            "quantity": "int — quantity for single item, default 1",
        })
        if isinstance(entities, dict):
            restaurant_name = entities.get("restaurant_name") or ""
            items_field = entities.get("items")
            if isinstance(items_field, list) and items_field:
                for it in items_field:
                    if isinstance(it, dict):
                        n = it.get("name") or it.get("item_name") or ""
                        q = it.get("quantity", 1) or 1
                        if n:
                            raw_items.append((str(n).strip(), int(q)))
                    elif isinstance(it, str) and it.strip():
                        raw_items.append((it.strip(), 1))
            elif entities.get("item_name") and isinstance(entities.get("item_name"), str):
                raw_items.append((entities["item_name"].strip(), int(entities.get("quantity", 1) or 1)))

    if not raw_items:
        # Multi-item regex matching (e.g. "1 Special chicken Biryani and 3 Garlic Naan" or lowercase)
        matches = re.findall(r'(\d+)\s+([a-zA-Z\s]+?)(?=\s+\d+|\s+and\s+|\s*,\s*|\s+from\s+|\s+to\s+cart|\s*$)', query, re.IGNORECASE)
        if matches:
            for qty_str, name_str in matches:
                clean_name = re.sub(r'^(?:add|order|get|want)\s+', '', name_str, flags=re.IGNORECASE).strip()
                if clean_name and clean_name.lower() not in ["and"]:
                    raw_items.append((clean_name, int(qty_str)))

    if not raw_items:
        qty_match = re.search(r'(\d+)\s+([a-zA-Z\s]+)', query)
        if qty_match:
            raw_items.append((qty_match.group(2).strip(), int(qty_match.group(1))))

    if not raw_items:
        return {
            "response_text": "Please specify the item and quantity you would like to add to your cart.",
            "tool_calls": tool_logs,
            "active_server": "food",
            "state": router.current_state,
        }

    # Search items across open restaurants
    matched_items_by_rest = {}
    not_found = []

    for name_str, qty in raw_items:
        clean_search = re.sub(r'\s+from\s+.*|\s+to\s+cart.*', '', name_str, flags=re.IGNORECASE).strip()
        search_term = clean_search.lower().rstrip('s') if len(clean_search) > 3 else clean_search.lower()

        search_res = await client.call_tool("food", "search_menu", {"query": search_term})
        tool_logs.append({"tool": "search_menu", "args": {"query": search_term}, "result": search_res})

        items_found = search_res.get("data", {}).get("items", []) if search_res.get("success") else []

        if restaurant_name and items_found:
            filtered = [i for i in items_found if restaurant_name.lower() in i.get("restaurantName", "").lower()]
            if filtered:
                items_found = filtered

        if items_found:
            matched = items_found[0]
            r_id = matched["restaurantId"]
            r_name = matched.get("restaurantName", "Restaurant")
            if r_id not in matched_items_by_rest:
                matched_items_by_rest[r_id] = {"rest_name": r_name, "items": []}
            matched_items_by_rest[r_id]["items"].append({
                "itemId": matched["id"],
                "name": matched["name"],
                "quantity": qty,
                "price": matched["price"]
            })
        else:
            not_found.append(name_str)

    if not matched_items_by_rest:
        missing_str = ", ".join([f"'{n}'" for n in not_found])
        return {
            "response_text": f"Could not find {missing_str} on the menu of any OPEN restaurant near **{address['label']}**.",
            "tool_calls": tool_logs,
            "active_server": "food",
            "state": router.current_state,
        }

    # Select target restaurant (prefer the one with the most matched items)
    target_rest_id = max(matched_items_by_rest.keys(), key=lambda r: len(matched_items_by_rest[r]["items"]))
    target_rest = matched_items_by_rest[target_rest_id]
    rest_name = target_rest["rest_name"]
    items_payload = [{"itemId": it["itemId"], "quantity": it["quantity"]} for it in target_rest["items"]]

    cart_res = await client.call_tool("food", "update_food_cart", {
        "restaurantId": target_rest_id,
        "items": items_payload
    })
    tool_logs.append({
        "tool": "update_food_cart",
        "args": {"restaurantId": target_rest_id, "items": items_payload},
        "result": cart_res
    })

    if not cart_res.get("success"):
        return {
            "response_text": f"Cart update failed: {cart_res.get('error')}",
            "tool_calls": tool_logs,
            "active_server": "food",
            "state": router.current_state,
        }

    cart_data = cart_res.get("data", {})
    subtotal = cart_data.get("subtotal", 0.0)

    # Food Cart Cap limit Rs 1000
    if subtotal > 1000:
        return {
            "response_text": f"Order total (Rs.{subtotal}) exceeds maximum single food cart limit of ₹1000.",
            "tool_calls": tool_logs,
            "active_server": "food",
            "state": router.current_state,
        }

    coupon_res = await client.call_tool("food", "apply_food_coupon", {"code": "WELCOME50"})
    tool_logs.append({"tool": "apply_food_coupon", "args": {"code": "WELCOME50"}, "result": coupon_res})

    final_total = cart_data.get("grand_total", subtotal)
    if coupon_res.get("success") and coupon_res.get("data", {}).get("final_amount"):
        final_total = coupon_res["data"]["final_amount"]

    router.current_state["stage"] = "awaiting_order_confirm"
    router.current_state["pending_action"] = {
        "server": "food",
        "tool_name": "place_food_order",
        "arguments": {"addressId": address["id"], "paymentMethod": "COD"}
    }

    added_lines = "\n".join([f"• **{it['quantity']}x {it['name']}** (Rs.{it['price'] * it['quantity']})" for it in target_rest["items"]])

    return {
        "response_text": (
            f"Added to cart from **{rest_name}**:\n"
            f"{added_lines}\n"
            f"Applied coupon WELCOME50 (50% off).\n"
            f"**Grand Total: Rs.{final_total}** (COD)\n"
            f"Confirm placing this order? (yes/no)"
        ),
        "tool_calls": tool_logs,
        "active_server": "food",
        "state": router.current_state,
    }

