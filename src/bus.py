"""
Footpump Artifact Bus — SQLite-based agent communication.

Single file: special_circumstances/data/bus.db
WAL mode for concurrent reads during writes.
Agents poll by querying WHERE to_agent=X AND status='pending'.
Atomic claiming via UPDATE ... RETURNING.

Schema:

  artifacts
    id              TEXT PRIMARY KEY  (e.g. "hyp_20260504_001")
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    from_agent      TEXT NOT NULL     (e.g. "research_agent")
    to_agent        TEXT NOT NULL     (e.g. "strategy_agent")
    artifact_type   TEXT NOT NULL     (hypothesis, signal, task, finding, alert, report)
    priority        REAL DEFAULT 0.5  (0.0-1.0)
    status          TEXT DEFAULT 'pending'  (pending, claimed, completed, rejected, failed)
    claimed_by      TEXT
    claimed_at      TEXT
    completed_at    TEXT
    response_to     TEXT              (parent artifact id, for threading)
    thread_id       TEXT              (groups related artifacts)

    payload         JSON NOT NULL     (the actual artifact body, flexible schema)
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("/home/maxrush/special_circumstances/data/bus.db")


def init_db():
    """Create the database and schema if not exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS artifacts (
            id              TEXT PRIMARY KEY,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            from_agent      TEXT NOT NULL,
            to_agent        TEXT NOT NULL,
            artifact_type   TEXT NOT NULL,
            priority        REAL NOT NULL DEFAULT 0.5,
            status          TEXT NOT NULL DEFAULT 'pending',
            claimed_by      TEXT,
            claimed_at      TEXT,
            completed_at    TEXT,
            response_to     TEXT,
            thread_id       TEXT,
            payload         JSON NOT NULL,
            
            FOREIGN KEY (response_to) REFERENCES artifacts(id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_artifacts_status_agent 
            ON artifacts(status, to_agent);
        CREATE INDEX IF NOT EXISTS idx_artifacts_thread 
            ON artifacts(thread_id);
        CREATE INDEX IF NOT EXISTS idx_artifacts_type_status 
            ON artifacts(artifact_type, status);
        CREATE INDEX IF NOT EXISTS idx_artifacts_from_agent 
            ON artifacts(from_agent, created_at);
            
        -- Agent registry: who's active, last heartbeat
        CREATE TABLE IF NOT EXISTS agents (
            name            TEXT PRIMARY KEY,
            role            TEXT NOT NULL,
            status          TEXT DEFAULT 'active',
            last_heartbeat  TEXT,
            config_profile  TEXT
        );
    """)
    
    conn.commit()
    conn.close()
    print(f"Database initialized: {DB_PATH}")


def submit_artifact(from_agent, to_agent, artifact_type, payload, 
                    priority=0.5, response_to=None, thread_id=None):
    """Submit a new artifact to the bus. Agents call this to send messages."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    
    artifact_id = f"{artifact_type}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    conn.execute("""
        INSERT INTO artifacts (id, from_agent, to_agent, artifact_type, priority, 
                               status, response_to, thread_id, payload)
        VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
    """, (artifact_id, from_agent, to_agent, artifact_type, priority,
          response_to, thread_id, json.dumps(payload)))
    
    conn.commit()
    conn.close()
    print(f"Submitted: {artifact_id}")
    return artifact_id


def claim_next(agent_name, artifact_types=None, limit=1):
    """
    Atomically claim the next pending task for an agent.
    Returns list of claimed artifacts.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    
    now = datetime.now(timezone.utc).isoformat()
    
    if artifact_types:
        placeholders = ','.join('?' * len(artifact_types))
        query = f"""
            UPDATE artifacts SET status='claimed', claimed_by=?, claimed_at=?
            WHERE id IN (
                SELECT id FROM artifacts 
                WHERE to_agent=? AND status='pending' 
                  AND artifact_type IN ({placeholders})
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            )
            RETURNING *
        """
        params = [agent_name, now, agent_name] + list(artifact_types) + [limit]
    else:
        query = """
            UPDATE artifacts SET status='claimed', claimed_by=?, claimed_at=?
            WHERE id IN (
                SELECT id FROM artifacts 
                WHERE to_agent=? AND status='pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            )
            RETURNING *
        """
        params = [agent_name, now, agent_name, limit]
    
    rows = conn.execute(query, params).fetchall()
    conn.commit()
    conn.close()
    
    results = []
    for row in rows:
        results.append({
            "id": row[0], "created_at": row[1], "from_agent": row[2],
            "to_agent": row[3], "artifact_type": row[4], "priority": row[5],
            "status": row[6], "claimed_by": row[7], "claimed_at": row[8],
            "completed_at": row[9], "response_to": row[10], "thread_id": row[11],
            "payload": json.loads(row[12])
        })
    
    if results:
        print(f"Claimed {len(results)} artifact(s) for {agent_name}")
    return results


def complete_artifact(artifact_id, status='completed'):
    """Mark an artifact as completed/failed."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        UPDATE artifacts SET status=?, completed_at=? WHERE id=?
    """, (status, now, artifact_id))
    conn.commit()
    conn.close()
    print(f"Artifact {artifact_id} → {status}")


def query_artifacts(to_agent=None, from_agent=None, status=None, 
                    artifact_type=None, thread_id=None, limit=20):
    """Query artifacts with optional filters."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    conditions = []
    params = []
    
    if to_agent:
        conditions.append("to_agent = ?")
        params.append(to_agent)
    if from_agent:
        conditions.append("from_agent = ?")
        params.append(from_agent)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if artifact_type:
        conditions.append("artifact_type = ?")
        params.append(artifact_type)
    if thread_id:
        conditions.append("thread_id = ?")
        params.append(thread_id)
    
    where = " AND ".join(conditions) if conditions else "1=1"
    query = f"""
        SELECT * FROM artifacts WHERE {where}
        ORDER BY priority DESC, created_at DESC LIMIT ?
    """
    params.append(limit)
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    return [dict(r) for r in rows]


def register_agent(name, role, config_profile=None):
    """Register an agent in the registry."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        INSERT OR REPLACE INTO agents (name, role, status, last_heartbeat, config_profile)
        VALUES (?, ?, 'active', datetime('now'), ?)
    """, (name, role, config_profile))
    conn.commit()
    conn.close()


def heartbeat(agent_name):
    """Update agent heartbeat."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        UPDATE agents SET last_heartbeat = datetime('now') WHERE name = ?
    """, (agent_name,))
    conn.commit()
    conn.close()


# ─── Test / demo ──────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    
    # Register agents
    register_agent("cio_agent", "CIO/Portfolio Manager", "footpump")
    register_agent("research_agent", "Research Analyst", "footpump-research")
    register_agent("data_agent", "Data Engineer", "footpump-data")
    register_agent("strategy_agent", "Strategy/Signals", "footpump-strategy")
    register_agent("risk_agent", "Risk Manager", "footpump-risk")
    
    # CIO assigns a research task
    submit_artifact(
        from_agent="cio_agent",
        to_agent="research_agent",
        artifact_type="task",
        priority=0.9,
        payload={
            "objective": "Investigate prediction market inefficiencies",
            "focus": "Polymarket vs sportsbook odds during live events",
            "context": "Early-pump detection may extend to information asymmetry in prediction markets",
            "requested_output": "Hypothesis with evidence, ready for backtesting"
        }
    )
    
    # Research agent claims and processes it
    tasks = claim_next("research_agent", artifact_types=["task"])
    for task in tasks:
        # Simulate research output
        submit_artifact(
            from_agent="research_agent",
            to_agent="strategy_agent",
            artifact_type="hypothesis",
            priority=0.7,
            response_to=task["id"],
            thread_id=task.get("thread_id", "thread_001"),
            payload={
                "asset_class": "prediction_markets",
                "claim": "Polymarket reacts slower than sharp sportsbook odds during live esports maps",
                "evidence": [
                    {"source": "polymarket", "metric": "odds_lag_seconds", "value": 12.4},
                    {"source": "pinnacle", "metric": "odds_update_ms", "value": 200}
                ],
                "confidence": 0.62,
                "requested_action": "backtest"
            }
        )
        complete_artifact(task["id"])
    
    # Show what's pending for strategy agent
    print("\n─── Pending for strategy_agent ───")
    for a in query_artifacts(to_agent="strategy_agent", status="pending"):
        print(f"  {a['id']}: {a['artifact_type']} from {a['from_agent']} (priority={a['priority']})")
    
    # Thread view
    print("\n─── Full thread ───")
    for a in query_artifacts(thread_id="thread_001"):
        print(f"  [{a['status']}] {a['from_agent']} → {a['to_agent']}: {a['artifact_type']}")
    
    print("\n✓ Demo complete. Agents: registered, task: dispatched, hypothesis: routed.")
