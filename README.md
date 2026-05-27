<div align="center">

# MCP Orchestrator

**A pluggable orchestration layer that sits across multiple MCP servers and prioritizes real-world tasks based on context.**

<br>

[![MCP](https://img.shields.io/badge/Protocol-MCP-blue?style=for-the-badge&logo=chainlink&logoColor=white)](https://modelcontextprotocol.io/)
[![Python](https://img.shields.io/badge/Python-3.11+-green?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Status](https://img.shields.io/badge/Status-WIP-orange?style=for-the-badge)]()
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)]()
[![Swiggy](https://img.shields.io/badge/Swiggy-Builder's_Club-FC8019?style=for-the-badge&logo=swiggy&logoColor=white)](https://mcp.swiggy.com/builders/)

<br>

<!-- Add demo video / screenshot here -->

</div>

---

## Why This Exists

Most builders on MCP create **one agent per server** — a Food agent, an Instamart agent, a Dineout agent. Context gets siloed. No shared memory. Token overhead everywhere.

MCP Orchestrator flips the model.

Instead of asking **"how do I call this API?"**, it asks **"what should I do right now?"**

One layer. Multiple MCP servers. Smart prioritization. Low overhead.

---

## Architecture

```
                         ┌──────────────────────┐
                         │    User / AI Agent    │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │   Prioritization     │
                         │      Engine          │
                         │                      │
                         │  • Time of day       │
                         │  • Location          │
                         │  • Past behavior     │
                         │  • Active goals      │
                         │  • Urgency scoring   │
                         └──────────┬───────────┘
                                    │
                   ┌────────────────┼────────────────┐
                   │                │                │
          ┌────────▼────────┐ ┌────▼────────┐ ┌────▼────────┐
          │   Swiggy Food   │ │  Swiggy     │ │  Swiggy     │
          │   MCP Server    │ │  Instamart  │ │  Dineout    │
          │                 │ │  MCP Server │ │  MCP Server │
          │  • Search       │ │             │ │             │
          │  • Order        │ │  • Browse   │ │  • Discover │
          │  • Track        │ │  • Cart     │ │  • Reserve  │
          │  • History      │ │  • Delivery │ │  • Reviews  │
          └─────────────────┘ └─────────────┘ └─────────────┘
```

---

## Core Components

| Component | Description |
|-----------|-------------|
| **MCP Client Layer** | Connects to multiple Swiggy MCP servers via Model Context Protocol |
| **Prioritization Engine** | Scores and ranks tasks using context signals — time, location, history, urgency |
| **Persistent Memory** | Stores user preferences, order history, and learned skills across sessions |
| **Plugin System** | Register new MCP servers without changing orchestration logic |
| **LLM Reasoning** | Handles natural language interaction — not state management, keeping token costs low |

---

## Key Features

- **Context-Aware Prioritization** — Knows what matters right now, not just what was asked
- **Pluggable Server Architecture** — Add new MCP servers by registering them, zero orchestration changes
- **Persistent Memory** — Learns your preferences over time across sessions
- **Low Token Overhead** — LLM handles reasoning only, state stays lightweight
- **Multi-Server Routing** — One conversation can span Food, Instamart, and Dineout seamlessly

---

## Tech Stack

<table>
<tr>
<td><strong>Language</strong></td><td>Python 3.11+</td>
</tr>
<tr>
<td><strong>Protocol</strong></td><td>Model Context Protocol (MCP)</td>
</tr>
<tr>
<td><strong>LLM</strong></td><td>Pluggable — OpenAI, Anthropic, local models</td>
</tr>
<tr>
<td><strong>Storage</strong></td><td>SQLite / JSON for persistent memory</td>
</tr>
<tr>
<td><strong>Platform</strong></td><td>Swiggy MCP Servers (Food, Instamart, Dineout)</td>
</tr>
</table>

---

## Planned Project Structure

Once API access is available, the project will be organized as follows:

```
mcp-orchestrator/
├── orchestrator/
│   ├── __init__.py
│   ├── client.py          # MCP client connections
│   ├── prioritizer.py     # Context-aware task scoring engine
│   ├── memory.py          # Persistent user memory & preferences
│   ├── router.py          # Multi-server task routing
│   └── plugins/           # Pluggable MCP server registrations
│       ├── __init__.py
│       ├── food.py
│       ├── instamart.py
│       └── dineout.py
├── config/
│   ├── servers.yaml       # MCP server configurations
│   └── settings.yaml      # App settings
├── tests/
├── requirements.txt
└── README.md
```

> This is the proposed architecture. Structure may evolve as development progresses.

---

## Getting Started

> **Status:** Waiting on Swiggy Builder's Club API access to begin integration.

### Prerequisites

- Python 3.11+
- Swiggy MCP API credentials (via [Builder's Club](https://mcp.swiggy.com/builders/))
- LLM API key (OpenAI / Anthropic / local model)

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/mcp-orchestrator.git
cd mcp-orchestrator
pip install -r requirements.txt
```

### Configuration

```bash
cp config/servers.yaml.example config/servers.yaml
# Add your MCP server credentials and LLM API keys
```

### Run

```bash
python -m orchestrator
```

---

## How It Works

1. **You say something** — "I'm hungry" or "Need groceries for dinner"
2. **Orchestrator reads context** — It's 7 PM, you're home, you ordered biryani twice this week
3. **Prioritization engine scores tasks** — Swiggy Food for dinner > Instamart for groceries (you can cook tomorrow)
4. **Routes to the right MCP server** — Calls Food server, pulls your usual spots
5. **Learns** — Remembers you prefer quick delivery at night, stores it

---

<!-- Add screenshots / demo walkthrough here -->

---

## Roadmap

- [ ] MCP client connection to Swiggy Food, Instamart, Dineout servers
- [ ] Context-aware prioritization engine with scoring model
- [ ] Persistent memory layer (SQLite-backed)
- [ ] Plugin system for registering new MCP servers
- [ ] Natural language interface via LLM reasoning
- [ ] Multi-turn conversation with context carryover
- [ ] Demo video and usage examples

---

## Contributing

This project is in early development. Contributions, ideas, and feedback are welcome once API access is available.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built for the [Swiggy Builder's Club](https://mcp.swiggy.com/builders/) Developer Program**

![MCP](https://img.shields.io/badge/Powered_by-MCP-blue?style=flat-square)
![Swiggy](https://img.shields.io/badge/Commerce-Swiggy-FC8019?style=flat-square)

</div>
