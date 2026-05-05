# Footpump Dashboard

## Active Agents
- [[Agents/Data Agent]] - Continuous data ingestion & normalization (cron)
- [[Agents/Strategy Agent]] - Signal generation & scoring (cron)
- [[Agents/CIO Agent]] - Portfolio management & orchestration (interactive)
- [[Agents/Research Agent]] - On-chain deep dives (on-demand)
- [[Agents/Risk Agent]] - Risk monitoring & position guarding (cron)

## Bus Topology
```
Data Agent ──→ Strategy Agent ──→ CIO Agent
                                   │
                        ┌──────────┼──────────┐
                        ↓          ↓          ↓
                 Research Agent    Risk Agent   (decisions)
```

## Latest Signals
```dataview
TABLE score, confidence, timestamp
FROM "Signals"
SORT timestamp DESC
LIMIT 10
```

## Recent Reports
```dataview
TABLE date, author
FROM "Reports"
SORT date DESC
LIMIT 5
```

## Watchlist
See [[Watchlist/Live Watchlist]] for current top assets.
