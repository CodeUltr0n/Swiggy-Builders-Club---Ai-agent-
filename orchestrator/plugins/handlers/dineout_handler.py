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

    dine_res = await client.call_tool("dineout", "search_restaurants_dineout", {"query": search_query})
    if not dine_res.get("success"):
        dine_res = await client.call_tool("dineout", "search_restaurants", {"query": search_query})
    tool_logs.append({"tool": "search_restaurants_dineout", "args": {"query": search_query}, "result": dine_res})

    dine_data = dine_res.get("data") if (dine_res.get("success") and isinstance(dine_res.get("data"), dict)) else {}
    restaurants = dine_data.get("restaurants", [])

    deals_info = []
    if restaurants:
        first = restaurants[0]
        router.current_state["active_restaurant_id"] = first["id"]
        router.current_state["active_restaurant_name"] = first["name"]

        details_res = await client.call_tool("dineout", "get_restaurant_details", {"restaurantId": first["id"]})
        tool_logs.append({"tool": "get_restaurant_details", "args": {"restaurantId": first["id"]}, "result": details_res})
        d_data = details_res.get("data") if (details_res.get("success") and isinstance(details_res.get("data"), dict)) else {}
        deals_info = d_data.get("deals", [])

    # LLM Dynamic Reasoning & Response Generation
    if router.llm and router.llm.api_key:
        llm_response = await router.llm.generate_response(
            query=query,
            context={
                "user_location": context.get("address_label", "Home"),
                "time_of_day": context.get("time_of_day", "current time"),
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

    text = f"**Dineout** (Priority Score: {rankings[0][1]}):\n\nTop restaurants:\n"
    for i, r in enumerate(restaurants[:3]):
        deal = " *(Deals available)*" if r.get("has_deals") else ""
        text += f"  {i + 1}. **{r['name']}** — {r['cuisine']} ({r['rating']}★, Rs.{r.get('avg_cost_for_two', 'N/A')} for two){deal}\n"

    if deals_info:
        first_name = restaurants[0]["name"]
        text += f"\nDeals at **{first_name}**:\n"
        for d in deals_info:
            price = "FREE" if d.get("isFree") else f"Rs.{d.get('bookingPrice', 0)}"
            text += f"  • {d['title']} ({price})\n"
        text += f"\nTo book: 'book a table at {first_name} for 2 guests'"

    return {
        "response_text": text,
        "tool_calls": tool_logs,
        "active_server": "dineout",
        "state": router.current_state,
    }


async def _book_table(client, router, query, context, tool_logs):
    """Book a table. LLM extracts guest count, time, date, restaurant name."""
    rest_id = router.current_state.get("active_restaurant_id")
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
            search_res = await client.call_tool("dineout", "search_restaurants_dineout", {"query": mentioned_rest})
            if not search_res.get("success"):
                search_res = await client.call_tool("dineout", "search_restaurants", {"query": mentioned_rest})
            tool_logs.append({"tool": "search_restaurants_dineout", "args": {"query": mentioned_rest}, "result": search_res})
            s_data = search_res.get("data") if (search_res.get("success") and isinstance(search_res.get("data"), dict)) else {}
            if s_data.get("restaurants"):
                found = s_data["restaurants"][0]
                rest_id = found["id"]
                router.current_state["active_restaurant_id"] = found["id"]
                router.current_state["active_restaurant_name"] = found["name"]

    if not rest_id:
        fallback_query = "dining"
        search_res = await client.call_tool("dineout", "search_restaurants_dineout", {"query": fallback_query})
        if not search_res.get("success"):
            search_res = await client.call_tool("dineout", "search_restaurants", {"query": fallback_query})
        tool_logs.append({"tool": "search_restaurants_dineout", "args": {"query": fallback_query}, "result": search_res})
        s_data = search_res.get("data") if (search_res.get("success") and isinstance(search_res.get("data"), dict)) else {}
        if s_data.get("restaurants"):
            found = s_data["restaurants"][0]
            rest_id = found["id"]
            router.current_state["active_restaurant_id"] = found["id"]
            router.current_state["active_restaurant_name"] = found["name"]
        else:
            return {
                "response_text": "No restaurants found on Dineout.",
                "tool_calls": tool_logs,
                "active_server": "dineout",
                "state": router.current_state,
            }

    details_res = await client.call_tool("dineout", "get_restaurant_details", {"restaurantId": rest_id})
    tool_logs.append({"tool": "get_restaurant_details", "args": {"restaurantId": rest_id}, "result": details_res})

    d_data = details_res.get("data") if (details_res.get("success") and isinstance(details_res.get("data"), dict)) else {}
    deals = d_data.get("deals", [])
    deal_id = "deal_001"
    if deals:
        free_deals = [d for d in deals if d.get("isFree")]
        if free_deals:
            deal_id = free_deals[0].get("id", deal_id)

    cart_res = await client.call_tool("dineout", "create_cart", {
        "restaurantId": rest_id,
        "dealId": deal_id,
        "guests": guests,
        "slotTime": slot_time,
        "slotDate": slot_date,
        "billToPay": 0.0,
        "skipPayment": True,
    })
    tool_logs.append({"tool": "create_cart", "args": {
        "restaurantId": rest_id, "dealId": deal_id, "guests": guests,
        "slotTime": slot_time, "slotDate": slot_date, "billToPay": 0.0, "skipPayment": True,
    }, "result": cart_res})

    if not cart_res.get("success"):
        return {
            "response_text": f"Reservation failed: {cart_res.get('error')}",
            "tool_calls": tool_logs,
            "active_server": "dineout",
            "state": router.current_state,
        }

    router.current_state["stage"] = "awaiting_order_confirm"
    router.current_state["pending_action"] = {
        "server": "dineout",
        "tool_name": "book_table",
        "arguments": {
            "restaurantId": rest_id,
            "slotDate": slot_date,
            "slotTime": slot_time,
            "guests": guests,
        },
    }

    rest_name = router.current_state.get("active_restaurant_name", "Restaurant")

    return {
        "response_text": (
            f"Table reserved at **{rest_name}**:\n"
            f"Guests: **{guests}** | Date: **{slot_date}** | Time: **{slot_time}** (FREE)\n"
            f"Confirm booking? (yes/no)"
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
    status_res = await client.call_tool("dineout", "get_booking_status", {"bookingId": latest["id"]})
    tool_logs.append({"tool": "get_booking_status", "args": {"bookingId": latest["id"]}, "result": status_res})

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
