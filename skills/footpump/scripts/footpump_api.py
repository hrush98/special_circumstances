"""
Footpump API Skill — Async HTTP client for the Discovery Service REST API.

Import this in agent code to query footpump's watchlist, asset details,
score history, and operational status. Agents call these functions directly
when they need data — no raw data flows through the artifact bus.

Base URL configurable via FOOTPUMP_API_URL env var (default http://localhost:8000).
"""

import os
from typing import Any, Dict, List, Optional

import httpx

FOOTPUMP_API_URL: str = os.environ.get(
    "FOOTPUMP_API_URL", "http://localhost:8000"
).rstrip("/")

_default_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    """Get or create a shared AsyncClient."""
    global _default_client
    if _default_client is None:
        _default_client = httpx.AsyncClient(
            base_url=FOOTPUMP_API_URL,
            timeout=httpx.Timeout(30.0),
            headers={"Accept": "application/json"},
        )
    return _default_client


def _build_url(path: str) -> str:
    """Build a full URL from a path."""
    return f"{FOOTPUMP_API_URL}{path}"


async def health_check() -> Dict[str, Any]:
    """
    Check footpump service health (DB, Redis, adapters).

    Returns:
        dict with keys: status, database, redis, adapters
        On error: {"status": "error", "error": str}
    """
    try:
        client = _get_client()
        response = await client.get("/health")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Connection failed: {e}"}


async def get_watchlist(
    limit: int = 50,
    min_score: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Get the current live watchlist from Redis cache.

    Args:
        limit: Max entries to return (1-1000)
        min_score: Filter by minimum discovery score (0.0-1.0)

    Returns:
        List of watchlist entries with keys:
        asset_id, symbol, chain, contract_address, score, updated_at, reasons
        On error: [{"error": str}]
    """
    try:
        client = _get_client()
        params: Dict[str, Any] = {"limit": limit}
        if min_score is not None:
            params["min_score"] = min_score
        response = await client.get("/watchlist", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return [{"error": str(e)}]
    except Exception as e:
        return [{"error": f"Connection failed: {e}"}]


async def get_asset(asset_id: str) -> Dict[str, Any]:
    """
    Get a full asset snapshot with all metadata.

    The asset_id format is: {symbol}:{chain}:{contract_address}
    Example: BONK:solana:DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263

    Returns:
        dict with keys: asset_id, symbol, name, chain, contract_address,
        asset_type, market (price, mcap, liquidity, volume, holders, etc.),
        momentum (price change, volume change, acceleration, age),
        enrichment (trending rank, safety scores),
        latest_score (score, components, tier, reasons),
        discovery (why_interesting, market_quality_hints, investigation_hints),
        metadata (project, quality, security, market_structure, research_context)
        On error: {"error": str}
    """
    try:
        client = _get_client()
        response = await client.get(f"/assets/{asset_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return {"error": f"Asset not found: {asset_id}"}
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Connection failed: {e}"}


async def get_asset_score(asset_id: str) -> Dict[str, Any]:
    """
    Get the latest discovery score for an asset with component breakdown.

    Returns:
        dict with keys: asset_id, score, timestamp, components (breadth,
        recency, liquidity, venue_mix), reasons, raw_features, safety_flags
    """
    try:
        client = _get_client()
        response = await client.get(f"/assets/{asset_id}/score")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return {"error": f"Asset or score not found: {asset_id}"}
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Connection failed: {e}"}


async def get_asset_history(
    asset_id: str,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Get historical score series for an asset.

    Args:
        asset_id: Asset identifier
        limit: Max data points to return (1-500)

    Returns:
        dict with keys: asset_id, points (list of {timestamp, score, components})
    """
    try:
        client = _get_client()
        response = await client.get(
            f"/assets/{asset_id}/history",
            params={"limit": limit},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return {"error": f"Asset not found: {asset_id}"}
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Connection failed: {e}"}


async def search_assets(query: str) -> List[Dict[str, Any]]:
    """
    Search for assets by symbol, name, or contract address.

    Args:
        query: Search string (min 1 character)

    Returns:
        List of matching assets with keys:
        asset_id, symbol, name, chain, contract_address, coingecko_id,
        first_seen_at, last_updated_at
    """
    try:
        client = _get_client()
        response = await client.get("/search", params={"q": query})
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return [{"error": str(e)}]
    except Exception as e:
        return [{"error": f"Connection failed: {e}"}]


async def get_scan_status() -> Dict[str, Any]:
    """
    Get operational status: worker freshness, watchlist staleness.

    Returns:
        dict with keys: worker_status (idle/ready/stale),
        refresh_supported, refresh_endpoint, watchlist_size,
        latest_asset_update_at, latest_score_at, latest_watchlist_update_at,
        data_freshness_seconds
    """
    try:
        client = _get_client()
        response = await client.get("/scan/status")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Connection failed: {e}"}


async def close() -> None:
    """Close the shared HTTP client."""
    global _default_client
    if _default_client is not None:
        await _default_client.aclose()
        _default_client = None


# ─── Test ──────────────────────────────────────────────────────────────

async def _main() -> None:
    """Quick test: run health_check() and print the result."""
    import asyncio

    print(f"Footpump API URL: {FOOTPUMP_API_URL}")
    print("-" * 40)

    result = await health_check()
    print(json.dumps(result, indent=2))

    if result.get("status") == "healthy":
        watchlist = await get_watchlist(limit=5)
        print(f"\nTop 5 watchlist entries ({len(watchlist)} returned):")
        for entry in watchlist[:5]:
            print(
                f"  {entry.get('symbol', '???')} "
                f"({entry.get('chain', '?')}) "
                f"score={entry.get('score', 0):.3f}"
            )

    await close()


if __name__ == "__main__":
    import asyncio
    import json

    asyncio.run(_main())
