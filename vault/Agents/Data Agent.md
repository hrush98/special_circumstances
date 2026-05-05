# Data Agent

**Role:** Data ingestion & normalization
**Profile:** footpump-data (cron)
**Schedule:** Every 60 seconds
**Source of truth for asset data on the bus**

## Responsibilities
- Poll footpump Discovery API for watchlist changes
- Ingest from all adapters (DEX Screener, Birdeye, GeckoTerminal, CoinGecko, DeFiLlama)
- Normalize multi-source data into canonical asset records
- Maintain the live watchlist (top N assets)
- Push normalized data and watchlist snapshots to Strategy Agent via bus
- Detect new token listings from factory watchers

## Inputs
- footpump Discovery API (FastAPI/Redis)
- Factory watcher events (new pairs, new tokens)

## Outputs
- Normalized asset snapshots → Strategy Agent via bus (data_agent → strategy_agent)
- Watchlist updates → [[Watchlist/Live Watchlist]]
- New listing alerts → CIO Agent via bus (data_agent → cio_agent)

## Current Status
- Last poll: 
- Sources healthy: 
- Assets tracked: 

---
Connects to: footpump Discovery Service (FastAPI + SQLAlchemy + Redis)
Adapters: dex_screener, birdeye, geckoterminal, coingecko, defillama
