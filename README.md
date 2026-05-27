# MCP Orchestrator

> A pluggable orchestration layer that sits across multiple MCP servers and prioritizes real-world tasks based on context.

[![MCP](https://img.shields.io/badge/MCP-Protocol-blue)](https://modelcontextprotocol.io/)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://python.org)
[![Status](https://img.shields.io/badge/Status-WIP-orange)]()
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

## The Problem

Most people building on MCP servers create one agent per server — Food agent here, Instamart agent there, Dineout agent somewhere else. Context gets lost between them. No shared memory. No prioritization. Token overhead everywhere.

## The Solution

MCP Orchestrator flips the model. Instead of "how do I call this API?", it asks **"what should I do right now?"**

One layer. Multiple MCP servers. Smart prioritization based on:

- Time of day
- User location
- Past behavior and order history
- Active goals and urgency

The LLM handles reasoning and conversation. State management stays lightweight. Token costs stay low.

## Architecture

```
┌─────────────────────────────────────┐
│           User / AI Agent           │
└──────────────┬──────────────────────┘
               │
     ┌─────────▼─────────┐
     │   Prioritization   │
     │      Engine        │
     │  (context-aware    │
     │   task scoring)    │
     └─────────┬─────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐ ┌───▼───┐ ┌───▼───┐
│ Swiggy│ │Swiggy │ │Swiggy │
│ Food  │ │Insta- │ │Dineout│
│ MCP   │ │mart   │ │ MCP   │
│Server │ │ MCP   │ │Server │
│       │ │Server │ │       │
└───────┘ └───────┘ └───────┘
```

## Core Components

- **MCP Client Layer** — Connects to multiple Swiggy MCP servers via Model Context Protocol
- **Prioritization Engine** — Scores and ranks tasks using context signals
- **Persistent Memory** — Stores user preferences, order history, learned skills across sessions
- **Plugin System** — Register new MCP servers without changing orchestration logic

## Status

This project is in early development. Waiting on Swiggy Builder's Club API access to start building the integration layer.

## Planned Features

- [ ] MCP client connection to Swiggy Food, Instamart, Dineout servers
- [ ] Context-aware prioritization engine
- [ ] Persistent user memory and preference learning
- [ ] Pluggable server registration system
- [ ] Natural language interface via LLM reasoning

## Tech Stack

- **Language:** Python 3.11+
- **Protocol:** Model Context Protocol (MCP)
- **LLM:** Pluggable (OpenAI, Anthropic, local models)
- **Storage:** Lightweight persistent memory (SQLite / JSON)

## Getting Started

> Coming soon — waiting on MCP API credentials.

## License

MIT

---

*Built for the Swiggy Builder's Club Developer Program*
