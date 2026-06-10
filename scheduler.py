from __future__ import annotations

import logging
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

import database as db
from config import TIMEZONE, ADMIN_ID, EVENT_TIMES, EVENT_MIN_INTERACTIONS
from services.tracker import InteractionTracker

log = logging.getLogger(__name__)


async def daily_reset(tracker: InteractionTracker, bot: Bot) -> None:
    await tracker.flush_all()
    await db.reset_today_all()
    log.info("Daily reset done.")
    try:
        await bot.send_message(ADMIN_ID, "🔄 Đã reset tương tác hôm nay (00:00 VN).")
    except Exception:
        pass


async def event_check(bot: Bot) -> None:
    """At each event time, list eligible users (>=500 today)."""
    top = await db.get_top_today(50)
    eligible = [u for u in top if u["today_messages"] >= EVENT_MIN_INTERACTIONS]
    if not eligible:
        return
    lines = ["⏰ <b>EVENT GIỜ</b> — Đủ điều kiện (≥ 500 tin):"]
    for i, u in enumerate(eligible[:20], 1):
        name = u.get("full_name") or str(u["user_id"])
        lines.append(f"{i}. {name} – {u['today_messages']} tin")
    try:
        await bot.send_message(ADMIN_ID, "\n".join(lines))
    except Exception:
        pass


def setup_scheduler(bot: Bot, tracker: InteractionTracker) -> AsyncIOScheduler:
    tz = pytz.timezone(TIMEZONE)
    sched = AsyncIOScheduler(timezone=tz)
    sched.add_job(
        daily_reset,
        CronTrigger(hour=0, minute=0, timezone=tz),
        args=[tracker, bot],
        id="daily_reset",
        replace_existing=True,
    )
    for hh, mm in EVENT_TIMES:
        sched.add_job(
            event_check,
            CronTrigger(hour=hh, minute=mm, timezone=tz),
            args=[bot],
            id=f"event_{hh:02d}{mm:02d}",
            replace_existing=True,
        )
    # Periodic flush every 30s as safety net
    sched.add_job(tracker.flush_all, "interval", seconds=30, id="periodic_flush", replace_existing=True)
    return sched
