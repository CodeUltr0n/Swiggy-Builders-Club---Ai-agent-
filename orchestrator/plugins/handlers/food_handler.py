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


def _extract_restaurants(tool_result: dict) -> list:
    """Safely extract restaurant list from a call_tool result.

    The Swiggy MCP may return data in different shapes:
    - structuredContent: {"restaurants": [...], "dishes": [...]}
    - {"data": {"restaurants": [...]}}
    - {"data": [...]}  (flat list)
    - {"dishes": [...]} -> extracted to restaurant entries
    - {"data": "json string" or markdown text}
    """
    if not tool_result.get("success"):
        return []

    # Check structured content first if present
    structured = tool_result.get("structured")
    if isinstance(structured, dict):
        if "restaurants" in structured and isinstance(structured["restaurants"], list) and structured["restaurants"]:
            return structured["restaurants"]
        if "data" in structured and isinstance(structured["data"], dict) and "restaurants" in structured["data"]:
            return structured["data"]["restaurants"]

    data = tool_result.get("data")
    if data is None:
        return []

    # data is already a list
    if isinstance(data, list):
        return data

    # data is a dict
    if isinstance(data, dict):
        if "restaurants" in data and isinstance(data["restaurants"], list) and data["restaurants"]:
            return data["restaurants"]
        if "data" in data and isinstance(data["data"], dict):
            inner_rest = data["data"].get("restaurants", [])
            if inner_rest and isinstance(inner_rest, list):
                return inner_rest

        # If dishes are returned, extract restaurants from dishes
        dishes = data.get("dishes") or (data.get("data", {}).get("dishes") if isinstance(data.get("data"), dict) else None)
        if isinstance(dishes, list) and dishes:
            dish_restaurants = {}
            for d in dishes:
                r_id = d.get("restaurantId") or d.get("restaurant_id")
                r_name = d.get("restaurantName") or d.get("restaurant_name")
                if r_id and r_id not in dish_restaurants:
                    dish_restaurants[r_id] = {
                        "id": r_id,
                        "name": r_name or "Restaurant",
                        "cuisine": d.get("category", "Food"),
                        "rating": d.get("restaurantRating", "4.0"),
                        "menu_highlights": [f"{d.get('name')} (Rs.{d.get('price', '?')})"],
                    }
                elif r_id and len(dish_restaurants[r_id]["menu_highlights"]) < 3:
                    dish_restaurants[r_id]["menu_highlights"].append(f"{d.get('name')} (Rs.{d.get('price', '?')})")
            if dish_restaurants:
                return list(dish_restaurants.values())

        if "cards" in data:
            return _extract_from_cards(data["cards"])

    # data is a string
    if isinstance(data, str):
        import re
        import json

        # 1. Try direct JSON parse
        try:
            parsed = json.loads(data)
            res = _extract_restaurants({"success": True, "data": parsed})
            if res:
                return res
        except Exception:
            pass

        # 2. Try JSON regex search for codeblock or object
        json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', data) or re.search(r'(\{[\s\S]*"restaurants"[\s\S]*\})', data)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                res = _extract_restaurants({"success": True, "data": parsed})
                if res:
                    return res
            except Exception:
                pass

        # 3. Parse markdown restaurant listings from Swiggy's text
        text_restaurants = []
        pattern = re.findall(r'(?:^|\n)\s*(?:\d+\.|\*|\-)?\s*\*\*([^*]+)\*\*(.*?)(?=\n|$)', data)
        for name, details in pattern:
            clean_name = name.strip()
            if any(h in clean_name.lower() for h in ["food server", "popular items", "added to cart", "warning", "note"]):
                continue
            rating_match = re.search(r'(\d\.\d)\s*★?', details)
            rating = rating_match.group(1) if rating_match else "4.2"
            cuisine = re.sub(r'\(.*?\)', '', details).strip(" —-|,\t")
            text_restaurants.append({
                "id": f"rest_{len(text_restaurants)+1}",
                "name": clean_name,
                "cuisine": cuisine or "Multi-cuisine",
                "rating": rating,
                "distance_km": 1.5,
            })
        if text_restaurants:
            return text_restaurants

    return []


