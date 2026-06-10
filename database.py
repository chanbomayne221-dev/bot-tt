from __future__ import annotations

import asyncpg
from datetime import datetime, timezone
from typing import Optional

from .config import DATABASE_URL

_pool: Optional[asyncpg.Pool] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    today_messages INTEGER NOT NULL DEFAULT 0,
    total_messages INTEGER NOT NULL DEFAULT 0,
    highest_reward INTEGER NOT NULL DEFAULT 0,
    dm_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    banned_tt BOOLEAN NOT NULL DEFAULT FALSE,
    last_message_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reward_codes (
    id BIGSERIAL PRIMARY KEY,
    milestone INTEGER NOT NULL,
    code TEXT NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    used_by BIGINT,
    used_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_reward_codes_ms_used ON reward_codes(milestone, used);

CREATE TABLE IF NOT EXISTS claimed_rewards (
    user_id BIGINT NOT NULL,
    milestone INTEGER NOT NULL,
    code TEXT NOT NULL,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, milestone)
);

CREATE TABLE IF NOT EXISTS groups (
    group_id BIGINT PRIMARY KEY,
    group_name TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);
"""


async def init_db() -> None:
    global _pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=5,
        statement_cache_size=0,  # required for Supabase pgbouncer (transaction pooler)
    )
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA)


def pool() -> asyncpg.Pool:
    assert _pool is not None, "DB pool not initialized"
    return _pool


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _row_to_dict(row) -> Optional[dict]:
    return dict(row) if row else None


async def ensure_user(user_id: int, username: Optional[str], full_name: str) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO users (user_id, username, full_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name""",
            user_id, username, full_name,
        )


async def get_user(user_id: int) -> Optional[dict]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        return _row_to_dict(row)


async def add_interactions(user_id: int, delta: int, now_ts: float) -> Optional[dict]:
    """Atomically add delta and return updated user, or None if banned/missing."""
    async with pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id=$1 FOR UPDATE", user_id
            )
            if not row or row["banned_tt"]:
                return None
            updated = await conn.fetchrow(
                """UPDATE users SET today_messages=today_messages+$1,
                    total_messages=total_messages+$1,
                    last_message_at=$2
                    WHERE user_id=$3 RETURNING *""",
                delta, now_ts, user_id,
            )
            return _row_to_dict(updated)


async def set_dm_enabled(user_id: int, enabled: bool) -> None:
    async with pool().acquire() as conn:
        await conn.execute("UPDATE users SET dm_enabled=$1 WHERE user_id=$2", enabled, user_id)


async def set_highest_reward(user_id: int, milestone: int) -> None:
    async with pool().acquire() as conn:
        await conn.execute("UPDATE users SET highest_reward=$1 WHERE user_id=$2", milestone, user_id)


async def reset_today_all() -> None:
    async with pool().acquire() as conn:
        await conn.execute("UPDATE users SET today_messages=0, highest_reward=0")


async def get_top_today(limit: int = 15) -> list[dict]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """SELECT user_id, username, full_name, today_messages
            FROM users WHERE banned_tt=FALSE AND today_messages>0
            ORDER BY today_messages DESC LIMIT $1""",
            limit,
        )
        return [dict(r) for r in rows]


async def get_today_total() -> int:
    async with pool().acquire() as conn:
        val = await conn.fetchval(
            "SELECT COALESCE(SUM(today_messages),0) FROM users WHERE banned_tt=FALSE"
        )
        return int(val or 0)


async def take_code(milestone: int, user_id: int) -> Optional[str]:
    """Atomically pop one unused code for milestone."""
    async with pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT id, code FROM reward_codes
                WHERE milestone=$1 AND used=FALSE
                ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1""",
                milestone,
            )
            if not row:
                return None
            now = datetime.now(timezone.utc)
            await conn.execute(
                "UPDATE reward_codes SET used=TRUE, used_by=$1, used_at=$2 WHERE id=$3",
                user_id, now, row["id"],
            )
            await conn.execute(
                """INSERT INTO claimed_rewards (user_id, milestone, code)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, milestone) DO UPDATE SET code=EXCLUDED.code""",
                user_id, milestone, row["code"],
            )
            return row["code"]


async def add_code(milestone: int, code: str) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO reward_codes (milestone, code) VALUES ($1, $2)", milestone, code
        )


async def stock_summary() -> list[tuple[int, int]]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT milestone, COUNT(*) AS c FROM reward_codes WHERE used=FALSE GROUP BY milestone ORDER BY milestone"
        )
        return [(int(r["milestone"]), int(r["c"])) for r in rows]


async def get_claimed_milestones(user_id: int) -> list[int]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT milestone FROM claimed_rewards WHERE user_id=$1 ORDER BY milestone", user_id
        )
        return [int(r["milestone"]) for r in rows]


async def set_banned(user_id: int, banned: bool) -> None:
    async with pool().acquire() as conn:
        await conn.execute("UPDATE users SET banned_tt=$1 WHERE user_id=$2", banned, user_id)


async def find_user_by_username(username: str) -> Optional[dict]:
    username = username.lstrip("@").lower()
    async with pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE LOWER(username)=$1", username)
        return _row_to_dict(row)


async def upsert_group(group_id: int, group_name: str) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            """INSERT INTO groups (group_id, group_name) VALUES ($1, $2)
            ON CONFLICT (group_id) DO UPDATE SET group_name=EXCLUDED.group_name""",
            group_id, group_name,
        )


async def stats_global() -> dict:
    async with pool().acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users")
        total = await conn.fetchval("SELECT COALESCE(SUM(total_messages),0) FROM users")
        today = await conn.fetchval("SELECT COALESCE(SUM(today_messages),0) FROM users")
        codes_left = await conn.fetchval("SELECT COUNT(*) FROM reward_codes WHERE used=FALSE")
        codes_used = await conn.fetchval("SELECT COUNT(*) FROM reward_codes WHERE used=TRUE")
        return {
            "users": int(users or 0),
            "total_messages": int(total or 0),
            "today_messages": int(today or 0),
            "codes_left": int(codes_left or 0),
            "codes_used": int(codes_used or 0),
        }
