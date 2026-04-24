"""CLI for managing the gratitude journal."""
import sys
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from models import Base, GratitudeEntry, User
from prompts import get_daily_prompt

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def show_info():
    session = Session()
    user = session.query(User).filter_by(active=True).first()
    if not user:
        print("No user yet – start the app and visit http://localhost:5000 to create one.")
    else:
        count = session.query(GratitudeEntry).filter_by(user_id=user.id).count()
        print(f"User: {user.name}")
        print(f"Total entries: {count}")
    session.close()


def show_today():
    today = date.today()
    prompt = get_daily_prompt(today.timetuple().tm_yday)
    print(f"Today's prompt ({today}):\n  {prompt}")


def clear_entries():
    confirm = input("Delete ALL entries? Type YES to confirm: ")
    if confirm.strip() != "YES":
        print("Cancelled.")
        return
    session = Session()
    deleted = session.query(GratitudeEntry).delete()
    session.commit()
    session.close()
    print(f"Deleted {deleted} entries.")


def migrate():
    """Add columns introduced in the Worry Time CBT update.

    Safe to run on both fresh and existing databases — each ALTER TABLE is
    attempted independently and silently skipped if the column already exists.
    """
    migrations = [
        ("worry_entries", "category",  "VARCHAR(20)"),
        ("worry_entries", "action",    "TEXT"),
        ("worry_entries", "skipped",   "BOOLEAN DEFAULT 0"),
        ("worry_entries", "resolved",  "BOOLEAN DEFAULT 0"),
        ("worry_entries", "reframe",   "TEXT"),
        ("mood_entries",  "note",      "TEXT"),
    ]

    with engine.connect() as conn:
        for table, column, col_type in migrations:
            try:
                conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
                    )
                )
                conn.commit()
                print(f"  ✓ {table}.{column} added")
            except Exception as exc:
                msg = str(exc).lower()
                if "duplicate column" in msg or "already exists" in msg:
                    print(f"  – {table}.{column} already exists, skipped")
                else:
                    print(f"  ✗ {table}.{column} failed: {exc}")

    print("Migration complete.")


USAGE = """
Usage:
  python manage.py info           – show user info and entry count
  python manage.py today          – show today's prompt
  python manage.py clear_entries  – delete all journal entries (careful!)
  python manage.py migrate        – add new DB columns (safe to re-run)
"""

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(USAGE)
        sys.exit(1)

    cmd = args[0]
    if cmd == "info":
        show_info()
    elif cmd == "today":
        show_today()
    elif cmd == "clear_entries":
        clear_entries()
    elif cmd == "migrate":
        migrate()
    else:
        print(USAGE)
        sys.exit(1)
