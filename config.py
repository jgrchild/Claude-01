import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///gratitude.db")
TIMEZONE = os.environ.get("TIMEZONE", "America/New_York")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")

MORNING_HOUR = int(os.environ.get("MORNING_HOUR", "8"))
MORNING_MINUTE = int(os.environ.get("MORNING_MINUTE", "0"))
MIDDAY_HOUR = int(os.environ.get("MIDDAY_HOUR", "14"))
MIDDAY_MINUTE = int(os.environ.get("MIDDAY_MINUTE", "0"))
WORRY_HOUR = int(os.environ.get("WORRY_HOUR", "19"))
WORRY_MINUTE = int(os.environ.get("WORRY_MINUTE", "0"))
NIGHTLY_HOUR = int(os.environ.get("NIGHTLY_HOUR", "21"))
NIGHTLY_MINUTE = int(os.environ.get("NIGHTLY_MINUTE", "0"))

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_EMAIL = os.environ.get("VAPID_EMAIL", "mailto:user@example.com")
