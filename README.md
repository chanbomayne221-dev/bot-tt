# Telegram Interaction Bot (aiogram 3 + Supabase Postgres)

Bot theo dõi tương tác trong group Telegram, trao giftcode theo mốc, ranking, ban/unban, chạy 24/7 trên Render bằng polling.

## 1. Tạo Supabase project (làm DB)

1. Vào https://supabase.com → **New project** → đặt password mạnh, chọn region gần (Singapore).
2. Đợi project tạo xong → vào **Project Settings → Database → Connection string**.
3. Chọn tab **Transaction pooler** (port **6543**) — bắt buộc cho Render vì connection ổn định hơn.
4. Copy URI, ví dụ:
   ```
   postgresql://postgres.abcdxyz:YOUR-PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```
5. Thay `YOUR-PASSWORD` bằng password DB bạn vừa đặt.

> Schema bảng sẽ tự tạo lần đầu bot chạy (`init_db()`).

## 2. Tạo bot Telegram

- Mở @BotFather → `/newbot` → copy `BOT_TOKEN`.
- Lấy `ADMIN_ID` của bạn từ @userinfobot.
- Thêm bot vào group, bật quyền đọc tin nhắn (tắt Privacy Mode trong BotFather: `/setprivacy` → Disable).
- Lấy `group_id` (số âm bắt đầu bằng `-100...`).

## 3. Cấu hình local (tuỳ chọn để test)

```bash
cd bot
cp .env.example .env
# điền BOT_TOKEN, ADMIN_ID, GROUP_IDS, DATABASE_URL
pip install -r requirements.txt
python -m bot.main
```

## 4. Deploy Render

1. Push repo lên GitHub.
2. Vào https://render.com → **New → Background Worker** → connect repo.
3. Render sẽ đọc `render.yaml`. Set các Environment Variables:
   - `BOT_TOKEN`
   - `ADMIN_ID`
   - `GROUP_IDS` (cách nhau dấu phẩy)
   - `DATABASE_URL` (connection string Supabase ở bước 1)
4. Deploy. Log sẽ hiện `Bot starting (polling)...`.

## 5. Lệnh chính

- `/start` (DM): bật DM + xem hướng dẫn
- `/checktt` (DM): xem tương tác + rank + mốc tiếp theo
- `/stats`: top 15 hôm nay
- `/admin`: menu quản trị (chỉ ADMIN_ID)
- `/addcode <mốc> <code>`: nạp giftcode (admin)
- `/bantt @user` / `/unbantt @user`: ban/unban tương tác

## Lưu ý

- Dùng **Transaction Pooler** (6543) → đã set `statement_cache_size=0` để tương thích pgbouncer.
- Reset `today_messages` chạy lúc 00:00 giờ VN mỗi ngày.
- Dữ liệu persist trong Supabase, deploy lại Render KHÔNG mất data.
