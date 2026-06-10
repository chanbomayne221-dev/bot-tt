from __future__ import annotations

import time
from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatType

from ..config import GROUP_IDS
from .. import database as db
from ..services.tracker import InteractionTracker

router = Router(name="group")


def setup(tracker: InteractionTracker) -> Router:

    @router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
    async def on_group_message(message: Message) -> None:
        chat = message.chat
        if GROUP_IDS and chat.id not in GROUP_IDS:
            return
        user = message.from_user
        if not user or user.is_bot:
            return
        await db.upsert_group(chat.id, chat.title or "")
        await tracker.on_message(user.id, user.username, user.full_name)

    return router
