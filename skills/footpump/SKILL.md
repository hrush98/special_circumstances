---
name: footpump
description: Query the Footpump Discovery Service for early-pump crypto detection — watchlist, asset snapshots, score history, and search.
version: 1.0.0
author: Special Circumstances
platforms: [linux]
metadata:
  hermes:
    tags: [crypto, trading, on-chain, discovery, pump-detection]
    requires_toolsets: [code_execution]
    config:
      - key: footpump.api_url
        description: Base URL of the Footpump Discovery Service API
        default: "http://localhost:8000"
        prompt: Footpump API URL
      - key: footpump.redis_url
        description: Redis URL for the bridge to subscribe to watchlist updates
        default: "redis://localhost:6379/0"
        prompt: Footpump Redis URL
required_environment_variables:
  - name: FOOTPUMP_API_URL
    prompt: Footpump Discovery API base URL
    help: "Default is http://localhost:8000 if not set"
    required_for: API queries
---

# Footpump Discovery Service

Query the Footpump early-pump detection engine. Footpump ingests data from DexScreener,
Birdeye, CoinGecko, GeckoTerminal, and DeFiLlama, scores assets on acceleration metrics,
and maintains a live watchlist of the top ~200 tokens showing unusual activity.

## When to Use

- **CIO Agent**: After receiving a bridge `alert` that new assets entered the watchlist.
  Pull the watchlist or specific asset detail before dispatching research tasks.
- **Research Agent**: When a CIO task requires deep investigation of a specific asset.
  Call `get_asset()` for the full snapshot — market data, security flags, socials, metadata.
- **Strategy Agent**: When building signals. Pull asset history to see score momentum.
- **Data Agent**: Periodically check `/scan/status` for data freshness.

## Quick Reference

All functions are async. Import and call from `execute_code`:

```python
import sys; sys.path.insert(0, '${HERMES_SKILL_DIR}/scripts')
from footpump_api import (
    health_check,       # GET /health → service status
    get_watchlist,      # GET /watchlist?limit=N&min_score=X → live watchlist
    get_asset,          # GET /assets/{asset_id} → full snapshot with metadata
    get_asset_score,    # GET /assets/{asset_id}/score → latest score + components
    get_asset_history,  # GET /assets/{asset_id}/history?limit=N → score time series
    search_assets,      # GET /search?q={query} → symbol/name/address search
    get_scan_status,    # GET /scan/status → worker freshness
)

# Example: pull top 10 watchlist entries
watchlist = await get_watchlist(limit=10)
for entry in watchlist:
    print(f"{entry['symbol']}: {entry['score']:.3f}")
```

Asset ID format: `{symbol}:{chain}:{contract_address}`
Example: `BONK:solana:DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`

## Common Workflows

### 1. Check service is alive
```python
status = await health_check()
print(status['status'])  # healthy, degraded, or unhealthy
```

### 2. Pull watchlist (score-ordered)
```python
watchlist = await get_watchlist(limit=20, min_score=0.5)
for entry in watchlist:
    print(f"{entry['symbol']} ({entry['chain']}) score={entry['score']:.3f}")
```

### 3. Deep-dive one asset
```python
asset = await get_asset("BONK:solana:DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")
print(asset['symbol'], asset['market']['price'])
print(asset['latest_score']['score'], asset['latest_score']['tier'])
print(asset['metadata']['security'])  # honeypot status, ownership, taxes
print(asset['metadata']['project'])   # website, socials, description
print(asset['discovery']['investigation_hints'])
```

### 4. Check score momentum
```python
history = await get_asset_history("BONK:solana:DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", limit=20)
scores = [p['score'] for p in history['points']]
print(f"Trend: {scores[-1] - scores[0]:+.3f} over {len(scores)} readings")
```

### 5. Search for an asset
```python
results = await search_assets("bonk")
for r in results:
    print(f"{r['symbol']} ({r['chain']}) {r['asset_id']}")
```

### 6. Check data freshness
```python
status = await get_scan_status()
print(f"Worker: {status['worker_status']}, Freshness: {status['data_freshness_seconds']}s")
```

## Architecture Note

The Footpump **bridge** (`bridges/footpump.py` in the SC repo) is a separate background daemon
that subscribes to Footpump's Redis `watchlist:updates` channel and publishes `alert` artifacts
to the artifact bus. The skill does NOT replace the bridge — the bridge pushes notifications,
the skill pulls data on demand.

## Pitfalls

- **Footpump must be running.** If `health_check()` fails, the discovery service is down.
  Report this and retry; do not fabricate data.
- **Asset IDs are case-sensitive.** Use the exact ID from the watchlist or search results.
- **The watchlist is cached in Redis (5min TTL).** It may lag behind the database by up to
  one poll cycle (60s).
- **Manual refresh is not implemented.** `/scan/refresh` returns 501. Data updates on the
  worker's polling cadence.
- **Empty watchlist is normal.** It means no assets currently cross the discovery score
  threshold. Do not treat this as an error.

## Verification

```python
status = await health_check()
assert status['database'] and status['redis'], "Footpump unhealthy"
watchlist = await get_watchlist(limit=1)
print(f"OK — {len(watchlist)} assets on watchlist")
```