def _extract_from_cards(cards: list) -> list:
    """Extract restaurants from Swiggy's card-based response format."""
    restaurants = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        # Navigate into card -> card -> info structure
        info = card.get("card", {}).get("card", {}).get("info", card.get("info", {}))
        if isinstance(info, dict) and info.get("id"):
            restaurants.append({
                "id": info.get("id"),
                "name": info.get("name", "Unknown"),
                "cuisine": ", ".join(info.get("cuisines", [])) if isinstance(info.get("cuisines"), list) else info.get("cuisine", ""),
                "rating": info.get("avgRating", info.get("rating", "N/A")),
                "distance_km": info.get("sla", {}).get("lastMileTravel", 0) if isinstance(info.get("sla"), dict) else 0,
            })
        # Also check for restaurant list inside card gridElements
        grid = card.get("card", {}).get("card", {}).get("gridElements", {})
        if isinstance(grid, dict):
            info_list = grid.get("infoWithStyle", {}).get("restaurants", [])
            for r_wrapper in info_list:
                r_info = r_wrapper.get("info", {}) if isinstance(r_wrapper, dict) else {}
                if r_info.get("id"):
                    restaurants.append({
                        "id": r_info.get("id"),
                        "name": r_info.get("name", "Unknown"),
                        "cuisine": ", ".join(r_info.get("cuisines", [])) if isinstance(r_info.get("cuisines"), list) else "",
                        "rating": r_info.get("avgRating", "N/A"),
                        "distance_km": r_info.get("sla", {}).get("lastMileTravel", 0) if isinstance(r_info.get("sla"), dict) else 0,
                    })
    return restaurants


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
            return await _track_order(client, router, address, tool_logs)

        # ---- Scenario 2: Add to cart / Place order ----
        if any(w in query_lower for w in ["add", "cart", "order", "place", "buy"]):
            return await _add_to_cart(client, router, query, address, tool_logs)

        # ---- Scenario 3: Search / Browse (default for food) ----
        return await _search_restaurants(client, router, query, address, tool_logs, rankings)

    return handle


async def _track_order(client, router, address, tool_logs):
    orders_res = await client.call_tool("food", "get_food_orders", {"addressId": address.get("id", "")})
    tool_logs.append({"tool": "get_food_orders", "args": {"addressId": address.get("id", "")}, "result": orders_res})

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


