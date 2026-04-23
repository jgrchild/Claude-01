"""CLI for managing users and testing the app."""
import sys
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from models import Base, GratitudeEntry, User
from sms import send_sms
from prompts import get_daily_prompt

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def add_user(phone: str, name: str = "", timezone: str = ""):
    session = Session()
    existing = session.query(User).filter_by(phone_number=phone).first()
    if existing:
        print(f"User already exists: {existing.name} ({existing.phone_number})")
        session.close()
        return
    user = User(
        phone_number=phone,
        name=name or phone,
        timezone=timezone or config.TIMEZONE,
    )
    session.add(user)
    session.commit()
    print(f"Added user: {user.name} ({user.phone_number})")
    session.close()


def list_users():
    session = Session()
    users = session.query(User).all()
    if not users:
        print("No users registered.")
    for u in users:
        status = "active" if u.active else "inactive"
        print(f"  {u.id}. {u.name} – {u.phone_number} [{status}]")
    session.close()


def send_test(phone: str):
    today = date.today()
    prompt = get_daily_prompt(today.timetuple().tm_yday)
    send_sms(phone, f"🌙 [TEST] Nightly gratitude\n\n{prompt}\n\nReply HELP for options.")
    print(f"Test message sent to {phone}")


def deactivate_user(phone: str):
    session = Session()
    user = session.query(User).filter_by(phone_number=phone).first()
    if not user:
        print(f"No user found with phone {phone}")
    else:
        user.active = False
        session.commit()
        print(f"Deactivated {user.name}")
    session.close()


USAGE = """
Usage:
  python manage.py add_user <phone> [name] [timezone]
  python manage.py list_users
  python manage.py send_test <phone>
  python manage.py deactivate <phone>

Examples:
  python manage.py add_user +12125550100 "Alice" "America/New_York"
  python manage.py send_test +12125550100
"""

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(USAGE)
        sys.exit(1)

    cmd = args[0]
    if cmd == "add_user" and len(args) >= 2:
        add_user(args[1], args[2] if len(args) > 2 else "", args[3] if len(args) > 3 else "")
    elif cmd == "list_users":
        list_users()
    elif cmd == "send_test" and len(args) >= 2:
        send_test(args[1])
    elif cmd == "deactivate" and len(args) >= 2:
        deactivate_user(args[1])
    else:
        print(USAGE)
        sys.exit(1)
