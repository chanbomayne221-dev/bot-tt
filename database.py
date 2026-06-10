from __future__ import annotations

import aiosqlite
import asyncio
from datetime import datetime
from typing import Optional

from config import DB_PATH

_db_lock = asyncio.Lock()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    today_messages INTEGER NOT NULL DEFAULT 0,
    total_messages INTEGER NOT NULL DEFAULT 0,
    highest_reward INTEGER NOT NULL DEFAULT 0,
    dm_enabled INTEGER NOT NULL DEFAULT 0,
    banned_tt INTEGER NOT NULL DEFAULT 0,
    last_message_at REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reward_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    milestone INTEGER NOT NULL,
    code TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    used_by INTEGER,
    used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_reward_codes_ms_used ON reward_codes(milestone, used);

CREATE TABLE IF NOT EXISTS claimed_rewards (
    user_id INTEGER NOT NULL,
    milestone INTEGER NOT NULL,
    code TEXT NOT NULL,
    claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, milestone)
);

CREATE TABLE IF NOT EXISTS groups (
    group_id INTEGER PRIMARY KEY,
    group_name TEXT,
    enabled INTEGER NOT NULL DEFAULT 1
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def ensure_user(user_id: int, username: Optional[str], full_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name""",
            (user_id, username, full_name),
        )
        await db.commit()


async def get_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def add_interactions(user_id: int, delta: int, now_ts: float) -> Optional[dict]:
    """Add delta to today_messages and total_messages, set last_message_at. Returns updated user dict or None if banned."""
    async with _db_lock:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if not row:
                return None
            if row["banned_tt"]:
                return None
            await db.execute(
                """UPDATE users SET today_messages=today_messages+?,
                    total_messages=total_messages+?,
                    last_message_at=?
                    WHERE user_id=?""",
                (delta, delta, now_ts, user_id),
            )
            await db.commit()
            cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None


async def set_dm_enabled(user_id: int, enabled: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET dm_enabled=? WHERE user_id=?", (1 if enabled else 0, user_id))
        await db.commit()


async def set_highest_reward(user_id: int, milestone: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET highest_reward=? WHERE user_id=?", (milestone, user_id))
        await db.commit()


async def reset_today_all() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET today_messages=0, highest_reward=0")
        await db.commit()


async def get_top_today(limit: int = 15) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT user_id, username, full_name, today_messages
            FROM users WHERE banned_tt=0 AND today_messages>0
            ORDER BY today_messages DESC LIMIT ?""",
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_today_total() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COALESCE(SUM(today_messages),0) FROM users WHERE banned_tt=0")
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def take_code(milestone: int, user_id: int) -> Optional[str]:
    """Atomically pop one unused code for milestone, mark used and create claimed record."""
    async with _db_lock:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id, code FROM reward_codes WHERE milestone=? AND used=0 ORDER BY id LIMIT 1",
                (milestone,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            now = datetime.utcnow().isoformat()
            await db.execute(
                "UPDATE reward_codes SET used=1, used_by=?, used_at=? WHERE id=?",
                (user_id, now, row["id"]),
            )
            await db.execute(
                "INSERT OR REPLACE INTO claimed_rewards (user_id, milestone, code) VALUES (?, ?, ?)",
                (user_id, milestone, row["code"]),
            )
            await db.commit()
            return row["code"]


async def add_code(milestone: int, code: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO reward_codes (milestone, code) VALUES (?, ?)", (milestone, code))
        await db.commit()


async def stock_summary() -> list[tuple[int, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT milestone, COUNT(*) FROM reward_codes WHERE used=0 GROUP BY milestone ORDER BY milestone"
        )
        return [(int(m), int(c)) for m, c in await cur.fetchall()]


async def get_claimed_milestones(user_id: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT milestone FROM claimed_rewards WHERE user_id=? ORDER BY milestone", (user_id,)
        )
        return [int(r[0]) for r in await cur.fetchall()]


async def set_banned(user_id: int, banned: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET banned_tt=? WHERE user_id=?", (1 if banned else 0, user_id))
        await db.commit()


async def find_user_by_username(username: str) -> Optional[dict]:
    username = username.lstrip("@").lower()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE LOWER(username)=?", (username,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_group(group_id: int, group_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO groups (group_id, group_name) VALUES (?, ?)
            ON CONFLICT(group_id) DO UPDATE SET group_name=excluded.group_name""",
            (group_id, group_name),
        )
        await db.commit()


async def stats_global() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        users = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COALESCE(SUM(total_messages),0) FROM users")
        total = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COALESCE(SUM(today_messages),0) FROM users")
        today = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM reward_codes WHERE used=0")
        codes_left = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM reward_codes WHERE used=1")
        codes_used = (await cur.fetchone())[0]
        return {
            "users": users,
            "total_messages": total,
            "today_messages": today,
            "codes_left": codes_left,
            "codes_used": codes_used,
        }
