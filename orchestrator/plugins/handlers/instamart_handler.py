"""
Instamart server plugin handler.

Registers a handler with the OrchestratorRouter.
Uses LLM for entity extraction and dynamic contextual reasoning.
ZERO hardcoded product IDs or names.
"""

import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def register(router, client):
    """Register instamart handler with router."""
    handler = create_handler(client, router)
    router.register_handler("instamart", handler)


def create_handler(client, router):
    async def handle(query: str, context: Dict[str, Any], tool_logs: List[Dict[str, Any]], rankings: list) -> Dict[str, Any]:
        query_lower = query.lower()
        address = context["resolved_address"]

        # ---- Track order ----
        if any(w in query_lower for w in ["track", "status"]):
            return await _track_order(client, router, tool_logs)

        # ---- Add to cart ----
        if any(w in query_lower for w in ["add", "cart", "buy", "order"]):
            return await _add_to_cart(client, router, query, address, tool_logs)

        # ---- Search (default) ----
        return await _search_products(client, router, query, address, tool_logs, rankings)

    return handle


async def _search_products(client, router, query, address, tool_logs, rankings):
    """Search Instamart products. Uses LLM reasoning over location, demand, and results."""
    search_query = ""

    if router.llm:
        entities = await router._extract_entities(query, {
            "product_name": "string or null — the grocery/product to search for",
        })
        search_query = entities.get("product_name") or ""

    if not search_query:
        match = re.search(r'(?:search|find|need|buy|get|want)\s+(.+?)(?:\s*(?:near|for|please|on instamart)|$)', query.lower())
        search_query = match.group(1).strip() if match else query.lower()

    # Strip conversational filler: 'me', 'some', 'a', 'an', 'need', 'buy'
    search_query = re.sub(r'^(?:me\s+|some\s+|a\s+|an\s+|need\s+|buy\s+|get\s+)+', '', search_query.strip(), flags=re.IGNORECASE).strip()
    search_query = re.sub(r'\s+on\s+instamart.*$', '', search_query, flags=re.IGNORECASE).strip()

    if not search_query:
        search_query = "groceries"

    # Split multi-item search queries like "milk and eggs" into sub-terms
    sub_terms = [t.strip() for t in re.split(r'\s+and\s+|\s*,\s*|\s*&\s*', search_query) if t.strip()]
    if not sub_terms:
        sub_terms = [search_query]

    seen_ids = set()
    products = []
    for term in sub_terms:
        prod_res = await client.call_tool("instamart", "search_products", {
            "addressId": address.get("id", ""), "query": term
        })
        tool_logs.append({"tool": "search_products", "args": {"addressId": address.get("id", ""), "query": term}, "result": prod_res})
        if prod_res.get("success"):
            prod_data = prod_res.get("data") if isinstance(prod_res.get("data"), dict) else {}
            prod_list = prod_data.get("products", prod_data.get("data", []))
            if isinstance(prod_list, list):
                for p in prod_list:
                    if isinstance(p, dict) and p.get("id") and p["id"] not in seen_ids:
                        seen_ids.add(p["id"])
                        products.append(p)

    # LLM Dynamic Reasoning & Response Generation
    if router.llm and router.llm.api_key:
        llm_response = await router.llm.generate_response(
            query=query,
            context={
                "user_location": address.get("label", "Home"),
                "demand": "grocery request",
                "priority_server": rankings[0][0] if rankings else "instamart",
                "priority_score": rankings[0][1] if rankings else 1.0,
            },

            data={
                "search_query": search_query,
                "products_found": products,
            },
            system_instruction=(
                "You are the Swiggy Instamart Grocery Orchestrator. "
                "Evaluate the user query against their location and retrieved Instamart grocery items. "
                "STRICT RULE: ONLY reference and recommend the EXACT product names and prices present in the 'products_found' array. "
                "NEVER invent or hallucinate product names, prices, or brands not listed in 'products_found'. "
                "Highlight available key items, exact prices, stock status, and suggest how to add them to cart."
            )
        )


        if llm_response:
            return {
                "response_text": llm_response,
                "tool_calls": tool_logs,
                "active_server": "instamart",
                "state": router.current_state,
            }

    if not products:
        return {
            "response_text": f"No products found for '{search_query}' on Instamart.",
            "tool_calls": tool_logs,
            "active_server": "instamart",
            "state": router.current_state,
        }

    text = f"**Instamart** (Priority Score: {rankings[0][1]}):\n\n"
    text += f"Results for '{search_query}' near **{address['label']}**:\n"
    for i, p in enumerate(products[:4]):
        stock = "" if p.get("in_stock", True) else " *(Out of stock)*"
        text += f"  {i + 1}. **{p['name']}** — Rs.{p['price']}{stock}\n"

    text += "\nWant me to add any of these to your cart?"
    return {
        "response_text": text,
        "tool_calls": tool_logs,
        "active_server": "instamart",
        "state": router.current_state,
    }


