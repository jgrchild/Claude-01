import logging
import os
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

import config
from models import Base, GratitudeEntry, User
from prompts import get_daily_prompt
from sms import send_sms

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


# ── helpers ───────────────────────────────────────────────────────────────────

def get_streak(session, user: User) -> int:
    check = date.today()
    streak = 0
    while True:
        if session.query(GratitudeEntry).filter_by(user_id=user.id, date=check).first():
            streak += 1
            check -= timedelta(days=1)
        else:
            break
    return streak


def streak_msg(n: int) -> str:
    if n == 0:
        return "Start your streak tonight! 🌱"
    if n == 1:
        return "1-day streak – great start! 🌱"
    if n < 7:
        return f"{n}-day streak – keep going! 💪"
    if n < 30:
        return f"{n}-day streak! 🔥"
    return f"{n}-day streak! 🏆 Incredible!"


# ── scheduled jobs ────────────────────────────────────────────────────────────

def send_nightly_prompts():
    session = Session()
    try:
        users = session.query(User).filter_by(active=True).all()
        today = date.today()
        prompt = get_daily_prompt(today.timetuple().tm_yday)
        is_sunday = today.isoweekday() == 7

        for user in users:
            if is_sunday:
                _send_sunday_message(session, user, prompt)
            else:
                send_sms(user.phone_number, f"🌙 Nightly gratitude\n\n{prompt}\n\nReply HELP for options.")
    finally:
        session.close()


def _send_sunday_message(session, user: User, prompt: str):
    today = date.today()
    week_ago = today - timedelta(days=6)
    entries = (
        session.query(GratitudeEntry)
        .filter(GratitudeEntry.user_id == user.id, GratitudeEntry.date >= week_ago)
        .order_by(GratitudeEntry.date)
        .all()
    )
    streak = get_streak(session, user)

    lines = ["✨ Weekly Gratitude Digest\n"]
    if entries:
        for e in entries:
            preview = e.content[:70] + ("…" if len(e.content) > 70 else "")
            lines.append(f"• {e.date.strftime('%a %-d')}: {preview}")
        lines.append(f"\n{streak_msg(streak)}")
    else:
        lines.append("No entries this week – there's still tonight!")

    lines.append(f"\n🌙 This week:\n{prompt}\n\nReply HELP for options.")
    send_sms(user.phone_number, "\n".join(lines))


# ── SMS webhook ───────────────────────────────────────────────────────────────

@app.route("/sms", methods=["POST"])
def sms_webhook():
    if config.VALIDATE_TWILIO:
        validator = RequestValidator(config.TWILIO_AUTH_TOKEN)
        sig = request.headers.get("X-Twilio-Signature", "")
        if not validator.validate(request.url, request.form, sig):
            log.warning("Invalid Twilio signature from %s", request.remote_addr)
            return "Forbidden", 403

    from_number = request.form.get("From", "").strip()
    body = request.form.get("Body", "").strip()
    resp = MessagingResponse()

    session = Session()
    try:
        user = session.query(User).filter_by(phone_number=from_number, active=True).first()
        if not user:
            resp.message("You're not registered. Ask the admin to add your number.")
            return str(resp)

        cmd = body.upper().strip()

        if cmd == "HELP":
            resp.message(
                "Gratitude app commands:\n"
                "• STREAK – your current streak\n"
                "• HISTORY – your last 7 entries\n"
                "• Or just reply with today's gratitude! 🙏"
            )

        elif cmd == "STREAK":
            n = get_streak(session, user)
            resp.message(streak_msg(n))

        elif cmd == "HISTORY":
            entries = (
                session.query(GratitudeEntry)
                .filter_by(user_id=user.id)
                .order_by(GratitudeEntry.date.desc())
                .limit(7)
                .all()
            )
            if not entries:
                resp.message("No entries yet. Reply to tonight's prompt to start! 🌱")
            else:
                lines = ["Your last 7 entries:\n"]
                for e in entries:
                    preview = e.content[:60] + ("…" if len(e.content) > 60 else "")
                    lines.append(f"• {e.date.strftime('%b %-d')}: {preview}")
                resp.message("\n".join(lines))

        else:
            today = date.today()
            entry = session.query(GratitudeEntry).filter_by(user_id=user.id, date=today).first()
            if entry:
                entry.content = body
            else:
                entry = GratitudeEntry(user_id=user.id, date=today, content=body)
                session.add(entry)
            session.commit()

            n = get_streak(session, user)
            resp.message(f"✨ Saved! {streak_msg(n)}")

    finally:
        session.close()

    return str(resp)


@app.route("/health")
def health():
    return {"status": "ok"}, 200


# ── scheduler startup ─────────────────────────────────────────────────────────

def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(
        send_nightly_prompts,
        "cron",
        hour=config.NIGHTLY_HOUR,
        minute=config.NIGHTLY_MINUTE,
        id="nightly",
    )
    scheduler.start()
    log.info(
        "Scheduler started – nightly job at %02d:%02d %s",
        config.NIGHTLY_HOUR,
        config.NIGHTLY_MINUTE,
        config.TIMEZONE,
    )
    return scheduler


# Avoid double-start when Flask reloader spawns a child process
if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    _scheduler = start_scheduler()


if __name__ == "__main__":
    app.run(port=5000, use_reloader=False)
