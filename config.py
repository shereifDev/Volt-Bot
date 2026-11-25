import os
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
TIMEZONE = os.getenv("TIMEZONE", "Africa/Cairo")
LOCK_TIME = os.getenv("LOCK_TIME", "00:00")
UNLOCK_TIME = os.getenv("UNLOCK_TIME", "08:00")
OWNER_IDS = {int(x.strip()) for x in os.getenv("OWNER_IDS", "").split(",") if x.strip().isdigit()}