async def _add_to_cart(client, router, query, address, tool_logs):
    """Add products to Instamart cart. LLM extracts item + quantity."""
    quantity = 1
    item_name = ""

    if router.llm:
        entities = await router._extract_entities(query, {
            "product_name": "string — the grocery/product to add",
            "quantity": "int — how many, default 1",
        })
        item_name = entities.get("product_name", "")
        quantity = entities.get("quantity", 1) or 1

    if not item_name:
        qty_match = re.search(r'(\d+)\s+(.+)', query.lower())
        if qty_match:
            quantity = int(qty_match.group(1))
            item_name = qty_match.group(2).strip()
        else:
            item_name = re.sub(r'^(?:add|order|buy|get)\s+', '', query.lower(), flags=re.IGNORECASE)
            item_name = re.sub(r'\s+to\s+cart.*$', '', item_name, flags=re.IGNORECASE)
            item_name = re.sub(r'\s+on\s+instamart.*$', '', item_name, flags=re.IGNORECASE).strip()

    item_name = re.sub(r'^(?:me\s+|some\s+|a\s+|an\s+|packet\s+of\s+|packets\s+of\s+|bottle\s+of\s+|bottles\s+of\s+)+', '', item_name.strip(), flags=re.IGNORECASE).strip()

    if not item_name:
        return {
            "response_text": "What would you like to add? Try: 'add 2 milk'.",
            "tool_calls": tool_logs,
            "active_server": "instamart",
            "state": router.current_state,
        }

    prod_res = await client.call_tool("instamart", "search_products", {
        "addressId": address["id"], "query": item_name
    })
    tool_logs.append({"tool": "search_products", "args": {"addressId": address["id"], "query": item_name}, "result": prod_res})

    prod_data = prod_res.get("data") if (prod_res.get("success") and isinstance(prod_res.get("data"), dict)) else {}
    products = prod_data.get("products", [])

    if not products:
        return {
            "response_text": f"Could not find '{item_name}' on Instamart.",
            "tool_calls": tool_logs,
            "active_server": "instamart",
            "state": router.current_state,
        }

    products = prod_res["data"]["products"]
    in_stock = [p for p in products if p.get("in_stock", True)]
    if not in_stock:
        return {
            "response_text": f"'{item_name}' is out of stock on Instamart.",
            "tool_calls": tool_logs,
            "active_server": "instamart",
            "state": router.current_state,
        }

    target = in_stock[0]
    spin_id = target.get("spinId") or target.get("id")
    sku_id = target.get("skuId") or target.get("id")

    item_payload = {
        "spinId": spin_id,
        "skuId": sku_id,
        "quantity": quantity,
    }
    update_res = await client.call_tool("instamart", "update_cart", {
        "selectedAddressId": address["id"],
        "items": [item_payload],
    })
    tool_logs.append({
        "tool": "update_cart",
        "args": {"selectedAddressId": address["id"], "items": [item_payload]},
        "result": update_res,
    })

    if not update_res.get("success"):
        return {
            "response_text": f"Failed to update cart: {update_res.get('error')}",
            "tool_calls": tool_logs,
            "active_server": "instamart",
            "state": router.current_state,
        }

    cart_data = update_res.get("data", {})
    items_list = cart_data.get("items", [target]) if isinstance(cart_data, dict) else [target]
    items_str = ", ".join(f"{it.get('quantity', quantity)}x {it.get('name', item_name)}" for it in items_list if isinstance(it, dict))
    total_val = cart_data.get('grand_total', cart_data.get('total', target.get('price', 0) * quantity)) if isinstance(cart_data, dict) else (target.get('price', 0) * quantity)

    router.current_state["stage"] = "awaiting_order_confirm"
    router.current_state["pending_action"] = {
        "server": "instamart",
        "tool_name": "checkout",
        "arguments": {"addressId": address["id"]},
    }

    delivery_charge = cart_data.get('delivery_charge', 0) if isinstance(cart_data, dict) else 0
    return {
        "response_text": (
            f"Instamart cart: {items_str}.\n"
            f"Delivery: Rs.{delivery_charge} (Free above Rs.199)\n"
            f"**Total: Rs.{total_val}**\n"
            f"Confirm placing this order? (yes/no)"
        ),
        "tool_calls": tool_logs,
        "active_server": "instamart",
        "state": router.current_state,
    }


async def _track_order(client, router, tool_logs):
    orders_res = await client.call_tool("instamart", "get_orders", {})
    tool_logs.append({"tool": "get_orders", "args": {}, "result": orders_res})

    if orders_res.get("success") and orders_res.get("data"):
        latest = orders_res["data"][0]
        track_res = await client.call_tool("instamart", "track_order", {"orderId": latest["id"]})
        tool_logs.append({"tool": "track_order", "args": {"orderId": latest["id"]}, "result": track_res})

        if track_res.get("success"):
            d = track_res["data"]
            return {
                "response_text": f"Instamart Order **{latest['id']}**:\nStatus: **{d['status']}**\nETA: **{d['etaMinutes']} min**",
                "tool_calls": tool_logs,
                "active_server": "instamart",
                "state": router.current_state,
            }

    return {
        "response_text": "No active Instamart orders to track.",
        "tool_calls": tool_logs,
        "active_server": "instamart",
        "state": router.current_state,
    }
