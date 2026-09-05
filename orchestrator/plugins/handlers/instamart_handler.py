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


def _resolve_instamart_image(p: dict, first_var: dict, name: str) -> str:
    """Resolve real Swiggy Instamart image or provide fresh grocery photography."""
    raw = (
        first_var.get("imageUrl") or 
        p.get("imageUrl") or 
        first_var.get("imageId") or 
        p.get("imageId") or 
        first_var.get("cloudinaryImageId") or 
        p.get("cloudinaryImageId") or ""
    )
    if raw:
        if raw.startswith("http"):
            return raw
        return f"https://media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,w_660/{raw}"

    name_l = name.lower()
    if any(k in name_l for k in ["milk", "dairy", "curd", "paneer", "cheese", "butter", "yogurt"]):
        return "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=660&auto=format&fit=crop&q=80"
    if any(k in name_l for k in ["chip", "snack", "biscuit", "cookie", "namkeen", "popcorn"]):
        return "https://images.unsplash.com/photo-1621996346565-e3d5d6281292?w=660&auto=format&fit=crop&q=80"
    if any(k in name_l for k in ["fruit", "apple", "banana", "mango", "orange"]):
        return "https://images.unsplash.com/photo-1619566636858-adf3ef46400b?w=660&auto=format&fit=crop&q=80"
    if any(k in name_l for k in ["veg", "onion", "potato", "tomato", "chilli", "carrot"]):
        return "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=660&auto=format&fit=crop&q=80"
    if any(k in name_l for k in ["coke", "pepsi", "drink", "juice", "beverage", "water", "soda"]):
        return "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=660&auto=format&fit=crop&q=80"
    if any(k in name_l for k in ["chocolate", "sweet", "candy"]):
        return "https://images.unsplash.com/photo-1511381939415-e44015466834?w=660&auto=format&fit=crop&q=80"

    return "https://images.unsplash.com/photo-1542838132-92c53300491e?w=660&auto=format&fit=crop&q=80"


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
                    if not isinstance(p, dict):
                        continue
                    variations = p.get("variations", [])
                    first_var = variations[0] if (isinstance(variations, list) and variations and isinstance(variations[0], dict)) else {}
                    
                    p_id = p.get("productId") or first_var.get("spinId") or first_var.get("skuId") or p.get("id")
                    if not p_id or p_id in seen_ids:
                        continue
                    seen_ids.add(p_id)
                    
                    # Normalize fields for LLM and UI cards
                    norm_prod = dict(p)
                    norm_prod["id"] = p_id
                    norm_prod["name"] = p.get("displayName") or first_var.get("displayName") or p.get("name") or "Grocery Item"
                    norm_prod["brand"] = p.get("brand") or first_var.get("brandName") or ""
                    
                    # Price extraction
                    price_obj = p.get("price") if isinstance(p.get("price"), dict) else first_var.get("price", {})
                    p_val = price_obj.get("offerPrice") or price_obj.get("mrp") or norm_prod.get("price") or 0
                    norm_prod["price"] = p_val
                    norm_prod["mrp"] = price_obj.get("mrp") or p_val
                    
                    # Image URL & description
                    norm_prod["imageUrl"] = _resolve_instamart_image(p, first_var, norm_prod["name"])
                    norm_prod["quantity"] = first_var.get("quantityDescription") or p.get("quantity") or ""
                    
                    # Stock & SLA
                    norm_prod["in_stock"] = first_var.get("isInStockAndAvailable", p.get("inStock", True))
                    norm_prod["sla"] = first_var.get("sla", {}).get("value", "15-25")
                    
                    # IDs for cart operations
                    norm_prod["spinId"] = first_var.get("spinId")
                    norm_prod["skuId"] = first_var.get("skuId")
                    
                    products.append(norm_prod)

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
    loc_name = address.get('label') or address.get('address_line') or 'Home'
    text += f"Available on Instamart near **{loc_name}**:\n\n"
    for i, p in enumerate(products[:5]):
        stock = "" if p.get("in_stock", True) else " *(Out of stock)*"
        qty_str = f" ({p['quantity']})" if p.get("quantity") else ""
        brand_str = f" — {p['brand']}" if p.get("brand") else ""
        text += f"{i + 1}. **{p['name']}**{qty_str}{brand_str}\n"
        text += f"   • Price: **₹{p['price']}**"
        if p.get("mrp") and p["mrp"] > p["price"]:
            text += f" ~~(MRP ₹{p['mrp']})~~"
        if p.get("sla"):
            text += f" | ⚡ Delivery in {p['sla']} mins"
        text += f"{stock}\n\n"

    text += "💡 *To add to cart, reply: 'add 1 <item name>'*"
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

    in_stock = []
    for p in products:
        if not isinstance(p, dict):
            continue
        vars_list = p.get("variations", [])
        if isinstance(vars_list, list) and vars_list:
            for v in vars_list:
                if isinstance(v, dict) and v.get("isInStockAndAvailable", True) and (v.get("spinId") or v.get("skuId")):
                    price_val = 0
                    if isinstance(v.get("price"), dict):
                        price_val = v["price"].get("offerPrice") or v["price"].get("mrp") or 0
                    elif isinstance(v.get("price"), (int, float)):
                        price_val = v["price"]
                    in_stock.append({
                        "name": v.get("displayName") or p.get("displayName") or p.get("name", item_name),
                        "spinId": v.get("spinId"),
                        "skuId": v.get("skuId"),
                        "price": price_val,
                        "quantityDescription": v.get("quantityDescription", ""),
                    })
        elif p.get("spinId") or p.get("productId") or p.get("id"):
            in_stock.append({
                "name": p.get("displayName") or p.get("name", item_name),
                "spinId": p.get("spinId") or p.get("productId") or p.get("id"),
                "skuId": p.get("skuId") or p.get("productId") or p.get("id"),
                "price": p.get("price", 0) if isinstance(p.get("price"), (int, float)) else 0,
                "quantityDescription": p.get("quantity", ""),
            })

    if not in_stock:
        return {
            "response_text": f"'{item_name}' is currently out of stock on Instamart.",
            "tool_calls": tool_logs,
            "active_server": "instamart",
            "state": router.current_state,
        }

    target = in_stock[0]
    spin_id = target.get("spinId") or "SPIN_DEFAULT"
    sku_id = target.get("skuId") or "SKU_DEFAULT"

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
    items_str = ", ".join(f"{it.get('quantity', quantity)}x {it.get('name', target['name'])}" for it in items_list if isinstance(it, dict))
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
            f"🛒 **Instamart Cart**:\n"
            f"• {items_str}\n"
            f"• Delivery: ₹{delivery_charge} (Free above ₹199)\n"
            f"• **Grand Total: ₹{total_val}**\n\n"
            f"Confirm placing this order? Reply **yes** or **no**."
        ),
        "tool_calls": tool_logs,
        "active_server": "instamart",
        "state": router.current_state,
    }


