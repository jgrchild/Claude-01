import json
import logging
import os
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request
from pywebpush import WebPushException, webpush
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from models import Base, GratitudeEntry, PushSubscription, User
from prompts import get_daily_prompt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


# ── helpers ───────────────────────────────────────────────────────────────────

def get_or_create_user(session) -> User:
    user = session.query(User).filter_by(active=True).first()
    if not user:
        user = User(name="Me")
        session.add(user)
        session.commit()
    return user


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
        return "Write your first entry to start a streak 🌱"
    if n == 1:
        return "1-day streak – great start! 🌱"
    if n < 7:
        return f"{n}-day streak – keep going! 💪"
    if n < 30:
        return f"{n}-day streak! 🔥"
    return f"{n}-day streak! 🏆 Incredible!"


# ── push notifications ────────────────────────────────────────────────────────

def send_push(subscription_info: dict, title: str, body: str):
    if not config.VAPID_PRIVATE_KEY or not config.VAPID_PUBLIC_KEY:
        log.warning("VAPID keys not configured – skipping push notification")
        return
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=config.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": config.VAPID_EMAIL},
        )
    except WebPushException as e:
        log.error("Push notification failed: %s", e)


def send_nightly_notification():
    today = date.today()
    prompt = get_daily_prompt(today.timetuple().tm_yday)

    session = Session()
    try:
        subs = session.query(PushSubscription).all()
        for sub in subs:
            send_push(json.loads(sub.subscription_json), "🌙 Gratitude time", prompt)
        log.info("Sent nightly notification to %d subscribers", len(subs))
    finally:
        session.close()


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    today = date.today()
    prompt = get_daily_prompt(today.timetuple().tm_yday)

    session = Session()
    try:
        user = get_or_create_user(session)
        entry = session.query(GratitudeEntry).filter_by(user_id=user.id, date=today).first()
        streak = get_streak(session, user)
        return render_template(
            "index.html",
            today=today,
            prompt=prompt,
            entry=entry,
            streak=streak,
            streak_msg=streak_msg(streak),
            vapid_public_key=config.VAPID_PUBLIC_KEY,
        )
    finally:
        session.close()


@app.route("/entry", methods=["POST"])
def save_entry():
    content = (request.json or {}).get("content", "").strip()
    if not content:
        return jsonify({"error": "Entry cannot be empty"}), 400

    today = date.today()
    session = Session()
    try:
        user = get_or_create_user(session)
        entry = session.query(GratitudeEntry).filter_by(user_id=user.id, date=today).first()
        if entry:
            entry.content = content
        else:
            entry = GratitudeEntry(user_id=user.id, date=today, content=content)
            session.add(entry)
        session.commit()
        streak = get_streak(session, user)
        return jsonify({"streak": streak, "streak_msg": streak_msg(streak)})
    finally:
        session.close()


@app.route("/history")
def history():
    session = Session()
    try:
        user = get_or_create_user(session)
        entries = (
            session.query(GratitudeEntry)
            .filter_by(user_id=user.id)
            .order_by(GratitudeEntry.date.desc())
            .limit(60)
            .all()
        )
        streak = get_streak(session, user)
        return render_template(
            "history.html",
            entries=entries,
            streak=streak,
            streak_msg=streak_msg(streak),
        )
    finally:
        session.close()


@app.route("/subscribe", methods=["POST"])
def subscribe():
    sub_data = request.json
    if not sub_data:
        return jsonify({"error": "No subscription data"}), 400

    sub_json = json.dumps(sub_data, sort_keys=True)
    session = Session()
    try:
        if not session.query(PushSubscription).filter_by(subscription_json=sub_json).first():
            session.add(PushSubscription(subscription_json=sub_json))
            session.commit()
    finally:
        session.close()

    return jsonify({"ok": True})


@app.route("/health")
def health():
    return {"status": "ok"}, 200


# ── scheduler ─────────────────────────────────────────────────────────────────

def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(
        send_nightly_notification,
        "cron",
        hour=config.NIGHTLY_HOUR,
        minute=config.NIGHTLY_MINUTE,
        id="nightly",
    )
    scheduler.start()
    log.info(
        "Scheduler started – nightly notification at %02d:%02d %s",
        config.NIGHTLY_HOUR,
        config.NIGHTLY_MINUTE,
        config.TIMEZONE,
    )
    return scheduler


if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    _scheduler = start_scheduler()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, use_reloader=False)
