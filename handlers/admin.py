from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatType

from .. import database as db
from ..config import ADMIN_ID

router = Router(name="admin")


def _is_admin(uid: int) -> bool:
    return uid == ADMIN_ID


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Thêm code", callback_data="adm:addcode")],
            [InlineKeyboardButton(text="📂 Xem kho code", callback_data="adm:stock")],
            [InlineKeyboardButton(text="📊 Thống kê", callback_data="adm:stats")],
            [InlineKeyboardButton(text="🚫 Ban TT", callback_data="adm:bantt"),
             InlineKeyboardButton(text="✅ Unban TT", callback_data="adm:unbantt")],
        ]
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    await message.answer("📦 <b>Quản trị kho code</b>", reply_markup=admin_menu_kb())


@router.message(Command("addcode"))
async def cmd_addcode(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Cú pháp: <code>/addcode &lt;mốc&gt; &lt;code&gt;</code>\nVD: /addcode 100 ABC123")
        return
    try:
        milestone = int(parts[1])
    except ValueError:
        await message.answer("Mốc không hợp lệ.")
        return
    code = parts[2].strip()
    if milestone < 100 or milestone % 100 != 0:
        await message.answer("Mốc phải là bội số của 100 và ≥ 100.")
        return
    if not code:
        await message.answer("Code rỗng.")
        return
    # Allow multi-line / multiple codes split by whitespace or newlines
    codes = [c.strip() for c in code.replace(",", " ").split() if c.strip()]
    for c in codes:
        await db.add_code(milestone, c)
    await message.answer(f"✅ Đã thêm {len(codes)} code vào mốc {milestone}.")


@router.message(Command("stock"))
async def cmd_stock(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    await _send_stock(message)


async def _send_stock(target: Message) -> None:
    rows = await db.stock_summary()
    if not rows:
        await target.answer("📦 KHO CODE\n\n(trống)")
        return
    lines = ["📦 <b>KHO CODE</b>", ""]
    for m, c in rows:
        lines.append(f"{m} tin: {c} code")
    await target.answer("\n".join(lines))


@router.message(Command("bantt"))
async def cmd_bantt(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    await _ban_unban(message, ban=True)


@router.message(Command("unbantt"))
async def cmd_unbantt(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    await _ban_unban(message, ban=False)


async def _ban_unban(message: Message, ban: bool) -> None:
    target_user = None
    target_name = ""
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        await db.ensure_user(u.id, u.username, u.full_name)
        target_user = await db.get_user(u.id)
        target_name = u.full_name
    else:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Cú pháp: /bantt @username (hoặc reply tin nhắn)")
            return
        username = parts[1].strip()
        target_user = await db.find_user_by_username(username)
        if not target_user:
            await message.answer("Không tìm thấy user. Họ cần chat ít nhất 1 lần để được ghi nhận.")
            return
        target_name = target_user.get("full_name") or username
    await db.set_banned(int(target_user["user_id"]), ban)
    if ban:
        await message.answer(f"🚫 Đã ban tương tác user {target_name}")
    else:
        await message.answer(f"✅ Đã mở ban tương tác user {target_name}")


@router.callback_query(F.data.startswith("adm:"))
async def admin_cb(call: CallbackQuery) -> None:
    if not call.from_user or not _is_admin(call.from_user.id):
        await call.answer("Không có quyền.", show_alert=True)
        return
    action = call.data.split(":", 1)[1]
    if action == "addcode":
        await call.message.answer("Dùng: <code>/addcode &lt;mốc&gt; &lt;code&gt;</code>")
    elif action == "stock":
        await _send_stock(call.message)
    elif action == "stats":
        s = await db.stats_global()
        await call.message.answer(
            "📊 <b>THỐNG KÊ</b>\n"
            f"👥 Users: {s['users']}\n"
            f"💬 Tổng tin: {s['total_messages']}\n"
            f"📅 Tin hôm nay: {s['today_messages']}\n"
            f"🎁 Code còn: {s['codes_left']}\n"
            f"✅ Code đã phát: {s['codes_used']}"
        )
    elif action == "bantt":
        await call.message.answer("Dùng: <code>/bantt @username</code> hoặc reply tin nhắn của user.")
    elif action == "unbantt":
        await call.message.answer("Dùng: <code>/unbantt @username</code> hoặc reply tin nhắn của user.")
    await call.answer()
