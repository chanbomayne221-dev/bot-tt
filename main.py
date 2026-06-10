from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

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

    dp.include_router(admin_handlers.router)
    dp.include_router(user_handlers.router)
    dp.include_router(group_handlers.setup(tracker))

    scheduler = setup_scheduler(bot, tracker)
    scheduler.start()

    log.info("Bot starting (polling)...")

    try:
        await bot.delete_webhook(drop_pending_updates=False)

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
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
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

    log.info("Bot starting (polling)...")

    try:
        # đảm bảo polling chạy ổn
        await bot.delete_webhook(
            drop_pending_updates=False
        )

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
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
```
