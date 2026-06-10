# Telegram Interaction Bot (aiogram 3 + SQLite)

Bot theo dõi tương tác chat trong group Telegram, tự phát giftcode theo mốc, có anti-spam, danh hiệu, top hôm nay và quản trị admin. Chạy polling 24/7 trên Render.

## Cấu trúc

```
bot/
├── main.py              # entrypoint (polling)
├── config.py            # đọc .env
├── database.py          # SQLite (aiosqlite)
├── rewards.py           # bảng mốc thưởng + danh hiệu
├── scheduler.py         # APScheduler (reset 00:00 VN, event 12:00/20:30/23:59)
├── services/tracker.py  # đếm tương tác + anti-spam + flush 8s
├── handlers/
│   ├── user.py          # /start /checktt /stats (private)
│   ├── admin.py         # /admin /addcode /stock /bantt /unbantt
│   └── group.py         # đếm tin trong các group được cấu hình
├── requirements.txt
├── render.yaml
├── Procfile
└── .env.example
```

## Cấu hình `.env`

```
BOT_TOKEN=123:abcdef
ADMIN_ID=123456789
GROUP_IDS=-1001234567890,-1009876543210
```

## Chạy local

```bash
cd bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # điền BOT_TOKEN, ADMIN_ID, GROUP_IDS
python -m bot.main
```

Lưu ý: chạy từ thư mục cha (project root) hoặc package path `bot.main` vẫn hoạt động vì `bot/` là package.

## Deploy Render (Background Worker, polling — KHÔNG webhook)

1. Push repo lên GitHub (kèm thư mục `bot/`).
2. Vào https://dashboard.render.com → **New +** → **Blueprint** → chọn repo. Render đọc `bot/render.yaml`.
   - Nếu không dùng Blueprint: **New +** → **Background Worker** → repo của bạn → cài thủ công:
     - Environment: `Python 3`
     - Build Command: `pip install -r bot/requirements.txt`
     - Start Command: `python -m bot.main` (nhớ đặt Root Directory = `bot` hoặc dùng `python -m bot.main` từ root nếu để nguyên).
3. Thêm Environment Variables: `BOT_TOKEN`, `ADMIN_ID`, `GROUP_IDS`.
4. Deploy. Log sẽ in `Bot starting (polling)...`.

**Quan trọng:** dùng **Worker** (không phải Web Service) vì bot không cần mở port HTTP. Render Free Worker phù hợp; nếu cần 24/7 ổn định 100%, dùng plan trả phí (Free Worker có thể bị giới hạn giờ chạy).

## Lệnh

- `/start` (private): bật DM, hiện hướng dẫn.
- `/checktt` (private): xem tương tác cá nhân.
- `/stats` (private): top 15 hôm nay.
- `/admin` (ADMIN): menu inline.
- `/addcode <mốc> <code>` (ADMIN): thêm code vào kho. Có thể truyền nhiều code cách nhau bằng dấu cách hoặc xuống dòng.
- `/stock` (ADMIN): xem tồn kho.
- `/bantt @user` hoặc reply (ADMIN): cấm tính tương tác.
- `/unbantt @user` hoặc reply (ADMIN): bỏ cấm.

## Cơ chế

- **Anti-spam:** mỗi user tối đa 1 tin / 2s được tính. Đếm trong RAM, **flush DB mỗi 8s/user**.
- **Reward:** khi today_messages vượt mốc 100/200/... bot tự lấy code khả dụng từ `reward_codes`, đánh `used=1`, ghi vào `claimed_rewards`, DM cho user. Hết code → báo ADMIN.
- **Reset 00:00 Asia/Ho_Chi_Minh:** `today_messages=0` và `highest_reward=0` (cho phép nhận lại mốc ngày mới); `total_messages` giữ nguyên.
- **Event 12:00 / 20:30 / 23:59:** bot gửi ADMIN danh sách user ≥ 500 tin hôm nay.
