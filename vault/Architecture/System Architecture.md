# Special Circumstances — System Architecture

## Principle

Special Circumstances is a multi-strategy hedge fund. Footpump is its first strategy
(early-pump crypto detection). The architecture separates data/storage from agent
decision-making so new strategies can be added without changing the core bus or agents.

---

## Two-Layer Architecture

```
LAYER 1: Data & Storage (per-strategy services own this)
─────────────────────────────────────────────────────────
  Each data source has its own:
  - Storage (SQLite, Postgres, etc.)
  - REST API for querying
  - Pub/sub for real-time events
  - Scoring / ranking logic
  
  Current: Footpump Discovery Service (localhost:8000)

LAYER 2: Decision & Comms (Special Circumstances owns this)
─────────────────────────────────────────────────────────
  - SQLite artifact bus (special_circumstances/data/bus.db)
  - Agent registry
  - Bridges (one per external service, publishes alerts)
  - Skills (agent libraries for calling external APIs)
  - Agents (cio, data, research, strategy, risk)
```

---

## Data Flow

```
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   Footpump   │     │  Future: CEX │     │  Future:     │
  │   Redis      │     │  Order Feed  │     │  News/On-Chn │
  │   pub/sub    │     │  webhook     │     │  ws-rpc      │
  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
         │                    │                     │
    ┌────▼────────────────────▼─────────────────────▼────┐
    │  Special Circumstances                              │
    │                                                     │
    │  ┌──────────────┐ ┌──────────┐ ┌──────────────┐   │
    │  │ footpump     │ │ cex      │ │ onchain      │   │  ← bridges
    │  │ bridge       │ │ bridge   │ │ bridge       │   │    one per source
    │  └──────┬───────┘ └────┬─────┘ └──────┬───────┘   │
    │         └──────────────┼──────────────┘            │
    │                        ▼                           │
    │  ┌─────────────────────────────────────────┐      │
    │  │       SQLite Artifact Bus               │      │
    │  │  tasks | findings | signals |           │      │
    │  │  risk_assessments | decisions | alerts  │      │
    │  └─────────────────────────────────────────┘      │
    │       │        │         │          │             │
    │  ┌────▼───┐┌───▼───┐┌────▼───┐┌────▼───┐        │
    │  │  data  ││research││strategy││  risk  │        │
    │  └────────┘└───┬───┘└────────┘└────────┘        │
    │                │                                  │
    │           ┌────▼───┐                              │
    │           │   cio  │                              │
    │           └────────┘                              │
    │                                                   │
    │  Skills: footpump_api.py, onchain.py, social.py   │
    │  Agents import skills to query external APIs      │
    └───────────────────────────────────────────────────┘
```

---

## Bridge vs Skill

| Component | Direction | What it does |
|-----------|-----------|--------------|
| `bridges/footpump.py` | External → Bus | Background daemon. Subscribes to footpump's Redis `watchlist:updates` channel. Publishes `alert` artifacts when new assets cross threshold. |
| `skills/footpump_api.py` | Bus → External | Library imported by agents. Functions to query footpump's REST API for asset data, scores, history, search, and scan status. |

Key: bridges push alerts IN. Skills pull data OUT. Agents never send data through bridges.

---

## Artifact Types (Bus Schema)

Used for agent-to-agent communication only. No raw market data.

| Type | From | To | Purpose |
|------|------|----|---------|
| `alert` | bridge | cio_agent | New asset crossed watchlist threshold |
| `task` | cio_agent | research/strategy/risk | Work assignment with objective + deadline |
| `finding` | research_agent | strategy_agent | Deep investigation results |
| `signal` | strategy_agent | risk_agent | Ranked trading signal with confidence |
| `risk_assessment` | risk_agent | cio_agent | Exposure check, risk validation |
| `decision` | cio_agent | broadcast | Final buy/sell/watch with rationale |
| `data_snapshot` | data_agent | broadcast | Structured market summary (periodic) |

---

## Agent Responsibilities

### CIO Agent
- Monitors bus for alerts, risk_assessments, findings
- Triages by urgency × materiality
- Dispatches tasks to specialist agents
- Makes final buy/sell/watch decisions
- Maintains portfolio state
- Generates daily brief

### Data Agent
- Polls external APIs for market snapshots
- Publishes periodic `data_snapshot` artifacts
- Maintains market state awareness
- Feeds strategy agent with structured data

### Research Agent
- Claims `task` artifacts from CIO
- Deep-dives on specific assets (on-chain, social, security)
- Uses `footpump_api` skill for asset snapshots
- Uses `onchain` skill for contract analysis
- Publishes `finding` artifacts

### Strategy Agent
- Consumes `finding` + `data_snapshot` artifacts
- Combines score momentum + research + market context
- Generates ranked `signal` artifacts with confidence scores
- May request backtesting from data agent

### Risk Agent
- Consumes `signal` artifacts
- Validates against portfolio risk limits
- Monitors concentration, drawdown, correlation
- Publishes `risk_assessment` (pass/fail/halt)
- Issues halt signals if limits breached

---

## Footpump API Endpoints (agents call via skill)

Base URL: `http://localhost:8000` (configurable via `FOOTPUMP_API_URL`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service index |
| GET | `/health` | Health check (DB, Redis, adapters) |
| GET | `/watchlist?limit=N&min_score=X` | Current watchlist from Redis |
| GET | `/assets/{asset_id}` | Full asset snapshot (market, momentum, metadata, security) |
| GET | `/assets/{asset_id}/score` | Latest discovery score with components |
| GET | `/assets/{asset_id}/history?limit=N` | Historical score series |
| GET | `/search?q={query}` | Search by symbol, name, or contract address |
| GET | `/scan/status` | Worker freshness, watchlist staleness |
| POST | `/scan/refresh` | Manual refresh (not yet implemented) |
| GET | `/debug/scores?limit=N&tier=X` | Debug score listing |

Asset ID format: `{symbol}:{chain}:{contract_address}`
Example: `BONK:solana:DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`

---

## Adding a New Strategy

1. Create the external service (own repo, own storage, own API)
2. Add a bridge in `special_circumstances/bridges/` (subscribes to its events → publishes alerts)
3. Add a skill in `special_circumstances/skills/` (wraps its API for agent queries)
4. Strategy agent learns to consume its signals (prompt update)
5. No bus schema changes required
