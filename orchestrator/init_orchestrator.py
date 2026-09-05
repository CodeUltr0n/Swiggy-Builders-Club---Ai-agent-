"""
Orchestrator initialization factory.

Wires MemoryManager, LLMClient, ContextPrioritizer, OrchestratorRouter,
and Plugin Registrars. Supports both simulation mode (SwiggyMCPClient)
and real MCP mode (MCPClient + OAuth).
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
from orchestrator.client import SwiggyMCPClient, MCPClient

logger = logging.getLogger(__name__)


def create_orchestrator(
    config_path: str = None,
    oauth_client=None,
) -> OrchestratorRouter:
    """
    Build and return a fully-wired OrchestratorRouter.

    Args:
        config_path: Path to settings.yaml
        oauth_client: SwiggyOAuthClient instance. If provided, creates a real
                      MCPClient for Streamable HTTP calls. If None, falls back
                      to SwiggyMCPClient (simulation mode).

    Reads settings from config/settings.yaml for:
      - LLM provider and model selection
      - MCP server URLs
      - Database path
    """
    config_path = config_path or str(Path(__file__).parent.parent / "config" / "settings.yaml")
    with open(config_path) as f:
        raw_settings = yaml.safe_load(f)

    # Allow nested or top-level settings
    settings = raw_settings.get("settings", raw_settings)
    llm_config = raw_settings.get("llm", settings.get("llm", {}))
    db_path = settings.get("database_path", raw_settings.get("db_path", "orchestrator.db"))

    # 1. Memory
    memory = MemoryManager(db_path=db_path)

    # 2. Simulation Client (always available — CLI and handlers use this)
    sim_client = SwiggyMCPClient(memory)

    # 3. Real MCP Client (only if OAuth is available)
    mcp_client = None
    if oauth_client:
        mcp_servers = raw_settings.get("mcp_servers", {})
        mcp_client = MCPClient(
            oauth_client=oauth_client,
            server_urls=mcp_servers if mcp_servers else None,
            memory_manager=memory,
        )
        logger.info("Real MCP client created (Streamable HTTP)")
    else:
        logger.info("No OAuth client provided — using simulation mode only")

    # 4. LLM Client
    llm = None
    if llm_config.get("enabled", True):
        provider = llm_config.get("provider", "groq")
        model = llm_config.get("model")
        api_key = llm_config.get("api_key")
        llm = LLMClient(provider=provider, model=model, api_key=api_key)
        logger.info(f"LLM initialized: {llm.provider}/{llm.model}")

    # 5. Prioritizer
    weights_path = str(Path(__file__).parent.parent / "config" / "weights.yaml")
    prioritizer = ContextPrioritizer(
        memory_manager=memory,
        config_path=weights_path,
        llm_client=llm,
    )

    # 6. Router — uses correct client based on env_mode
    active_client = mcp_client if (mcp_client and settings.get("env_mode") == "production") else sim_client

    router = OrchestratorRouter(
        client=active_client,
        prioritizer=prioritizer,
        llm=llm,
    )

    # Attach the real MCP client for server.py to use
    router.mcp_client = mcp_client

    # 7. Register Domain Handlers (correct import paths)
    register_plugins(router, active_client)

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
