from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ChatType

import database as db
from rewards import get_rank, next_milestone, get_reward_amount

router = Router(name="user")


START_TEXT = (
    "👋 Xin chào {name}!\n"
    "✅ Bạn đã kích hoạt nhận code qua DM.\n\n"
    "🎯 <b>CÁCH NHẬN CODE</b>\n\n"
    "1. Tham gia 2 nhóm sự kiện:\n"
    "   • https://t.me/txclmmgg\n"
    "   • https://t.me/clmmbankcom\n\n"
    "2. Chat đủ mốc trong nhóm → bot tự gửi code qua DM\n\n"
    "💰 <b>HỆ THỐNG GEN GIFTCODE TỰ ĐỘNG</b>\n"
    "• 100 tin = 3.5k\n"
    "• 200 tin = 5.555k\n"
    "• 300 tin = 6.5k\n"
    "• 400-900 tin: tăng 200đ mỗi 100 tin\n"
    "• từ 1000 tin: tăng 500đ mỗi 100 tin\n"
    "• 900 tin = 7.7k\n"
    "• 1000 tin = 8.2k\n"
    "• 2000 tin = 13.2k\n\n"
    "⏰ EVENT THEO GIỜ: 12:00 • 20:30 • 23:59\n"
    "✅ Điều kiện: ≥ 500 (theo /checktt)\n\n"
    "🏅 Danh hiệu: tính theo Tổng đã chat\n\n"
    "📜 Lệnh bạn dùng:\n"
    "• /checktt – xem tương tác + giftcode\n"
    "• /stats – top hôm nay\n"
    "• /start – kích hoạt nhận code qua DM\n\n"
    "🤖 Kho code: ✅ TRỰC TUYẾN\n\n"
    "Chúc bạn nhận được thật nhiều phần quà ❤️"
)


@router.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: Message) -> None:
    user = message.from_user
    if not user:
        return
    await db.ensure_user(user.id, user.username, user.full_name)
    await db.set_dm_enabled(user.id, True)
    await message.answer(START_TEXT.format(name=user.full_name))


@router.message(Command("checktt"), F.chat.type == ChatType.PRIVATE)
async def cmd_checktt(message: Message) -> None:
    user = message.from_user
    if not user:
        return
    await db.ensure_user(user.id, user.username, user.full_name)
    u = await db.get_user(user.id)
    if not u:
        await message.answer("Không tìm thấy dữ liệu.")
        return
    claimed = await db.get_claimed_milestones(user.id)
    nxt = next_milestone(u["today_messages"])
    remaining = max(0, nxt - u["today_messages"])
    claimed_str = ", ".join(str(m) for m in claimed) if claimed else "Chưa có"
    text = (
        "📊 <b>THỐNG KÊ CỦA BẠN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {u['full_name']}\n"
        f"💬 Tin hôm nay: <b>{u['today_messages']}</b>\n"
        f"📈 Tổng đã chat: <b>{u['total_messages']}</b>\n"
        f"🏅 Danh hiệu: {get_rank(u['total_messages'])}\n"
        f"🎁 Mốc code đã nhận: {claimed_str}\n\n"
        "ℹ️ Dùng /checktt trong chat riêng với bot để xem lại\n\n"
        f"🎯 Mốc kế tiếp: <b>{nxt} tin</b> (thưởng {get_reward_amount(nxt):,}đ)\n"
        f"Còn thiếu: <b>{remaining}</b> tin\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⏰ Event giờ: cần ≥ 500"
    )
    if u.get("banned_tt"):
        text += "\n\n🚫 Bạn đang bị ban tương tác."
    await message.answer(text)


@router.message(Command("stats"), F.chat.type == ChatType.PRIVATE)
async def cmd_stats(message: Message) -> None:
    from datetime import datetime
    import pytz
    from ..config import TIMEZONE
    top = await db.get_top_today(15)
    total = await db.get_today_total()
    today = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
    lines = [
        "📈 <b>TOP TƯƠNG TÁC HÔM NAY</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📅 Ngày: {today}",
        f"🧮 Tổng tin: {total}",
        "",
    ]
    if not top:
        lines.append("Chưa có dữ liệu hôm nay.")
    else:
        for i, u in enumerate(top, 1):
            name = u.get("full_name") or (u.get("username") and "@" + u["username"]) or str(u["user_id"])
            lines.append(f"{i}. {name} – {u['today_messages']} tin")
    await message.answer("\n".join(lines))
