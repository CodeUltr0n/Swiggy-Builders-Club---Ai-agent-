"""Simple prioritization engine skeleton."""
from typing import Dict, Any


class Prioritizer:
    """Scores tasks based on a few context signals (placeholder)."""

    def score(self, task: Dict[str, Any], context: Dict[str, Any]) -> float:
        # Very small heuristic: higher urgency and recency increase score
        urgency = float(task.get("urgency", 1.0))
        recency = float(context.get("recency_hours", 24))
        score = urgency / max(1.0, recency)
        return score
