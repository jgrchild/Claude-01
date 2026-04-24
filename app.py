import json
import logging
import os
import random
import re
from collections import Counter
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, render_template, request
from pywebpush import WebPushException, webpush
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from models import Base, GratitudeEntry, MoodEntry, PushSubscription, User, WinEntry, WorryEntry
from prompts import get_daily_prompt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

MOOD_EMOJIS = {1: "😔", 2: "😕", 3: "😐", 4: "🙂", 5: "😊"}

WIN_RESPONSES = [
    "That's worth celebrating. 🌱",
    "Look at you go. ⭐",
    "Every win counts, no matter the size.",
    "You showed up. That matters. 💚",
    "Progress is progress. Keep going.",
    "Noted and celebrated.",
    "That's a real win. Be proud.",
    "Small steps add up. Great work.",
    "You're doing better than you think. 🌿",
    "That deserves a moment of recognition.",
]

WORRY_STOPWORDS = {
    'a','an','the','i','my','is','it','its','that','this','of','and','to',
    'in','for','me','be','am','are','was','will','just','so','but','not',
    'about','with','at','if','on','or','do','have','what','get','got',
    'feel','feeling','keep','would','could','should','really','very',
    'when','know','think','need','want','going','been','more','some',
    'dont','cant','wont','im','ive','ill','its','they','them','their',
    'there','here','then','than','from','into','how','who','all','one',
}


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


def word_freq(entries, top_n=12):
    words = []
    for e in entries:
        for w in re.findall(r"[a-z]+", e.content.lower()):
            if len(w) > 3 and w not in WORRY_STOPWORDS:
                words.append(w)
    return Counter(words).most_common(top_n)


# ── push notifications ────────────────────────────────────────────────────────

def send_push(subscription_info: dict, title: str, body: str, url: str = "/"):
    if not config.VAPID_PRIVATE_KEY or not config.VAPID_PUBLIC_KEY:
        log.warning("VAPID keys not configured – skipping push notification")
        return
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=config.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": config.VAPID_EMAIL},
        )
    except WebPushException as e:
        log.error("Push notification failed: %s", e)


def _broadcast(title: str, body: str, url: str = "/"):
    session = Session()
    try:
        subs = session.query(PushSubscription).all()
        for sub in subs:
            send_push(json.loads(sub.subscription_json), title, body, url)
        log.info("Broadcast '%s' to %d subscribers", title, len(subs))
    finally:
        session.close()


def send_morning_notification():
    _broadcast("🌤 Good morning", "How are you feeling today? Take a moment to check in.", url="/mood")


def send_midday_notification():
    _broadcast("🌬 Midday breather", "Time for a quick breathing break. Just two minutes.", url="/breathing")


def send_worry_notification():
    _broadcast("💭 Worry time", "Your 20-minute session is ready.", url="/worry/session")


def send_nightly_notification():
    today = date.today()
    prompt = get_daily_prompt(today.timetuple().tm_yday)
    _broadcast("🌙 Evening gratitude", prompt, url="/")


# ── gratitude ─────────────────────────────────────────────────────────────────

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
            active="gratitude",
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
            active="gratitude",
            entries=entries,
            streak=streak,
            streak_msg=streak_msg(streak),
        )
    finally:
        session.close()


# ── mood ──────────────────────────────────────────────────────────────────────

@app.route("/mood")
def mood():
    today = date.today()
    week_ago = today - timedelta(days=6)
    session = Session()
    try:
        today_mood = session.query(MoodEntry).filter_by(date=today).first()
        week_moods = (
            session.query(MoodEntry)
            .filter(MoodEntry.date >= week_ago)
            .order_by(MoodEntry.date)
            .all()
        )
        week_map = {m.date: m for m in week_moods}
        week_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        return render_template(
            "mood.html",
            active="mood",
            today=today,
            today_mood=today_mood,
            week_days=week_days,
            week_map=week_map,
            mood_emojis=MOOD_EMOJIS,
        )
    finally:
        session.close()


@app.route("/api/mood", methods=["POST"])
def save_mood():
    data = request.json or {}
    rating = data.get("rating")
    note = data.get("note", "").strip()
    if not rating or int(rating) not in range(1, 6):
        return jsonify({"error": "Rating must be 1-5"}), 400
    session = Session()
    try:
        today = date.today()
        entry = session.query(MoodEntry).filter_by(date=today).first()
        if entry:
            entry.rating = int(rating)
            entry.note = note or None
        else:
            session.add(MoodEntry(date=today, rating=int(rating), note=note or None))
        session.commit()
        return jsonify({"ok": True, "emoji": MOOD_EMOJIS[int(rating)]})
    finally:
        session.close()


# ── worry ─────────────────────────────────────────────────────────────────────

