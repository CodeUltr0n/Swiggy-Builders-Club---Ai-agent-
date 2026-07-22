"""
Orchestrator initialization factory.

Wires MemoryManager, LLMClient, ContextPrioritizer, OrchestratorRouter, and Plugin Registrars.
"""

import logging
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from orchestrator.memory import MemoryManager
from orchestrator.llm import LLMClient
from orchestrator.prioritizer import ContextPrioritizer
from orchestrator.router import OrchestratorRouter
from orchestrator.client import SwiggyMCPClient

logger = logging.getLogger(__name__)


def create_orchestrator(config_path: str = None) -> OrchestratorRouter:
    """
    Build and return a fully-wired OrchestratorRouter.

    Reads settings from config/settings.yaml for:
      - LLM provider and model selection
      - Database path
    """
    config_path = config_path or str(Path(__file__).parent.parent / "config" / "settings.yaml")
    with open(config_path) as f:
        raw_settings = yaml.safe_load(f)

    # Allow nested or top-level settings
    settings = raw_settings.get("settings", raw_settings)
    llm_config = raw_settings.get("llm", settings.get("llm", {}))
    db_path = settings.get("database_path", raw_settings.get("db_path", "orchestrator.db"))

    # 1. Memory & Client
    memory = MemoryManager(db_path=db_path)
    client = SwiggyMCPClient(memory)

    # 2. LLM Client
    llm = None
    if llm_config.get("enabled", True):
        provider = llm_config.get("provider", "groq")
        model = llm_config.get("model")
        api_key = llm_config.get("api_key")
        llm = LLMClient(provider=provider, model=model, api_key=api_key)
        logger.info(f"LLM initialized: {llm.provider}/{llm.model}")

    # 3. Prioritizer
    weights_path = str(Path(__file__).parent.parent / "config" / "weights.yaml")
    prioritizer = ContextPrioritizer(
        memory_manager=memory,
        config_path=weights_path,
        llm_client=llm,
    )

    # 4. Router
    router = OrchestratorRouter(
        client=client,
        prioritizer=prioritizer,
        llm=llm,
    )

    # 5. Register Domain Handlers
    register_plugins(router, client)

    return router


def register_plugins(router: OrchestratorRouter, client):
    """Register all domain handlers with the OrchestratorRouter."""
    from orchestrator.plugins.handlers.food_handler import register as reg_food
    from orchestrator.plugins.handlers.instamart_handler import register as reg_instamart
    from orchestrator.plugins.handlers.dineout_handler import register as reg_dineout

    reg_food(router, client)
    reg_instamart(router, client)
    reg_dineout(router, client)

    logger.info(f"All plugins registered. Active handlers: {list(router._handlers.keys())}")
