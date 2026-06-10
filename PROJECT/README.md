# 🎫 AI-Powered Ticket Management MCP Server

> An MCP (Model Context Protocol) server that enables AI agents to manage support tickets and search a knowledge base, built with Python and SQLite.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)](#-testing)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [MCP Tools Reference](#-mcp-tools-reference)
- [Agent Loop Demo](#-agent-loop-demo)
- [Project Structure](#-project-structure)
- [Database Schema](#-database-schema)
- [Testing](#-testing)
- [Sample Data](#-sample-data)
- [AI Usage Disclosure](#-ai-usage-disclosure)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🔍 Overview

This project implements an **MCP Server** that exposes tools for managing support tickets, allowing an AI Agent to:

- **Create** new support tickets
- **List** and filter tickets by status, priority, or category
- **Retrieve** full ticket details including comments
- **Add comments** to existing tickets
- **Search** a knowledge base for solutions

The system demonstrates the complete lifecycle of AI-assisted tool use, from schema design to agent orchestration.

### Key Concepts Demonstrated

| Concept | Implementation |
|---|---|
| **MCP Server Authoring** | Python server with stdio transport using the official MCP SDK |
| **Tool Schema Design** | 7 tools with JSON Schema input definitions and typed parameters |
| **Agent Loop** | ReAct pattern with configurable LLM (OpenAI/Anthropic) |
| **SQLite Integration** | Schema with FTS5 full-text search, constraints, and indexes |
| **AI-Assisted Development** | Transparent AI usage disclosure in `AI_USAGE.md` |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client Layer                          │
│  ┌──────────┐    ┌───────────┐    ┌──────────────────┐  │
│  │ Human    │───>│ AI Agent  │<──>│ LLM API          │  │
│  │ User     │    │ Client    │    │ (OpenAI/Anthropic)│  │
│  └──────────┘    └─────┬─────┘    └──────────────────┘  │
│                        │ stdio (JSON-RPC)                │
├────────────────────────┼────────────────────────────────┤
│                    MCP Server                            │
│  ┌─────────────────────┴─────────────────────────────┐  │
│  │              Tool Router                           │  │
│  ├──────┬──────┬───────────┬───────────┬────────────┬─────────────┬──────────────┤  │
│  │list_ │get_  │create_    │add_       │search_     │update_ticket│resolve_      │  │
│  │tickets│ticket│ticket     │comment    │kb          │_status      │ticket        │  │
│  └──┬───┴──┬───┴─────┬─────┴─────┬─────┴──────┬─────┴──────┬──────┴──────┬───────┘  │
├─────┼──────┼─────────┼───────────┼────────────┼────────┤
│     │  Service Layer  │           │            │        │
│  ┌──┴──────┴─────────┴───────────┴──┐  ┌──────┴─────┐  │
│  │       TicketService              │  │  KBService  │  │
│  └──────────────┬───────────────────┘  └──────┬──────┘  │
├─────────────────┼─────────────────────────────┼────────┤
│            Data Layer                         │        │
│  ┌──────────────┴─────────────────────────────┴──────┐  │
│  │            DatabaseManager (aiosqlite)             │  │
│  │         ┌────────────────────────────┐             │  │
│  │         │  SQLite + FTS5             │             │  │
│  │         │  tickets.db                │             │  │
│  │         └────────────────────────────┘             │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## ✨ Features

- **7 MCP Tools** for full ticket lifecycle management
- **SQLite with FTS5** for knowledge base full-text search with BM25 ranking
- **AI Agent Loop** demonstrating the ReAct (Reasoning + Acting) pattern
- **Dual LLM Support** — works with both OpenAI and Anthropic APIs
- **Comprehensive Test Suite** with unit, integration, and e2e tests
- **Sample Data** — 8 tickets, 7 comments, 8 KB articles for immediate demos
- **Clean Architecture** — layered design with clear separation of concerns
- **One-Command Demo** — seed database and launch agent in a single command

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- An API key for OpenAI or Anthropic

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/ai-ticket-mcp.git
cd ai-ticket-mcp

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your API key
```

### Configuration

Edit the `.env` file with your settings:

```env
LLM_PROVIDER=openai           # or "anthropic"
OPENAI_API_KEY=sk-your-key    # if using OpenAI
LLM_MODEL=gpt-4o              # or claude-3-5-sonnet-20241022
DATABASE_PATH=./data/tickets.db
```

### Run the Demo

```bash
# Option 1: One-command demo (seeds DB + launches agent)
python scripts/run_demo.py

# Option 2: Step-by-step
python scripts/seed_db.py          # Seed the database
python -m src.client.agent_client  # Launch the agent
```

---

## 🔧 MCP Tools Reference

| Tool | Description | Required Args | Optional Args |
|---|---|---|---|
| `list_tickets` | List/filter support tickets | — | `status`, `priority`, `category` |
| `get_ticket` | Get ticket details + comments | `ticket_id` | — |
| `create_ticket` | Create a new ticket | `title`, `description`, `created_by` | `priority`, `category` |
| `add_comment` | Add comment to a ticket | `ticket_id`, `author`, `content` | — |
| `search_kb` | Search knowledge base | `query` | `category`, `limit` |
| `update_ticket_status` | Update a ticket's status | `ticket_id`, `status` | — |
| `resolve_ticket` | Resolve ticket & add timestamp| `ticket_id` | — |

### Example Tool Calls

**List open high-priority bugs:**
```json
{"name": "list_tickets", "arguments": {"status": "open", "priority": "high", "category": "bug"}}
```

**Search the knowledge base:**
```json
{"name": "search_kb", "arguments": {"query": "password reset", "limit": 3}}
```

---

## 🤖 Agent Loop Demo

The agent client uses the **ReAct pattern** (Reasoning + Acting):

```
User: "I can't reset my password, help!"
     ↓
Agent → LLM: What tools should I use?
     ↓
LLM: Call search_kb("password reset")
     ↓
Agent → MCP: Execute search_kb
     ↓
MCP → Agent: KB article found: "Password Reset Guide"
     ↓
Agent → LLM: Here are the results, synthesize a response
     ↓
LLM → Agent: "Here's how to reset your password: [steps]"
     ↓
Agent → User: Formatted response with solution
```

### Sample Interactions

```
👤 You: Show me all open high-priority tickets

🤖 Assistant: I found 3 open high-priority tickets:
   1. TKT-005 — Password reset email not received (HIGH, bug)
   2. TKT-001 — Login page returns 500 error (CRITICAL, bug)
   3. TKT-007 — Dashboard loading slowly (HIGH, bug)

👤 You: Create a bug ticket for search not working

🤖 Assistant: I've created ticket TKT-a1b2c3d4:
   Title: Search functionality not working
   Priority: medium | Category: bug | Status: open

👤 You: Great, now resolve TKT-001 since the servers are back online, and mark TKT-005 as Closed.

🤖 Assistant: I have updated the tickets:
   - TKT-001 has been resolved successfully.
   - TKT-005 status has been updated to Closed.
```

---

## 📁 Project Structure

```
ai-ticket-mcp/
├── src/
│   ├── server/              # MCP Server
│   │   ├── mcp_server.py   # Entry point, tool registration
│   │   └── tools/          # Tool handler functions
│   ├── services/            # Business logic layer
│   │   ├── ticket_service.py
│   │   └── kb_service.py
│   ├── database/            # Data access layer
│   │   ├── database.py     # SQLite connection manager
│   │   ├── models.py       # Pydantic data models
│   │   └── seed.py         # Sample data loader
│   ├── client/              # AI Agent client
│   │   └── agent_client.py # ReAct loop implementation
│   └── config.py            # Configuration management
├── data/                    # Sample data JSON files
├── tests/                   # Comprehensive test suite
├── scripts/                 # Utility scripts
│   ├── seed_db.py          # Database seeder
│   └── run_demo.py         # One-command demo launcher
└── docs/                    # Additional documentation
```

---

## 🗄️ Database Schema

### Entity Relationship

```
┌──────────────┐       ┌──────────────┐
│   TICKETS    │──1:N──│   COMMENTS   │
├──────────────┤       ├──────────────┤
│ id (PK)      │       │ id (PK)      │
│ title        │       │ ticket_id(FK)│
│ description  │       │ author       │
│ status       │       │ content      │
│ priority     │       │ created_at   │
│ category     │       └──────────────┘
│ created_by   │
│ assigned_to  │       ┌──────────────┐
│ created_at   │       │ KB_ARTICLES  │
│ updated_at   │       ├──────────────┤
└──────────────┘       │ id (PK)      │
                       │ title        │
                       │ content      │
                       │ category     │
                       │ tags         │
                       │ created_at   │
                       └──────┬───────┘
                              │ FTS5
                       ┌──────┴───────┐
                       │KB_ARTICLES_  │
                       │FTS (virtual) │
                       └──────────────┘
```

**Key Design Decisions:**
- UUID v4 for primary keys
- FTS5 with BM25 ranking for KB search
- CHECK constraints for enum validation
- CASCADE deletes for ticket→comments

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_mcp_tools.py -v

# Run only unit tests
pytest tests/ -v -k "not agent_loop"
```

### Test Coverage

| Layer | Test File | Tests |
|---|---|---|
| Database | `test_database.py` | Schema, CRUD, constraints, FTS5 |
| Ticket Service | `test_ticket_service.py` | Create, get, list, filter, comment |
| KB Service | `test_kb_service.py` | Search, filter, ranking, edge cases |
| MCP Tools | `test_mcp_tools.py` | All 5 tools end-to-end |
| Agent Loop | `test_agent_loop.py` | Multi-tool chains, config, prompts |

---

## 📊 Sample Data

The project includes realistic sample data for immediate demo readiness:

- **8 Tickets** spanning all statuses (open, in_progress, resolved, closed) and priorities
- **7 Comments** linked to tickets showing realistic support workflows
- **8 KB Articles** covering account, auth, performance, API, reports, troubleshooting, billing, and admin topics

Seed data is loaded from JSON files in the `data/` directory.

---

## 🤖 AI Usage Disclosure

See [AI_USAGE.md](AI_USAGE.md) for a transparent disclosure of how AI tools were used in the development of this project.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
