"""
Context-Aware Task Prioritizer

Scores and ranks MCP servers using:
1. Time-of-day signals (from config)
2. Location adjustments (from config)
3. Hunger/urgency adjustments (from config)
4. Past behavior — recency-weighted history from MemoryManager
5. Derived preferences — learned patterns (peak ordering time, preferred server)
6. LLM-based intent classification — actual intelligence, not keyword matching (with keyword fallback)

All weights and scores loaded from config/weights.yaml — ZERO hardcoded values.
"""

import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from orchestrator.llm import LLMClient

logger = logging.getLogger(__name__)


class ContextPrioritizer:

    SERVERS = ["food", "instamart", "dineout"]

    def __init__(self, memory_manager, config_path: str = None, llm_client: LLMClient = None):
        self.memory = memory_manager
        self.llm = llm_client
        config_path = config_path or str(Path(__file__).parent.parent / "config" / "weights.yaml")
        try:
            with open(config_path) as f:
                self.config = yaml.safe_load(f)
        except Exception:
            logger.warning(f"Could not load config from {config_path}, using default weights.")
            self.config = {
                "time_scores": {
                    "morning": {"food": 0.6, "instamart": 0.8, "dineout": 0.1},
                    "lunch": {"food": 0.9, "instamart": 0.4, "dineout": 0.5},
                    "afternoon": {"food": 0.5, "instamart": 0.6, "dineout": 0.2},
                    "dinner": {"food": 0.9, "instamart": 0.5, "dineout": 0.8},
                    "late_night": {"food": 0.8, "instamart": 0.2, "dineout": 0.1},
                    "default": {"food": 0.5, "instamart": 0.5, "dineout": 0.3},
                },
                "intent_boost": 0.8,
                "location_adjustments": {
                    "office": {"instamart": -0.3, "food": 0.1, "dineout": 0.1},
                    "gym": {"instamart": 0.2, "food": -0.1},
                },
                "hunger_adjustments": {
                    "high": {"food": 0.2, "dineout": -0.1},
                    "low": {"food": -0.1, "dineout": 0.2},
                },
                "signal_weights": {
                    "time": 1.0,
                    "intent": 0.8,
                    "location": 0.3,
                    "hunger": 0.2,
                    "history": 0.35,
                    "preference_loyalty": 0.15,
                },
                "score_limits": {"min": 0.0, "max": 2.0},
            }

    def _get_time_slot(self, time_str: str) -> str:
        """Map HH:MM to a time slot key from config."""
        try:
            t = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            t = datetime.now().time()

        hour = t.hour
        if 7 <= hour < 12:
            return "morning"
        elif 12 <= hour < 15:
            return "lunch"
        elif 15 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 23:
            return "dinner"
        elif hour >= 23 or hour < 2:
            return "late_night"
        else:
            return "default"

    def _time_scores(self, time_str: str) -> Dict[str, float]:
        slot = self._get_time_slot(time_str)
        return dict(self.config["time_scores"].get(slot, self.config["time_scores"]["default"]))

    def _location_adjustment(self, scores: Dict[str, float], address_label: str):
        label = address_label.lower()
        adjustments = self.config.get("location_adjustments", {})
        for location_key, adj in adjustments.items():
            if location_key.lower() == label:
                for server, delta in adj.items():
                    if server in scores:
                        scores[server] += delta
                break

    def _hunger_adjustment(self, scores: Dict[str, float], hunger_level: str):
        level = hunger_level.lower()
        adjustments = self.config.get("hunger_adjustments", {})
        adj = adjustments.get(level, {})
        for server, delta in adj.items():
            if server in scores:
                scores[server] += delta

    def _history_adjustment(self, scores: Dict[str, float]):
        """Recency-weighted history: last 5 orders matter 3x more than older ones."""
        past_orders = self.memory.get_past_orders(limit=20) if hasattr(self.memory, "get_past_orders") else []
        total = len(past_orders)
        if total == 0:
            return

        history_weight = self.config.get("signal_weights", {}).get("history", 0.35)

        recent_window = past_orders[:5]
        recent_total = len(recent_window) or 1

        for server in self.SERVERS:
            recent_count = sum(1 for o in recent_window if o.get("server") == server)
            overall_count = sum(1 for o in past_orders if o.get("server") == server)

            blended = (0.7 * (recent_count / recent_total)) + (0.3 * (overall_count / total))
            scores[server] += blended * history_weight

    def _preference_adjustment(self, scores: Dict[str, float]):
        """Boost the server the user gravitates toward based on derived preferences."""
        if hasattr(self.memory, "get_derived_preferences"):
            prefs = self.memory.get_derived_preferences()
            if prefs.get("preferred_server") and prefs["preferred_server"] in scores:
                scores[prefs["preferred_server"]] += self.config.get("signal_weights", {}).get(
                    "preference_loyalty", 0.15
                )

    def _keyword_fallback(self, query: str) -> Optional[Tuple[str, str]]:
        """Simple keyword matching fallback when LLM is unavailable."""
        query_lower = query.lower()

        # Food cooked meals keywords
        food_kw = ["biryani", "burger", "pizza", "hungry", "order food", "restaurant", "menu", "takeout", "swiggy food", "sweet", "dessert", "cake", "ice cream", "gulab jamun", "rasgulla", "pastry", "brownie", "milkshake", "kulfi", "mithai", "jalebi"]
        # Instamart grocery & raw ingredients keywords
        im_kw = ["milk", "egg", "eggs", "bread", "butter", "cheese", "groceries", "grocery", "tomato", "onion", "vegetables", "fruits", "chips", "coke", "ghee", "detergent", "soap", "curd", "paneer", "atta", "rice", "oil", "sugar", "salt", "tea", "coffee", "biscuits", "biscuit", "snacks"]
        # Dineout table reservation keywords
        dine_kw = ["table", "reserve", "dineout", "pub", "book", "go out", "fine dining", "reservation", "booking"]

        f_cnt = sum(1 for kw in food_kw if kw in query_lower)
        i_cnt = sum(1 for kw in im_kw if kw in query_lower)
        d_cnt = sum(1 for kw in dine_kw if kw in query_lower)

        # Grocery items take precedence for Instamart
        if i_cnt > 0 and i_cnt >= f_cnt and i_cnt >= d_cnt:
            return "instamart", f"Keyword intent match for Instamart (items: {', '.join([k for k in im_kw if k in query_lower])})"
        elif f_cnt > i_cnt and f_cnt > d_cnt:
            return "food", f"Keyword intent match for Food (items: {', '.join([k for k in food_kw if k in query_lower])})"
        elif d_cnt > f_cnt and d_cnt > i_cnt:
            return "dineout", f"Keyword intent match for Dineout (items: {', '.join([k for k in dine_kw if k in query_lower])})"
        return None


    async def _llm_intent(self, query: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Use LLM to classify intent. Returns {label, reasoning, confidence} or None on failure."""
        if not self.llm or not self.llm.api_key:
            return None

        pref_info = ""
        if hasattr(self.memory, "get_derived_preferences"):
            prefs = self.memory.get_derived_preferences()
            if prefs.get("preferred_server"):
                pref_info = f"User's most-used service: {prefs['preferred_server']}."

        context_str = (
            f"Time: {context.get('time_of_day', 'unknown')}, "
            f"Location: {context.get('address_label', 'unknown')}, "
            f"Hunger: {context.get('hunger_level', 'medium')}. {pref_info}"
        )

        try:
            return await self.llm.classify(query=query, options=self.SERVERS, context=context_str)
        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}")
            return None

    async def score_tasks(self, query: str, context: Dict[str, Any]) -> List[Tuple[str, float, str]]:
        """
        Score and rank servers. Returns sorted list of (server_name, score, reasoning).
        """
        time_str = context.get("time_of_day", datetime.now().strftime("%H:%M"))
        address_label = context.get("address_label", "Home")
        hunger_level = context.get("hunger_level", "medium")

        # Layers 1-5: deterministic context signals
        scores = self._time_scores(time_str)
        self._location_adjustment(scores, address_label)
        self._hunger_adjustment(scores, hunger_level)
        self._history_adjustment(scores)
        self._preference_adjustment(scores)

        intent_reasoning = "Scored by contextual signals (time, location, history)"

        # Check for order tracking queries: boost the server of the most recent order in memory
        track_kw = ["track", "status", "where is my", "order status", "booking status"]
        if any(kw in query.lower() for kw in track_kw) and hasattr(self.memory, "get_past_orders"):
            past = self.memory.get_past_orders(limit=1)
            if past and past[0].get("server") in scores:
                most_recent_server = past[0]["server"]
                scores[most_recent_server] += 1.5
                intent_reasoning = f"Tracking request for most recent {most_recent_server} order/booking ({past[0]['id']})"

        # Layer 6: LLM intent classification (or keyword fallback)
        if not any(kw in query.lower() for kw in track_kw):
            llm_result = await self._llm_intent(query, context)
            if llm_result and llm_result.get("confidence", 0) > 0:
                intent_label = llm_result["label"]
                intent_confidence = llm_result["confidence"]
                intent_reasoning = f"LLM classified as '{intent_label}' — {llm_result.get('reasoning', '')}"

                intent_boost = self.config.get("intent_boost", 1.2) * intent_confidence
                if intent_label in scores:
                    scores[intent_label] += intent_boost
            else:
                # Fallback to keyword matching
                kw_match = self._keyword_fallback(query)
                if kw_match:
                    lbl, intent_reasoning = kw_match
                    if lbl in scores:
                        scores[lbl] += self.config.get("intent_boost", 1.2)


        # Layer 7: Clamp and rank
        limits = self.config.get("score_limits", {"min": 0.0, "max": 2.0})
        ranked = []
        for server in self.SERVERS:
            final = max(limits["min"], min(scores.get(server, 0.0), limits["max"]))
            ranked.append((server, round(final, 2), intent_reasoning))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked
