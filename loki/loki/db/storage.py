import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from loki.core.canary import CanaryTrigger

LOKI_DIR = Path.home() / ".loki"
DB_PATH = LOKI_DIR / "loki.db"


class Storage:
    def __init__(self):
        LOKI_DIR.mkdir(exist_ok=True)
        self.path = DB_PATH
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS traps (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    mode        TEXT NOT NULL,
                    scenario    TEXT NOT NULL,
                    platform_url TEXT,
                    canary_uuid TEXT,
                    canary_url  TEXT,
                    extra       TEXT,
                    created_at  TEXT NOT NULL,
                    active      INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS triggers (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    trap_id      TEXT NOT NULL,
                    request_id   TEXT UNIQUE,
                    ip           TEXT,
                    user_agent   TEXT,
                    method       TEXT,
                    query        TEXT,
                    headers      TEXT,
                    triggered_at TEXT,
                    saved_at     TEXT NOT NULL
                );
            """)

    # ── Traps ──────────────────────────────────────────────

    def save_trap(
        self,
        name: str,
        mode: str,
        scenario: str,
        platform_url: Optional[str] = None,
        canary_uuid: Optional[str] = None,
        canary_url: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> str:
        trap_id = str(uuid.uuid4())[:8]
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO traps
                   (id, name, mode, scenario, platform_url, canary_uuid, canary_url, extra, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trap_id, name, mode, scenario,
                    platform_url, canary_uuid, canary_url,
                    json.dumps(extra or {}),
                    datetime.utcnow().isoformat(),
                ),
            )
        return trap_id

    def get_traps(self, active_only: bool = False) -> List[dict]:
        with self._connect() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM traps WHERE active=1 ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM traps ORDER BY created_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def get_trap(self, trap_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM traps WHERE id=?", (trap_id,)
            ).fetchone()
        return dict(row) if row else None

    def deactivate_trap(self, trap_id: str) -> bool:
        with self._connect() as conn:
            conn.execute("UPDATE traps SET active=0 WHERE id=?", (trap_id,))
        return True

    # ── Triggers ───────────────────────────────────────────

    def save_trigger(self, trap_id: str, trigger: CanaryTrigger) -> None:
        with self._connect() as conn:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO triggers
                       (trap_id, request_id, ip, user_agent, method, query, headers, triggered_at, saved_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        trap_id,
                        trigger.request_id,
                        trigger.ip,
                        trigger.user_agent,
                        trigger.method,
                        trigger.query,
                        json.dumps(trigger.headers),
                        trigger.triggered_at,
                        datetime.utcnow().isoformat(),
                    ),
                )
            except Exception:
                pass

    def get_triggers(self, trap_id: Optional[str] = None) -> List[dict]:
        with self._connect() as conn:
            if trap_id:
                rows = conn.execute(
                    "SELECT * FROM triggers WHERE trap_id=? ORDER BY triggered_at DESC",
                    (trap_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM triggers ORDER BY triggered_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def trigger_count(self, trap_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM triggers WHERE trap_id=?", (trap_id,)
            ).fetchone()
        return row[0] if row else 0
