import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_PHONE_NUMBER = os.environ["TWILIO_PHONE_NUMBER"]

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///gratitude.db")
NIGHTLY_HOUR = int(os.environ.get("NIGHTLY_HOUR", "21"))
NIGHTLY_MINUTE = int(os.environ.get("NIGHTLY_MINUTE", "0"))
TIMEZONE = os.environ.get("TIMEZONE", "America/New_York")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
VALIDATE_TWILIO = os.environ.get("VALIDATE_TWILIO", "true").lower() == "true"
