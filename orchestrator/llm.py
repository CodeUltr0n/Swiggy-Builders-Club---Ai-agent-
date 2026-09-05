"""
Lightweight LLM client for Groq / Gemini / xAI (Grok) models.
Supports automatic failover between providers (e.g. Groq -> Gemini fallback on rate limits or errors).
Used for intent classification, entity extraction, and dynamic contextual reasoning.
"""

import json
import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified client supporting Groq, Gemini, and xAI (Grok) backends with automatic failover."""

    def __init__(self, provider: str = "groq", model: str = None, api_key: str = None, fallback_provider: str = "gemini"):
        self.provider = provider.lower()
        self.model = model or self._default_model(self.provider)
        self.api_key = api_key or self._default_api_key(self.provider)
        self.base_url = self._get_base_url(self.provider)

        # Automatic Failover Config
        self.fallback_provider = fallback_provider.lower() if fallback_provider else "gemini"
        if self.fallback_provider == self.provider:
            self.fallback_provider = "gemini" if self.provider != "gemini" else "groq"
            
        self.fallback_model = self._default_model(self.fallback_provider)
        self.fallback_api_key = self._default_api_key(self.fallback_provider)
        self.fallback_base_url = self._get_base_url(self.fallback_provider)

    def _default_model(self, provider_name: str) -> str:
        if provider_name == "groq":
            return os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")
        elif provider_name in ("gemini", "google"):
            return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        elif provider_name in ("xai", "grok"):
            return os.getenv("GROK_MODEL", "grok-3-mini")
        return "qwen/qwen3.6-27b"

    def _default_api_key(self, provider_name: str) -> str:
        if provider_name == "groq":
            return os.getenv("GROQ_API_KEY", "")
        elif provider_name in ("gemini", "google"):
            return os.getenv("GEMINI_API_KEY", "")
        elif provider_name in ("xai", "grok"):
            return os.getenv("XAI_API_KEY", "")
        return ""

    def _get_base_url(self, provider_name: str) -> str:
        if provider_name == "groq":
            return "https://api.groq.com/openai/v1"
        elif provider_name in ("gemini", "google"):
            return "https://generativelanguage.googleapis.com/v1beta/openai"
        elif provider_name in ("xai", "grok"):
            return "https://api.x.ai/v1"
        return "https://api.groq.com/openai/v1"

    async def classify(
        self,
        query: str,
        options: list[str],
        context: str = "",
        system_prompt: str = "",
    ) -> dict:
        """
        Classify a query into one of the given options.
        Returns {"label": str, "reasoning": str, "confidence": float}.
        """
        if not self.api_key and not self.fallback_api_key:
            return {"label": options[0], "reasoning": "No API key configured", "confidence": 0.0}

        options_str = ", ".join(options)

        if not system_prompt:
            system_prompt = (
                "You are an intent classifier for Swiggy's multi-service platform. "
                "Classify the user's query into exactly ONE option.\n\n"
                "SERVICE DEFINITIONS:\n"
                "- food: Ordering PREPARED meals, dishes, desserts, sweets, cakes, ice cream, or any cooked/ready-to-eat items from RESTAURANTS. "
                "  Examples: 'something sweet', 'biryani', 'pizza', 'cake', 'dessert', 'ice cream', 'hungry', 'want to eat', 'lunch', 'dinner'.\n"
                "- instamart: Buying RAW INGREDIENTS, packaged goods, household essentials from a GROCERY store. "
                "  Examples: 'milk', 'eggs', 'sugar', 'detergent', 'vegetables', 'atta', 'cooking oil'.\n"
                "- dineout: RESERVING a TABLE at a restaurant to eat there in person. "
                "  Examples: 'book a table', 'restaurant reservation', 'dine out tonight', 'fine dining'.\n\n"
                "IMPORTANT: If the user wants to EAT something (sweet, spicy, etc.), classify as 'food'. "
                "Only classify as 'instamart' if they want to BUY raw/packaged grocery items.\n\n"
                "Return ONLY valid JSON: {\"label\": \"<option>\", \"reasoning\": \"<why>\", \"confidence\": <0.0-1.0>}. "
                "No markdown, no explanation, just JSON."
            )

        user_msg = f"Options: [{options_str}]\nQuery: \"{query}\""
        if context:
            user_msg += f"\nContext: {context}"

        response = await self._call(system_prompt, user_msg, max_tokens=120, temperature=0.1)
        return self._parse_classification(response, options)

    async def extract_entities(self, query: str, schema: dict) -> dict:
        """
        Extract structured entities from a query based on a JSON schema description.
        Returns a dict matching the requested keys.
        """
        if not self.api_key and not self.fallback_api_key:
            return {}

        schema_desc = json.dumps(schema, indent=2)

        system_prompt = (
            "You are an entity extractor. Extract structured data from the user's food/grocery/dining query. "
            "Return ONLY valid JSON with the exact keys requested. Use null for missing values. "
            "No markdown, no explanation, just JSON."
        )

        user_msg = f"Extract from: \"{query}\"\nSchema:\n{schema_desc}"

        response = await self._call(system_prompt, user_msg, max_tokens=150, temperature=0.0)
        return self._parse_json(response)

    async def generate_response(
        self,
        query: str,
        context: dict,
        data: dict,
        system_instruction: str = "",
    ) -> str:
        """
        Generate a dynamic, reasoned response evaluating the user query against
        location, demand context, and available server/restaurant options.
        """
        if not self.api_key and not self.fallback_api_key:
            return ""

        if not system_instruction:
            system_instruction = (
                "You are an AI assistant for Swiggy MCP Orchestrator. "
                "Analyze the user's request in light of their location, current demand/time of day, "
                "and the retrieved real-time options from the servers. "
                "Provide a helpful, friendly, and well-reasoned response guiding the user on what is available, "
                "why, and how to proceed (e.g. order, book, or search)."
            )

        context_str = json.dumps(context, indent=2)
        data_str = json.dumps(data, indent=2)

        user_msg = (
            f"User Query: \"{query}\"\n\n"
            f"User Context (Location & Time & Demand):\n{context_str}\n\n"
            f"Retrieved Server Options & Menus:\n{data_str}\n"
        )

        return await self._call(system_instruction, user_msg, max_tokens=350, temperature=0.3)

    async def _call(self, system: str, user: str, max_tokens: int = 100, temperature: float = 0.1) -> str:
        """Make the actual API call with automatic provider failover."""
        # Attempt Primary Provider first
        if self.api_key:
            try:
                return await self._execute_http_call(
                    self.base_url, self.model, self.api_key, system, user, max_tokens, temperature
                )
            except Exception as e:
                logger.warning(
                    f"Primary LLM call ({self.provider}/{self.model}) failed: {e}. "
                    f"Attempting failover to secondary provider ({self.fallback_provider}/{self.fallback_model})..."
                )

        # Attempt Fallback Provider if primary failed or primary key is missing
        if self.fallback_api_key:
            try:
                return await self._execute_http_call(
                    self.fallback_base_url, self.fallback_model, self.fallback_api_key, system, user, max_tokens, temperature
                )
            except Exception as fallback_err:
                logger.error(f"Fallback LLM call ({self.fallback_provider}/{self.fallback_model}) also failed: {fallback_err}")
                raise fallback_err

        raise RuntimeError("No valid LLM API key or active provider connection available.")

    async def _execute_http_call(
        self, base_url: str, model: str, api_key: str, system: str, user: str, max_tokens: int, temperature: float
    ) -> str:
        """Execute HTTP request to OpenAI-compatible endpoint."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            if "<think>" in content:
                import re
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content

    def _parse_classification(self, raw: str, options: list[str]) -> dict:
        """Parse and validate LLM classification response."""
        parsed = self._parse_json(raw)
        label = parsed.get("label", "")
        for opt in options:
            if opt.lower() in label.lower():
                label = opt
                break
        else:
            label = options[0]

        return {
            "label": label,
            "reasoning": parsed.get("reasoning", ""),
            "confidence": min(max(parsed.get("confidence", 0.5), 0.0), 1.0),
        }

    def _parse_json(self, raw: str) -> dict:
        """Robust JSON parsing from LLM output."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {}
