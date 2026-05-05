# Strategy Agent

**Role:** Signal generation & scoring
**Profile:** footpump-strategy (cron)
**Schedule:** Every 5 minutes
**Consumes:** Data Agent output via bus

## Responsibilities
- Consume normalized watchlist data from Data Agent
- Run scoring algorithms (volume acceleration, sentiment correlation, accumulation patterns)
- Cross-reference volume anomalies with X sentiment
- Generate ranked signal reports with confidence scores (1-100)
- Push high-priority signals to CIO Agent via bus

## Inputs
- Normalized asset data from Data Agent (bus: data_agent → strategy_agent)
- Watchlist snapshots (bus: data_agent → strategy_agent)

## Outputs
- Signal reports → [[Signals/]]
- Priority alerts → CIO Agent via bus (strategy_agent → cio_agent)

## Current Status
- Last run: 
- Signals today: 
- Watchlist size: 

---
Template: [[Templates/Signal Report]]
Data source: footpump Discovery API
