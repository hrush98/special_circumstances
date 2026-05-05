"""
Footpump Watchlist Bridge — Subscribe to Redis pub/sub and publish alerts to the artifact bus.

This is a one-way notification pipe:
  Footpump Redis (watchlist:updates) → SQLite Artifact Bus (alert artifacts)

The bridge does NOT stream raw data. It only publishes alerts when new assets enter
the watchlist, so the CIO agent knows something interesting appeared and can dispatch
a research task.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import redis

# Import the artifact bus module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.bus import submit_artifact, query_artifacts, init_db, register_agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [bridge] %(levelname)s %(message)s",
)
logger = logging.getLogger("footpump_bridge")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CHANNEL = "watchlist:updates"
RECONNECT_DELAY = 5  # seconds
MAX_RECONNECT_DELAY = 60


def _recent_alert_exists(event: dict) -> bool:
    """Check if a similar alert was already published recently (dedup)."""
    try:
        existing = query_artifacts(
            from_agent="footpump_bridge",
            artifact_type="alert",
            status="pending",
            limit=5,
        )
        for artifact in existing:
            payload = artifact.get("payload", {})
            existing_event = payload.get("event", {})
            # Same count and timestamp within 2 minutes = duplicate
            if (
                existing_event.get("count") == event.get("count")
                and existing_event.get("added") == event.get("added")
                and existing_event.get("removed") == event.get("removed")
            ):
                logger.debug("Duplicate alert suppressed")
                return True
    except Exception as e:
        logger.warning(f"Dedup check failed: {e}")
    return False


def handle_message(message: dict) -> None:
    """Parse a watchlist:updates message and publish an alert if new entries exist."""
    event = message.get("event", "unknown")
    count = message.get("count", 0)
    added = message.get("added", 0)
    removed = message.get("removed", 0)
    timestamp = message.get("timestamp", "")

    logger.info(
        f"Watchlist update: event={event}, count={count}, "
        f"added={added}, removed={removed}"
    )

    if added <= 0:
        logger.debug(f"No new entries (added={added}), skipping alert")
        return

    if _recent_alert_exists(message):
        return

    try:
        artifact_id = submit_artifact(
            from_agent="footpump_bridge",
            to_agent="cio_agent",
            artifact_type="alert",
            priority=0.7,
            payload={
                "source": "footpump",
                "event": message,
                "note": f"{added} new asset(s) entered watchlist",
            },
        )
        logger.info(f"Alert published: {artifact_id} ({added} new, {removed} removed)")
    except Exception as e:
        logger.error(f"Failed to publish alert: {e}")


def connect_redis() -> redis.Redis:
    """Connect to Redis with retries."""
    logger.info(f"Connecting to Redis: {REDIS_URL}")
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()  # Verify connection
    logger.info("Redis connected")
    return client


def run_bridge() -> None:
    """Main bridge loop — subscribe to watchlist:updates and publish alerts."""
    logger.info("Footpump Bridge starting")

    # Ensure bus DB exists and register this bridge
    init_db()
    register_agent("footpump_bridge", "Bridge", "footpump")

    delay = RECONNECT_DELAY
    while True:
        try:
            client = connect_redis()
            pubsub = client.pubsub()
            pubsub.subscribe(CHANNEL)
            logger.info(f"Subscribed to channel: {CHANNEL}")

            delay = RECONNECT_DELAY  # Reset on successful connect

            for raw in pubsub.listen():
                if raw["type"] != "message":
                    continue

                try:
                    message = json.loads(raw["data"])
                    handle_message(message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON on channel: {raw['data'][:200]}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}", exc_info=True)

        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Redis connection lost: {e}. Reconnecting in {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_DELAY)

        except KeyboardInterrupt:
            logger.info("Bridge shutting down")
            break

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            time.sleep(delay)
            delay = min(delay * 2, MAX_RECONNECT_DELAY)

    logger.info("Bridge stopped")


if __name__ == "__main__":
    run_bridge()
