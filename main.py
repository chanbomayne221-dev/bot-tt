from __future__ import annotations

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

from config import BOT_TOKEN
from database import init_db
from handlers import user as user_handlers
from handlers import admin as admin_handlers
from handlers import group as group_handlers
from services.tracker import InteractionTracker
from scheduler import setup_scheduler


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def start_health_server() -> web.AppRunner | None:
    """Bind Render's PORT for Web Service deploys while the bot keeps polling."""
    raw_port = os.getenv("PORT", "").strip()
    if not raw_port:
        return None

    try:
        port = int(raw_port)
    except ValueError:
        logging.getLogger("bot").warning("Invalid PORT value: %s", raw_port)
        return None

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.getLogger("bot").info("Health server listening on port %s", port)
    return runner


async def main() -> None:
    setup_logging()
    log = logging.getLogger("bot")

    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
    )

    dp = Dispatcher()

    tracker = InteractionTracker(bot)

    # Routers
    dp.include_router(admin_handlers.router)
    dp.include_router(user_handlers.router)
    dp.include_router(group_handlers.setup(tracker))

    # Scheduler
    scheduler = setup_scheduler(bot, tracker)
    scheduler.start()

    health_runner = await start_health_server()

    log.info("Bot starting (polling)...")

    try:
        # Xóa webhook cũ nếu có
        await bot.delete_webhook(
            drop_pending_updates=False
        )

        # Start bot polling
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )

    finally:
        log.info("Shutting down...")

        try:
            await tracker.flush_all()
        except Exception:
            pass

        scheduler.shutdown(wait=False)
        if health_runner is not None:
            await health_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