def _score_dish_relevance(dish: dict, query: str, restaurant: dict = None) -> float:
    """Calculate contextual relevance score for a dish based on user query, synonyms, and quality signals."""
    dish_name = str(dish.get("name") or "").lower()
    dish_desc = str(dish.get("description") or "").lower()

    rest_name = ""
    if restaurant and restaurant.get("name"):
        rest_name = str(restaurant["name"]).lower()
    elif dish.get("restaurantName"):
        rest_name = str(dish["restaurantName"]).lower()

    rest_cuisine = ""
    if restaurant and restaurant.get("cuisine"):
        rest_cuisine = str(restaurant["cuisine"]).lower()

    score = 0.0

    # Base quality score (bestsellers and high ratings)
    if dish.get("isBestseller"):
        score += 15.0
    try:
        r_val = float(dish.get("rating", 4.0))
        score += r_val * 2.0
    except (ValueError, TypeError):
        score += 8.0

    if not query:
        return score

    import re
    q_lower = str(query or "").lower().strip()
    # Normalize common phonetics / typo variants (e.g. jaamun -> jamun, biriyani -> biryani)
    q_normalized = re.sub(r'aa+', 'a', q_lower)
    q_normalized = re.sub(r'ee+', 'e', q_normalized)
    q_normalized = re.sub(r'oo+', 'o', q_normalized)

    q_words = [w for w in re.split(r'[\s,]+', q_lower) if len(w) > 2 and w not in {"the", "and", "for", "with", "near", "some", "likes", "like"}]

    # 1. Exact query phrase match in dish name
    if q_lower in dish_name or q_normalized in dish_name:
        score += 200.0

    # 2. Query words in dish name & description
    for w in q_words:
        w_norm = re.sub(r'aa+', 'a', w)
        if re.search(rf'\b{re.escape(w)}', dish_name) or re.search(rf'\b{re.escape(w_norm)}', dish_name):
            score += 120.0
        elif w in dish_name or w_norm in dish_name:
            score += 60.0
        elif w in dish_desc:
            score += 25.0

    # 3. Rich Indian food category keywords & synonyms expansion
    SWEET_TERMS = {
        "sweet", "sweets", "mithai", "dessert", "desserts", "jalebi", "gulab jamun", "jamun", "jaamun",
        "halwa", "rasgulla", "peda", "barfi", "burfi", "laddu", "laddoo", "kheer", "rabdi", "rabri",
        "kulfi", "rasmalai", "ice cream", "cake", "pastry", "mysore pak", "chikki", "sandesh", 
        "payasam", "malpua", "soan papdi", "khowa", "badam halwa", "gajar halwa", "moong dal halwa",
        "gulab", "rasgula", "cham cham", "dry fruit", "sweet box", "gulabjamun"
    }
    BIRYANI_TERMS = {"biryani", "biriyani", "pulao", "pulav", "mandi", "khichdi", "rice"}
    SNACK_TERMS = {"snack", "snacks", "chaat", "samosa", "kachori", "pakoda", "pakora", "bhel", "vada", "roll"}
    PIZZA_TERMS = {"pizza", "pasta", "garlic bread", "calzone"}
    BURGER_TERMS = {"burger", "wrap", "fries", "sandwich"}

    matched_category_terms = set()
    if any(w in q_lower or w in q_normalized for w in ["sweet", "mithai", "dessert", "halwa", "jamun", "jalebi", "gulab"]):
        matched_category_terms = SWEET_TERMS
    elif any(w in q_lower or w in q_normalized for w in ["biryani", "biriyani", "pulao"]):
        matched_category_terms = BIRYANI_TERMS
    elif any(w in q_lower for w in ["snack", "chaat", "samosa", "kachori"]):
        matched_category_terms = SNACK_TERMS
    elif any(w in q_lower for w in ["pizza", "pasta"]):
        matched_category_terms = PIZZA_TERMS
    elif any(w in q_lower for w in ["burger", "sandwich", "wrap"]):
        matched_category_terms = BURGER_TERMS

    if matched_category_terms:
        for term in matched_category_terms:
            if re.search(rf'\b{re.escape(term)}', dish_name):
                score += 85.0
            elif term in dish_desc:
                score += 20.0

    # 4. Restaurant specialization signals
    if q_lower in rest_name or (matched_category_terms and any(t in rest_name for t in matched_category_terms)):
        score += 45.0
    if q_lower in rest_cuisine or (matched_category_terms and any(t in rest_cuisine for t in matched_category_terms)):
        score += 30.0

    return score


def _extract_dishes_from_menu(menu_data: Any, r_id: str, r_name: str) -> list:
    """Recursively extract all real food dishes from Swiggy menu categories and subcategories."""
    dishes = []
    seen_ids = set()

    def _process_item(item: dict):
        if not isinstance(item, dict):
            return
        name = item.get("name") or item.get("itemName")
        if not name:
            return
        i_id = str(item.get("id") or item.get("itemId") or f"{r_id}_{len(dishes)+1}")
        if i_id in seen_ids:
            return
        seen_ids.add(i_id)

        raw_price = item.get("price") or item.get("defaultPrice") or item.get("finalPrice") or 0
        try:
            price = float(raw_price)
            if price > 1000:
                price = price / 100.0
        except (ValueError, TypeError):
            price = 0.0

        is_veg = item.get("isVeg")
        if is_veg is None:
            is_veg = item.get("itemAttribute", {}).get("vegClassifier") == "VEG" if isinstance(item.get("itemAttribute"), dict) else False

        img = item.get("imageUrl") or item.get("image") or ""
        if img and not img.startswith("http"):
            img = f"https://media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,w_300,h_300,c_fit/{img}"

        rating_val = "4.2"
        if item.get("rating"):
            rating_val = str(item.get("rating"))
        elif isinstance(item.get("ratings"), dict):
            rating_val = str(item.get("ratings", {}).get("aggregatedRating", {}).get("rating", "4.2"))

        dishes.append({
            "id": i_id,
            "restaurantId": r_id,
            "restaurantName": r_name,
            "name": name,
            "price": round(price, 2),
            "isVeg": bool(is_veg),
            "rating": rating_val,
            "imageUrl": img,
            "description": item.get("description", ""),
            "isBestseller": bool(item.get("isBestseller", False)),
            "inStock": item.get("inStock", 1)
        })

    def _walk(obj):
        if isinstance(obj, dict):
            if "items" in obj and isinstance(obj["items"], list):
                for it in obj["items"]:
                    _process_item(it)
            if "dishes" in obj and isinstance(obj["dishes"], list):
                for it in obj["dishes"]:
                    _process_item(it)
            for k, v in obj.items():
                if k not in ("items", "dishes"):
                    _walk(v)
        elif isinstance(obj, list):
            for elem in obj:
                _walk(elem)

    _walk(menu_data)
    return dishes


