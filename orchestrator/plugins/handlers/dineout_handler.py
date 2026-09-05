"""
Dineout server plugin handler.

Registers a handler with the OrchestratorRouter.
Uses LLM for entity extraction and dynamic contextual reasoning.
ZERO hardcoded restaurant IDs or names.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def register(router, client):
    """Register dineout handler with router."""
    handler = create_handler(client, router)
    router.register_handler("dineout", handler)


def create_handler(client, router):
    async def handle(query: str, context: Dict[str, Any], tool_logs: List[Dict[str, Any]], rankings: list) -> Dict[str, Any]:
        query_lower = query.lower()

        # ---- Check booking status first ----
        if any(w in query_lower for w in ["booking", "status", "track", "where"]):
            return await _booking_status(client, router, tool_logs)


        # ---- Book table ----
        if any(w in query_lower for w in ["book", "table", "reserve"]):
            return await _book_table(client, router, query, context, tool_logs)

        # ---- Search (default) ----
        return await _search_restaurants(client, router, query, context, tool_logs, rankings)

    return handle


def _extract_dineout_restaurants(tool_result: dict) -> list:
    """Safely extract restaurant list from Dineout tool response."""
    if not tool_result.get("success"):
        return []

    structured = tool_result.get("structured")
    if isinstance(structured, dict):
        if isinstance(structured.get("restaurants"), list) and structured["restaurants"]:
            return structured["restaurants"]
        if isinstance(structured.get("data"), dict) and isinstance(structured["data"].get("restaurants"), list):
            return structured["data"]["restaurants"]
        if isinstance(structured.get("data"), list) and structured["data"]:
            return structured["data"]

    data = tool_result.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("restaurants"), list) and data["restaurants"]:
            return data["restaurants"]
        if isinstance(data.get("data"), dict) and isinstance(data["data"].get("restaurants"), list):
            return data["data"]["restaurants"]
        if isinstance(data.get("data"), list) and data["data"]:
            return data["data"]

    if isinstance(data, str):
        try:
            import json
            parsed = json.loads(data)
            return _extract_dineout_restaurants({"success": True, "data": parsed})
        except Exception:
            pass

        import re, json
        m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', data) or re.search(r'(\{[\s\S]*"restaurants"[\s\S]*\})', data)
        if m:
            try:
                parsed = json.loads(m.group(1))
                return _extract_dineout_restaurants({"success": True, "data": parsed})
            except Exception:
                pass

        lines = data.split("\n")
        parsed_from_text = []
        for line in lines:
            # 1. Swiggy Dineout text format: "1. Pakwan - Royal Vegetarian Dining —  | 4.2★ |  | Indiranagar (ID: 803908)"
            m = re.search(r'^\s*\d+\.\s*(.+?)\s*—\s*(.*?)\(ID:\s*(\d+)\)', line)
            if m:
                name = m.group(1).strip()
                meta = m.group(2)
                r_id = m.group(3).strip()
                r_match = re.search(r'([0-9.]+)\s*★', meta)
                rating = r_match.group(1) if r_match else "4.2"
                parts = [p.strip() for p in meta.split('|') if p.strip() and '★' not in p]
                locality = parts[-1] if parts else "Bengaluru"
                cuisine = parts[0] if len(parts) > 1 else "Dining"
                parsed_from_text.append({
                    "id": r_id,
                    "name": name,
                    "rating": rating,
                    "locality": locality,
                    "cuisine": f"{cuisine}, {locality}" if locality else cuisine,
                    "avg_cost_for_two": "₹1,200",
                    "has_deals": True
                })
                continue

            # 2. Fallback without em-dash
            m2 = re.search(r'^\s*\d+\.\s*(.+?)\s*\(ID:\s*(\d+)\)', line)
            if m2:
                parsed_from_text.append({
                    "id": m2.group(2).strip(),
                    "name": m2.group(1).strip(),
                    "rating": "4.2",
                    "cuisine": "Dining",
                    "avg_cost_for_two": "₹1,200",
                    "has_deals": True
                })
                continue

            # 3. Fallback bold markdown
            m_bold = re.search(r'(?:^\d+\.|\*|\-)\s*\*\*([^*]+)\*\*(.*)', line)
            if m_bold:
                name = m_bold.group(1).strip()
                parsed_from_text.append({
                    "id": f"dine_{len(parsed_from_text)+1}",
                    "name": name,
                    "cuisine": "Dining",
                    "rating": "4.2",
                    "avg_cost_for_two": "₹1,200",
                    "has_deals": True
                })

        if parsed_from_text:
            return parsed_from_text

    return []


async def _search_restaurants(client, router, query, context, tool_logs, rankings):
    """Search Dineout restaurants. Uses LLM reasoning over demand, location, and deals."""
    search_query = ""

    if router.llm:
        entities = await router._extract_entities(query, {
            "restaurant_name": "string or null — specific restaurant name mentioned",
            "cuisine": "string or null — cuisine type preference",
        })
        search_query = entities.get("restaurant_name") or entities.get("cuisine") or ""

    if not search_query:
        import re
        match = re.search(r'(?:search for|find|show|book|reserve|at)\s+([a-zA-Z\s]+?)(?:\s+in|\s+near|\s+for|\s+on\s+dineout|$)', query, re.IGNORECASE)
        if match:
            search_query = match.group(1).strip()

    search_query = re.sub(r'^(?:me\s+|some\s+|a\s+|an\s+|table\s+for\s+\d+\s+at\s+|table\s+at\s+|dining\s+|restaurants\s+on\s+dineout)+', '', search_query.strip(), flags=re.IGNORECASE).strip()
    if not search_query or search_query.lower() in ["dineout", "restaurants", "dining", "table"]:
        search_query = "dining"

    lat = context.get("resolved_address", {}).get("latitude")
    lng = context.get("resolved_address", {}).get("longitude")
    if not lat or not lng:
        from orchestrator.router import resolve_lat_lng
        lat, lng = resolve_lat_lng(context.get("resolved_address", {}))
    addr_id = context.get("resolved_address", {}).get("id")

    search_args = {
        "query": search_query,
        "latitude": lat,
        "longitude": lng,
    }
    if addr_id:
        search_args["addressId"] = addr_id

    dine_res = await client.call_tool("dineout", "search_restaurants_dineout", search_args)
    tool_logs.append({"tool": "search_restaurants_dineout", "args": search_args, "result": dine_res})

    raw_restaurants = _extract_dineout_restaurants(dine_res)
    restaurants = []
    for r in raw_restaurants:
        if not isinstance(r, dict):
            continue
        norm_r = dict(r)
        norm_r["id"] = r.get("restaurantId") or r.get("id")
        norm_r["name"] = r.get("name") or r.get("restaurantName") or "Dineout Restaurant"
        cuisines = r.get("cuisines")
        norm_r["cuisine"] = ", ".join(cuisines) if isinstance(cuisines, list) else (r.get("cuisine") or "Dining & Bar")
        norm_r["rating"] = r.get("rating") or r.get("avgRating") or "4.3"
        norm_r["avg_cost_for_two"] = r.get("costForTwo") or r.get("avgCostForTwo") or r.get("avg_cost_for_two") or "₹1,200"
        norm_r["imageUrl"] = r.get("imageUrl") or r.get("mediaImageUrl") or ""
        norm_r["has_deals"] = bool(r.get("hasDeals") or r.get("deals"))
        restaurants.append(norm_r)

    deals_info = []
    if restaurants:
        first = restaurants[0]
        first_id = first.get("id")
        router.current_state["active_restaurant_id"] = first_id
        router.current_state["active_restaurant_name"] = first.get("name")

        if first_id:
            details_res = await client.call_tool("dineout", "get_restaurant_details", {
                "restaurantId": first_id,
                "latitude": lat,
                "longitude": lng,
            })
            tool_logs.append({"tool": "get_restaurant_details", "args": {"restaurantId": first_id, "latitude": lat, "longitude": lng}, "result": details_res})
            d_data = details_res.get("data") if (details_res.get("success") and isinstance(details_res.get("data"), dict)) else {}
            deals_info = d_data.get("deals", []) if isinstance(d_data, dict) else []

    # LLM Dynamic Reasoning & Response Generation
    if router.llm and router.llm.api_key:
        llm_response = await router.llm.generate_response(
            query=query,
            context={
                "user_location": context.get("resolved_address", {}).get("label", "Home"),
                "time_of_day": context.get("time_of_day", "evening"),
                "demand": "dining out / table reservation",
                "priority_server": rankings[0][0] if rankings else "dineout",
                "priority_score": rankings[0][1] if rankings else 1.0,
            },
            data={
                "search_query": search_query,
                "restaurants": restaurants,
                "featured_restaurant_deals": deals_info,
            },
            system_instruction=(
                "You are the Swiggy Dineout Table Booking Orchestrator. "
                "Evaluate the user request against their location, time of day/demand, and available restaurants and deals. "
                "Recommend top dining options, explain available free/paid deals, and guide the user on booking a table."
            )
        )

        if llm_response:
            return {
                "response_text": llm_response,
                "tool_calls": tool_logs,
                "active_server": "dineout",
                "state": router.current_state,
            }

    if not restaurants:
        return {
            "response_text": f"No restaurants found{' for ' + search_query if search_query else ''} on Dineout.",
            "tool_calls": tool_logs,
            "active_server": "dineout",
            "state": router.current_state,
        }

    loc_name = context.get("resolved_address", {}).get("label") or context.get("resolved_address", {}).get("city") or "your area"
    text = f"**Dineout** (Priority Score: {rankings[0][1]}):\n\nTop dining options near **{loc_name}**:\n\n"
    for i, r in enumerate(restaurants[:4]):
        deal = " *(Offers available)*" if r.get("has_deals") else ""
        text += f"{i + 1}. **{r['name']}** — {r['cuisine']} ({r['rating']}★, {r['avg_cost_for_two']} for two){deal}\n"

    if deals_info:
        first_name = restaurants[0]["name"]
        text += f"\n✨ Featured Deals at **{first_name}**:\n"
        for d in deals_info[:3]:
            price = "FREE" if d.get("isFree") else f"₹{d.get('bookingPrice', 0)}"
            text += f"  • {d.get('title', 'Special Offer')} ({price})\n"

    first_name = restaurants[0]["name"]
    text += f"\n💡 *To book a table, reply: 'book a table at {first_name} for 2 guests'*"

    return {
        "response_text": text,
        "tool_calls": tool_logs,
        "active_server": "dineout",
        "state": router.current_state,
    }


async def _book_table(client, router, query, context, tool_logs):
    """Book a table. Extracts guest count, time, date, restaurant name."""
    lat = context.get("resolved_address", {}).get("latitude")
    lng = context.get("resolved_address", {}).get("longitude")
    if not lat or not lng:
        from orchestrator.router import resolve_lat_lng
        lat, lng = resolve_lat_lng(context.get("resolved_address", {}))

    rest_id = None
    guests = 2
    slot_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    slot_time = "8:00 PM"

    if router.llm:
        entities = await router._extract_entities(query, {
            "restaurant_name": "string or null — restaurant name if mentioned",
            "guests": "int — number of guests, default 2",
            "date": "string or null — booking date in YYYY-MM-DD, default tomorrow",
            "time": "string or null — booking time like '8 PM', default '8:00 PM'",
        })
        guests = entities.get("guests", 2) or 2
        slot_date = entities.get("date") or slot_date
        slot_time = entities.get("time") or slot_time

        mentioned_rest = entities.get("restaurant_name")
        if mentioned_rest:
            search_args = {"query": mentioned_rest, "latitude": lat, "longitude": lng}
            search_res = await client.call_tool("dineout", "search_restaurants_dineout", search_args)
            tool_logs.append({"tool": "search_restaurants_dineout", "args": search_args, "result": search_res})
            found_list = _extract_dineout_restaurants(search_res)
            if found_list:
                found = found_list[0]
                rest_id = found.get("restaurantId") or found.get("id")
                router.current_state["active_restaurant_id"] = rest_id
                router.current_state["active_restaurant_name"] = found.get("name")

    if not rest_id:
        fallback_query = "dining"
        search_args = {"query": fallback_query, "latitude": lat, "longitude": lng}
        search_res = await client.call_tool("dineout", "search_restaurants_dineout", search_args)
        tool_logs.append({"tool": "search_restaurants_dineout", "args": search_args, "result": search_res})
        found_list = _extract_dineout_restaurants(search_res)
        if found_list:
            found = found_list[0]
            rest_id = found.get("restaurantId") or found.get("id")
            router.current_state["active_restaurant_id"] = rest_id
            router.current_state["active_restaurant_name"] = found.get("name")
        else:
            return {
                "response_text": "No restaurants found on Dineout for booking.",
                "tool_calls": tool_logs,
                "active_server": "dineout",
                "state": router.current_state,
            }

    # Query available slots from Swiggy Dineout
    slots_res = await client.call_tool("dineout", "get_available_slots", {
        "restaurantId": rest_id,
        "date": slot_date,
        "latitude": lat,
        "longitude": lng,
    })
    tool_logs.append({
        "tool": "get_available_slots",
        "args": {"restaurantId": rest_id, "date": slot_date, "latitude": lat, "longitude": lng},
        "result": slots_res,
    })

    slot_id = "SLOT_DEFAULT"
    item_id = "ITEM_DEFAULT"
    reservation_time = slot_time
    if slots_res.get("success"):
        s_data = slots_res.get("data")
        slots_list = s_data.get("slots", []) if isinstance(s_data, dict) else (s_data if isinstance(s_data, list) else [])
        if slots_list and isinstance(slots_list[0], dict):
            first_slot = slots_list[0]
            slot_id = first_slot.get("slotId") or first_slot.get("id") or slot_id
            item_id = first_slot.get("itemId") or item_id
            reservation_time = first_slot.get("reservationTime") or reservation_time

    # Create Cart with valid Swiggy contract type: DEAL_TICKET_PURCHASE
    cart_res = await client.call_tool("dineout", "create_cart", {
        "restaurantId": rest_id,
        "cartType": "DEAL_TICKET_PURCHASE",
        "latitude": lat,
        "longitude": lng,
    })
    tool_logs.append({"tool": "create_cart", "args": {
        "restaurantId": rest_id, "cartType": "DEAL_TICKET_PURCHASE", "latitude": lat, "longitude": lng,
    }, "result": cart_res})

    router.current_state["stage"] = "awaiting_order_confirm"
    router.current_state["pending_action"] = {
        "server": "dineout",
        "tool_name": "book_table",
        "arguments": {
            "restaurantId": rest_id,
            "slotId": slot_id,
            "itemId": item_id,
            "reservationTime": reservation_time,
            "guestCount": guests,
            "latitude": lat,
            "longitude": lng,
        },
    }

    rest_name = router.current_state.get("active_restaurant_name", "Restaurant")

    return {
        "response_text": (
            f"🍽️ Table reservation at **{rest_name}**:\n"
            f"• Guests: **{guests}**\n"
            f"• Date: **{slot_date}**\n"
            f"• Time: **{reservation_time}**\n\n"
            f"Confirm booking? Reply **yes** or **no**."
        ),
        "tool_calls": tool_logs,
        "active_server": "dineout",
        "state": router.current_state,
    }


async def _booking_status(client, router, tool_logs):
    """Check existing Dineout booking status."""
    db_orders = client.memory.get_past_orders() if hasattr(client.memory, "get_past_orders") else []
    dineout_orders = [o for o in db_orders if o.get("server") == "dineout"]

    if not dineout_orders:
        return {
            "response_text": "No table bookings found.",
            "tool_calls": tool_logs,
            "active_server": "dineout",
            "state": router.current_state,
        }

    latest = dineout_orders[0]
    status_res = await client.call_tool("dineout", "get_booking_status", {"orderId": latest["id"]})
    tool_logs.append({"tool": "get_booking_status", "args": {"orderId": latest["id"]}, "result": status_res})

    if status_res.get("success"):
        d = status_res["data"]
        return {
            "response_text": f"Dineout Booking **{latest['id']}**:\nStatus: **{d['status']}**",
            "tool_calls": tool_logs,
            "active_server": "dineout",
            "state": router.current_state,
        }

    return {
        "response_text": "Could not check booking status.",
        "tool_calls": tool_logs,
        "active_server": "dineout",
        "state": router.current_state,
    }
