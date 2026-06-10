import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0").strip() or 0)

_raw_groups = os.getenv("GROUP_IDS", "").strip()
GROUP_IDS: set[int] = set()
if _raw_groups:
    for part in _raw_groups.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            GROUP_IDS.add(int(part))
        except ValueError:
            pass

TIMEZONE = "Asia/Ho_Chi_Minh"
DB_PATH = os.getenv("DB_PATH", "bot_data.db")

# Anti-spam / update intervals (seconds)
MIN_INTERVAL_PER_USER = 2          # 1 message counted per 2s per user
UPDATE_DB_INTERVAL = 8             # flush interaction every 8s

# Event hours (HH:MM) - VN time
EVENT_TIMES = [(12, 0), (20, 30), (23, 59)]
EVENT_MIN_INTERACTIONS = 500

# Group links
EVENT_GROUP_LINKS = [
    "https://t.me/txclmmgg",
    "https://t.me/clmmbankcom",
]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID is not set in environment")