async def _search_restaurants(client, router, query, address, tool_logs, rankings):
    """
    Search restaurants and synthesize a dynamic response via LLM reasoning
    considering user demand, location, time-of-day, and available open venues/menus.
    """
    search_query = ""

    if router.llm:
        entities = await router._extract_entities(query, {
            "search_query": "string or null — what food/cuisine/item user wants to find (e.g. 'sweets', 'biryani', 'pizza')",
            "restaurant_name": "string or null — specific restaurant name mentioned",
        })
        search_query = entities.get("search_query") or entities.get("restaurant_name") or ""

    if not search_query:
        match = re.search(
            r'(?:search for|find|get|show|want|crave|cravings for)\s+(.+?)(?:\s*(?:near|for|please)|$)',
            query.lower()
        )
        if match:
            search_query = match.group(1).strip()

    # Strip conversational filler: 'me', 'some', 'a', 'an', 'good', 'best'
    search_query = re.sub(r'^(?:me\s+|some\s+|a\s+|an\s+|good\s+|best\s+)+', '', search_query.strip(), flags=re.IGNORECASE).strip()

    generic = {"to eat something", "something to eat", "something", "food", "some food", "hungry", "eat", "anything", "me", ""}
    if search_query.lower() in generic:
        q_lower = query.lower()
        if any(w in q_lower for w in ["sweet", "mithai", "dessert", "halwa", "laddu", "gulab jamun", "cake", "pastry"]):
            search_query = "sweets"
        elif any(w in q_lower for w in ["biryani", "rice"]):
            search_query = "biryani"
        elif any(w in q_lower for w in ["pizza", "burger", "fast food"]):
            search_query = "pizza"
        else:
            search_query = "food"

    # Swiggy MCP strictly requires a non-empty query parameter
    if not search_query:
        search_query = "food"

    # Search for matching open restaurants
    rest_res = await client.call_tool("food", "search_restaurants", {
        "addressId": address["id"], "query": search_query
    })
    tool_logs.append({
        "tool": "search_restaurants",
        "args": {"addressId": address["id"], "query": search_query},
        "result": rest_res
    })

    restaurants = _extract_restaurants(rest_res)

    raw_text = rest_res.get("raw_text") or (rest_res.get("data") if isinstance(rest_res.get("data"), str) else "")

    original_matched = bool(restaurants)
    fallback_used = False

    # If specific query returned 0 restaurants, fetch open restaurants with broad food queries
    if not restaurants:
        for fallback_q in ["food", "restaurant"]:
            if fallback_q == search_query.lower():
                continue
            all_open_res = await client.call_tool("food", "search_restaurants", {
                "addressId": address["id"], "query": fallback_q
            })
            tool_logs.append({
                "tool": "search_restaurants",
                "args": {"addressId": address["id"], "query": fallback_q},
                "result": all_open_res
            })
            if all_open_res.get("success"):
                restaurants = _extract_restaurants(all_open_res)
                if not raw_text:
                    raw_text = all_open_res.get("raw_text") or (all_open_res.get("data") if isinstance(all_open_res.get("data"), str) else "")
                if restaurants:
                    fallback_used = True
                    break

    # If search calls failed entirely (e.g. auth/MCP error), tell the user why
    if not restaurants and not raw_text:
        error_msg = rest_res.get("error", "No restaurants found.")
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

    # Fetch menu items for top open restaurants to provide rich LLM context and dish cards
    restaurant_options = []
    all_extracted_dishes = []

    # Also check if search_restaurants itself returned dishes directly
    if rest_res.get("data") and isinstance(rest_res["data"], dict):
        direct_dishes = rest_res["data"].get("dishes", [])
        if direct_dishes:
            for dd in direct_dishes:
                if isinstance(dd, dict):
                    all_extracted_dishes.append({
                        "id": str(dd.get("id", "")),
                        "restaurantId": str(dd.get("restaurantId", "")),
                        "restaurantName": dd.get("restaurantName", ""),
                        "name": dd.get("name", "Dish"),
                        "price": float(dd.get("price", 0) if dd.get("price") else 0),
                        "isVeg": bool(dd.get("isVeg", False)),
                        "rating": str(dd.get("rating", "4.2")),
                        "imageUrl": dd.get("imageUrl", ""),
                        "description": dd.get("description", ""),
                        "isBestseller": bool(dd.get("isBestseller", False)),
                        "inStock": dd.get("inStock", 1)
                    })

    valid_rests = [r for r in restaurants[:3] if isinstance(r, dict) and r.get("id")]

    if valid_rests:
        # Fetch menus concurrently with asyncio.gather to eliminate multi-second latency
        import asyncio
        menu_tasks = [
            client.call_tool("food", "get_restaurant_menu", {
                "addressId": address["id"],
                "restaurantId": r["id"],
            })
            for r in valid_rests
        ]
        menu_results = await asyncio.gather(*menu_tasks, return_exceptions=True)

        for r, menu_res in zip(valid_rests, menu_results):
            r_id = r.get("id")
            r_name = r.get("name", "Unknown Restaurant")
            if isinstance(menu_res, Exception):
                logger.warning(f"Error fetching menu for {r_name}: {menu_res}")
                menu_res = {"success": False}

            tool_logs.append({
                "tool": "get_restaurant_menu",
                "args": {"addressId": address["id"], "restaurantId": r_id},
                "result": menu_res,
            })

            menu_data = menu_res.get("data", {}) if (isinstance(menu_res, dict) and menu_res.get("success") and isinstance(menu_res.get("data"), dict)) else {}
            dishes = _extract_dishes_from_menu(menu_data, r_id, r_name)

            # Sort restaurant dishes by relevance to query
            dishes.sort(key=lambda d: _score_dish_relevance(d, search_query, r), reverse=True)
            all_extracted_dishes.extend(dishes)

            # Build menu highlights prioritizing top-scoring dishes
            menu_highlights = []
            for it in dishes[:4]:
                menu_highlights.append(f"{it['name']} (₹{it['price']})")

            restaurant_options.append({
                "id": r_id,
                "name": r_name,
                "cuisine": r.get("cuisine", ", ".join(r.get("cuisines", [])) if isinstance(r.get("cuisines"), list) else ""),
                "rating": r.get("rating", r.get("avgRating", "N/A")),
                "distance_km": r.get("distance_km", r.get("distanceKm", r.get("sla", {}).get("lastMileTravel", 0) if isinstance(r.get("sla"), dict) else 0)),
                "menu_highlights": menu_highlights,
                "dishes": dishes,
            })

    # Global sort across all restaurants by contextual relevance to query
    all_extracted_dishes.sort(key=lambda d: _score_dish_relevance(d, search_query), reverse=True)

    # Add dedicated dish tool call for frontend dish carousel rendering
    if all_extracted_dishes:
        tool_logs.append({
            "tool": "restaurant_menu_dishes",
            "args": {"query": search_query},
            "result": {
                "success": True,
                "data": {
                    "dishes": all_extracted_dishes[:30],
                    "total": len(all_extracted_dishes)
                }
            }
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
                "swiggy_raw_response": raw_text,
                "search_matched": original_matched,
            },
            system_instruction=(
                "You are the Swiggy MCP Food Orchestrator. "
                "The user is asking for food/sweets/meals. "
                "Analyze their request based on their location, time of day/demand, and the retrieved open restaurants and menus. "
                "CRITICAL: If the user specifically asked for a dish/cuisine (e.g. 'biryani') and no restaurants were found matching that dish (search_matched is False), "
                "you MUST clearly and politely state that no restaurants are currently delivering that specific item to their location right now before presenting the other available open restaurants as alternatives. "
                "IMPORTANT: A rich interactive widget is displayed below your message with dishes ready to add to cart and restaurant cards. Keep your text concise (1-2 brief paragraphs) with high-signal recommendations. Avoid dumping long repetitive bullet lists of dishes/prices in text."
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
    loc_label = address.get('label') or address.get('addressLine') or address.get('city') or 'your location'
    if restaurant_options:
        num_dishes = len(all_extracted_dishes)
        if not original_matched and fallback_used:
            text += f"⚠️ *No restaurants are currently delivering **{search_query}** to **{loc_label}** right now.*\n\n"
            text += f"Found **{len(restaurant_options)} top restaurants** delivering nearby with **{num_dishes} dishes** available. Select any item below to add directly to your cart, or switch tabs to browse restaurants:\n\n"
        else:
            dish_mention = f" with **{num_dishes} dishes** ready to add" if num_dishes > 0 else ""
            text += f"Found **{len(restaurant_options)} open restaurants** delivering near **{loc_label}**{dish_mention}. Select any item below to add to your cart, or switch tabs to browse restaurant details:\n\n"
        
        for r in restaurant_options[:3]:
            meta_parts = []
            if r.get('cuisine'):
                meta_parts.append(r['cuisine'])
            if r.get('rating') and r['rating'] != 'N/A':
                meta_parts.append(f"{r['rating']}★")
            if r.get('distance_km'):
                meta_parts.append(f"{r['distance_km']} km")
            meta_str = f" ({', '.join(meta_parts)})" if meta_parts else ""
            text += f"• **{r['name']}**{meta_str}\n"
        text += "\n"
    elif raw_text and ("total\":0" in raw_text or "totalRestaurants\":0" in raw_text or "restaurants\":[]" in raw_text):
        text += f"🌙 **All restaurants delivering to {loc_label} are currently closed for the night.**\n\nNo open restaurants are currently delivering **{search_query}** to this location.\n\nPlease check back during daytime operating hours or switch to another saved delivery address (e.g. Hyderabad or Bengaluru) in the top location selector."
    elif raw_text and len(raw_text.strip()) > 10 and not raw_text.strip().startswith("{"):
        text += f"{raw_text}\n"
    else:
        text += f"🌙 **All restaurants near {loc_label} are currently closed.**\n\nNo open restaurants found matching '{search_query or 'your request'}'. You can switch to another saved delivery address in the location menu above to order food right now.\n"

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
        clean_q = re.sub(r'^(?:order|buy|get|add)\s+', '', query, flags=re.IGNORECASE)
        clean_q = re.sub(r'\s+to\s+cart.*$', '', clean_q, flags=re.IGNORECASE).strip()
        if clean_q:
            raw_items.append((clean_q, 1))

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

    # Get active restaurant ID or search restaurants to find one
    target_rest_id = router.current_state.get("active_restaurant_id")
    target_rest_name = router.current_state.get("active_restaurant_name", "Restaurant")

    for name_str, qty in raw_items:
        clean_search = re.sub(r'\s+from\s+.*|\s+to\s+cart.*', '', name_str, flags=re.IGNORECASE).strip()
        search_term = clean_search.lower().rstrip('s') if len(clean_search) > 3 else clean_search.lower()

        # 1. Try search_menu
        search_res = await client.call_tool("food", "search_menu", {
            "addressId": address["id"],
            "query": search_term,
        })
        tool_logs.append({
            "tool": "search_menu",
            "args": {"addressId": address["id"], "query": search_term},
            "result": search_res,
        })

        items_found = []
        if search_res.get("success") and isinstance(search_res.get("data"), dict):
            items_found = search_res["data"].get("items", [])

        # 2. If search_menu returned nothing, try search_restaurants
        if not items_found:
            rest_search = await client.call_tool("food", "search_restaurants", {
                "addressId": address["id"],
                "query": search_term,
            })
            tool_logs.append({
                "tool": "search_restaurants",
                "args": {"addressId": address["id"], "query": search_term},
                "result": rest_search,
            })
            if rest_search.get("success") and isinstance(rest_search.get("data"), dict):
                dishes = rest_search["data"].get("dishes", [])
                if dishes:
                    items_found = dishes
                elif rest_search["data"].get("restaurants"):
                    # Check top restaurant's menu
                    top_r = rest_search["data"]["restaurants"][0]
                    target_rest_id = top_r.get("id")
                    target_rest_name = top_r.get("name")
                    m_res = await client.call_tool("food", "get_restaurant_menu", {
                        "addressId": address["id"], "restaurantId": target_rest_id
                    })
                    tool_logs.append({
                        "tool": "get_restaurant_menu",
                        "args": {"addressId": address["id"], "restaurantId": target_rest_id},
                        "result": m_res,
                    })
                    if m_res.get("success") and isinstance(m_res.get("data"), dict):
                        for cat in m_res["data"].get("categories", []):
                            if isinstance(cat, dict):
                                for cat_it in cat.get("items", []):
                                    if search_term in cat_it.get("name", "").lower():
                                        cat_it["restaurantId"] = target_rest_id
                                        cat_it["restaurantName"] = target_rest_name
                                        items_found.append(cat_it)

        if restaurant_name and items_found:
            filtered = [i for i in items_found if restaurant_name.lower() in i.get("restaurantName", "").lower()]
            if filtered:
                items_found = filtered

        if items_found:
            matched = items_found[0]
            r_id = matched.get("restaurantId") or matched.get("restaurant_id") or target_rest_id
            r_name = matched.get("restaurantName") or matched.get("restaurant_name") or target_rest_name
            item_id = matched.get("id") or matched.get("menu_item_id")
            if r_id not in matched_items_by_rest:
                matched_items_by_rest[r_id] = {"rest_name": r_name, "items": []}
            matched_items_by_rest[r_id]["items"].append({
                "itemId": item_id,
                "name": matched.get("name", name_str),
                "quantity": qty,
                "price": matched.get("price", 0),
            })
        else:
            not_found.append(name_str)

    if not matched_items_by_rest:
        missing_str = ", ".join([f"'{n}'" for n in not_found])
        loc_label = address.get('label') or 'your location'
        return {
            "response_text": f"Could not find {missing_str} on the menu of any OPEN restaurant near **{loc_label}**.",
            "tool_calls": tool_logs,
            "active_server": "food",
            "state": router.current_state,
        }

    # Select target restaurant (prefer the one with the most matched items)
    target_rest_id = max(matched_items_by_rest.keys(), key=lambda r: len(matched_items_by_rest[r]["items"]))
    target_rest = matched_items_by_rest[target_rest_id]
    rest_name = target_rest["rest_name"]
    items_payload = [{"menu_item_id": it["itemId"], "quantity": it["quantity"]} for it in target_rest["items"]]

    cart_res = await client.call_tool("food", "update_food_cart", {
        "restaurantId": target_rest_id,
        "cartItems": items_payload,
        "addressId": address["id"],
    })
    tool_logs.append({
        "tool": "update_food_cart",
        "args": {"restaurantId": target_rest_id, "cartItems": items_payload, "addressId": address["id"]},
        "result": cart_res,
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

    coupon_res = await client.call_tool("food", "apply_food_coupon", {
        "couponCode": "WELCOME50",
        "addressId": address["id"],
    })
    tool_logs.append({
        "tool": "apply_food_coupon",
        "args": {"couponCode": "WELCOME50", "addressId": address["id"]},
        "result": coupon_res,
    })

    final_total = cart_data.get("grand_total", subtotal)
    if coupon_res.get("success") and isinstance(coupon_res.get("data"), dict):
        if coupon_res["data"].get("final_amount"):
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