@app.route("/worry")
def worry():
    session = Session()
    try:
        open_worries = (
            session.query(WorryEntry)
            .filter_by(resolved=False)
            .order_by(WorryEntry.created_at.desc())
            .all()
        )
        return render_template(
            "worry.html",
            active="worry",
            open_worries=open_worries,
            open_count=len(open_worries),
        )
    finally:
        session.close()


@app.route("/worry/session")
def worry_session():
    session = Session()
    try:
        open_worries = (
            session.query(WorryEntry)
            .filter_by(resolved=False)
            .order_by(WorryEntry.created_at.asc())
            .all()
        )
        worries_json = json.dumps([
            {"id": w.id, "content": w.content, "date": str(w.date)}
            for w in open_worries
        ])
        return render_template(
            "worry_session.html",
            active="worry",
            worry_count=len(open_worries),
            worries_json=worries_json,
        )
    finally:
        session.close()


@app.route("/worry/patterns")
def worry_patterns():
    week_ago = date.today() - timedelta(days=6)
    session = Session()
    try:
        entries = session.query(WorryEntry).filter(WorryEntry.date >= week_ago).all()
        themes = word_freq(entries)
        max_count = themes[0][1] if themes else 1
        return render_template(
            "worry_patterns.html",
            active="worry",
            themes=themes,
            max_count=max_count,
            entry_count=len(entries),
        )
    finally:
        session.close()


@app.route("/api/worry", methods=["POST"])
def save_worry():
    data = request.json or {}
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Content required"}), 400
    session = Session()
    try:
        entry = WorryEntry(date=date.today(), content=content)
        session.add(entry)
        session.commit()
        return jsonify({"ok": True, "id": entry.id})
    finally:
        session.close()


@app.route("/api/worry/<int:worry_id>/classify", methods=["POST"])
def classify_worry(worry_id):
    data = request.json or {}
    category = data.get("category")
    action = data.get("action", "").strip()
    if category not in ("real", "hypothetical"):
        return jsonify({"error": "category must be real or hypothetical"}), 400
    session = Session()
    try:
        entry = session.query(WorryEntry).filter_by(id=worry_id).first()
        if not entry:
            return jsonify({"error": "Not found"}), 404
        entry.category = category
        entry.action = action or None
        entry.resolved = True
        session.commit()
        return jsonify({"ok": True})
    finally:
        session.close()


@app.route("/api/worry/<int:worry_id>/skip", methods=["POST"])
def skip_worry(worry_id):
    session = Session()
    try:
        entry = session.query(WorryEntry).filter_by(id=worry_id).first()
        if not entry:
            return jsonify({"error": "Not found"}), 404
        entry.skipped = True
        session.commit()
        return jsonify({"ok": True})
    finally:
        session.close()


@app.route("/api/worry/<int:worry_id>/resolve", methods=["POST"])
def resolve_worry(worry_id):
    session = Session()
    try:
        entry = session.query(WorryEntry).filter_by(id=worry_id).first()
        if not entry:
            return jsonify({"error": "Not found"}), 404
        entry.resolved = True
        session.commit()
        return jsonify({"ok": True})
    finally:
        session.close()


# ── wins ──────────────────────────────────────────────────────────────────────

@app.route("/wins")
def wins():
    today = date.today()
    week_ago = today - timedelta(days=6)
    session = Session()
    try:
        recent_wins = (
            session.query(WinEntry)
            .filter(WinEntry.date >= week_ago)
            .order_by(WinEntry.created_at.desc())
            .all()
        )
        return render_template("wins.html", active="wins", today=today, recent_wins=recent_wins)
    finally:
        session.close()


@app.route("/api/wins", methods=["POST"])
def save_win():
    content = (request.json or {}).get("content", "").strip()
    if not content:
        return jsonify({"error": "Content required"}), 400
    session = Session()
    try:
        session.add(WinEntry(date=date.today(), content=content))
        session.commit()
        return jsonify({"ok": True, "response": random.choice(WIN_RESPONSES)})
    finally:
        session.close()


# ── breathing ─────────────────────────────────────────────────────────────────

@app.route("/breathing")
def breathing():
    return render_template("breathing.html", active="breathing")


# ── push subscription ─────────────────────────────────────────────────────────

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
    scheduler.add_job(send_morning_notification, "cron",
                      hour=config.MORNING_HOUR, minute=config.MORNING_MINUTE, id="morning")
    scheduler.add_job(send_midday_notification, "cron",
                      hour=config.MIDDAY_HOUR, minute=config.MIDDAY_MINUTE, id="midday")
    scheduler.add_job(send_worry_notification, "cron",
                      hour=config.WORRY_HOUR, minute=config.WORRY_MINUTE, id="worry")
    scheduler.add_job(send_nightly_notification, "cron",
                      hour=config.NIGHTLY_HOUR, minute=config.NIGHTLY_MINUTE, id="nightly")
    scheduler.start()
    log.info("Scheduler started — 4 daily notifications configured")
    return scheduler


if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    _scheduler = start_scheduler()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, use_reloader=False)
