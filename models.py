from datetime import date, datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), default="Me")
    timezone = Column(String(50), default="America/New_York")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    entries = relationship("GratitudeEntry", back_populates="user", order_by="GratitudeEntry.date.desc()")


class GratitudeEntry(Base):
    __tablename__ = "gratitude_entries"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="entries")


class MoodEntry(Base):
    __tablename__ = "mood_entries"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True)
    rating = Column(Integer, nullable=False)  # 1–5
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorryEntry(Base):
    __tablename__ = "worry_entries"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    content = Column(Text, nullable=False)
    reframe = Column(Text)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class WinEntry(Base):
    __tablename__ = "win_entries"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True)
    subscription_json = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
