"""MCP Orchestrator — Pluggable orchestration layer for Swiggy MCP servers."""

# Simulation client (CLI, local dev)
from orchestrator.client import SwiggyMCPClient

# Real MCP client (Streamable HTTP, production)
from orchestrator.client import MCPClient, MCPError, MCPConnectionError

# Core services
from orchestrator.prioritizer import ContextPrioritizer
from orchestrator.router import OrchestratorRouter
from orchestrator.memory import MemoryManager
from orchestrator.oauth import SwiggyOAuthClient

__all__ = [
    "SwiggyMCPClient",
    "MCPClient",
    "MCPError",
    "MCPConnectionError",
    "ContextPrioritizer",
    "OrchestratorRouter",
    "MemoryManager",
    "SwiggyOAuthClient",
]