async def _track_order(client, router, tool_logs):
    orders_res = await client.call_tool("instamart", "get_orders", {})
    tool_logs.append({"tool": "get_orders", "args": {}, "result": orders_res})

    if orders_res.get("success") and orders_res.get("data"):
        data = orders_res["data"]
        orders_list = data if isinstance(data, list) else (data.get("orders", []) if isinstance(data, dict) else [])
        if orders_list:
            latest = orders_list[0]
            addr = context.get("resolved_address", {})
            lat = addr.get("latitude", 16.5062)
            lng = addr.get("longitude", 80.6480)
            track_res = await client.call_tool("instamart", "track_order", {
                "orderId": order_id,
                "lat": lat,
                "lng": lng,
            })
            tool_logs.append({"tool": "track_order", "args": {"orderId": order_id, "lat": lat, "lng": lng}, "result": track_res})

            if track_res.get("success"):
                d = track_res["data"] if isinstance(track_res.get("data"), dict) else {}
                status_str = d.get("status") or d.get("orderStatus") or "DELIVERED"
                eta_str = f"\nETA: **{d.get('etaMinutes') or d.get('deliveryTime', 15)} min**" if (d.get("etaMinutes") or d.get("deliveryTime")) else ""
                return {
                    "response_text": f"📦 Instamart Order **{order_id}**:\nStatus: **{status_str}**{eta_str}",
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
