"""In-memory per-user counters with anti-spam and periodic flush to DB."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Optional

from aiogram import Bot

from . import database as db
from .config import MIN_INTERVAL_PER_USER, UPDATE_DB_INTERVAL, ADMIN_ID
from .rewards import get_reward_amount, milestone_for


class InteractionTracker:
    def __init__(self, bot: Bot):
        self.bot = bot
        # pending count not yet flushed to DB per user
        self._pending: dict[int, int] = defaultdict(int)
        # last counted message time per user (for anti-spam)
        self._last_counted_ts: dict[int, float] = {}
        # last flush time per user
        self._last_flush_ts: dict[int, float] = {}
        # user meta for ensure
        self._user_meta: dict[int, tuple[Optional[str], str]] = {}
        self._lock = asyncio.Lock()

    async def on_message(self, user_id: int, username: Optional[str], full_name: str) -> None:
        now = time.monotonic()
        async with self._lock:
            last = self._last_counted_ts.get(user_id, 0.0)
            if now - last < MIN_INTERVAL_PER_USER:
                return  # anti-spam: skip
            self._last_counted_ts[user_id] = now
            self._pending[user_id] += 1
            self._user_meta[user_id] = (username, full_name)
            last_flush = self._last_flush_ts.get(user_id, 0.0)
            should_flush = (now - last_flush) >= UPDATE_DB_INTERVAL
            if not should_flush:
                return
            delta = self._pending.pop(user_id)
            self._last_flush_ts[user_id] = now
            meta = self._user_meta.get(user_id, (username, full_name))

        # outside lock: DB IO
        await db.ensure_user(user_id, meta[0], meta[1])
        updated = await db.add_interactions(user_id, delta, time.time())
        if updated is None:
            return  # banned
        await self._check_reward(updated)

    async def flush_all(self) -> None:
        """Flush all pending counters to DB. Useful before shutdown / scheduled jobs."""
        async with self._lock:
            pending = dict(self._pending)
            self._pending.clear()
            meta = dict(self._user_meta)
            now = time.monotonic()
            for uid in pending:
                self._last_flush_ts[uid] = now
        for uid, delta in pending.items():
            if delta <= 0:
                continue
            m = meta.get(uid)
            if m:
                await db.ensure_user(uid, m[0], m[1])
            updated = await db.add_interactions(uid, delta, time.time())
            if updated is None:
                continue
            await self._check_reward(updated)

    async def _check_reward(self, user: dict) -> None:
        today = int(user["today_messages"])
        highest = int(user["highest_reward"])
        target = milestone_for(today)
        if target is None or target <= highest:
            return
        # Award all crossed milestones from highest+100 up to target
        ms = highest + 100 if highest >= 100 else 100
        while ms <= target:
            await self._award(user, ms)
            ms += 100

    async def _award(self, user: dict, milestone: int) -> None:
        uid = int(user["user_id"])
        amount = get_reward_amount(milestone)
        code = await db.take_code(milestone, uid)
        if code is None:
            try:
                await self.bot.send_message(
                    ADMIN_ID, f"⚠️ Kho code mốc {milestone} đã hết."
                )
            except Exception:
                pass
            return
        await db.set_highest_reward(uid, milestone)
        # DM user if enabled
        if user.get("dm_enabled"):
            try:
                await self.bot.send_message(
                    uid,
                    (
                        f"🎉 Chúc mừng! Bạn đã đạt mốc <b>{milestone} tin</b>\n"
                        f"💰 Phần thưởng: <b>{amount:,}đ</b>\n"
                        f"🎁 Giftcode: <code>{code}</code>"
                    ),
                )
            except Exception:
                # User hasn't started DM or blocked bot
                try:
                    await self.bot.send_message(
                        ADMIN_ID,
                        f"⚠️ Không thể DM user {uid} ({user.get('full_name')}). Code {milestone}: {code}",
                    )
                except Exception:
                    pass
