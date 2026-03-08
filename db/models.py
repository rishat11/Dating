"""SQLAlchemy models: users, matches, messages, destiny_index, destiny_events."""
from datetime import date, datetime
from enum import Enum
from typing import Optional


def age_from_birth_date(birth_date: Optional[datetime]) -> Optional[int]:
    """Возраст в полных годах на сегодня. Если birth_date нет — None."""
    if birth_date is None:
        return None
    today = date.today()
    bd = birth_date.date() if hasattr(birth_date, "date") else birth_date
    age = today.year - bd.year
    if (today.month, today.day) < (bd.month, bd.day):
        age -= 1
    return age


# Границы знаков зодиака (тропический зодиак): день начала (месяц, день) и ключ знака по порядку года
_ZODIAC_BOUNDS = [
    ((1, 20), "aquarius"),   # Водолей
    ((2, 19), "pisces"),     # Рыбы
    ((3, 21), "aries"),      # Овен
    ((4, 20), "taurus"),     # Телец
    ((5, 21), "gemini"),     # Близнецы
    ((6, 21), "cancer"),     # Рак
    ((7, 23), "leo"),        # Лев
    ((8, 23), "virgo"),      # Дева
    ((9, 23), "libra"),      # Весы
    ((10, 23), "scorpio"),   # Скорпион
    ((11, 22), "sagittarius"),  # Стрелец
    ((12, 22), "capricorn"),   # Козерог
]


def zodiac_from_birth_date(birth_date: Optional[datetime]) -> Optional[str]:
    """Знак зодиака по дате рождения (ключ для i18n: capricorn, aquarius, ...)."""
    if birth_date is None:
        return None
    bd = birth_date.date() if hasattr(birth_date, "date") else birth_date
    m, d = bd.month, bd.day
    # Козерог: 22.12 — 19.01
    if (m, d) >= (12, 22) or (m, d) < (1, 20):
        return "capricorn"
    last = "aquarius"
    for (sm, sd), sign in _ZODIAC_BOUNDS:
        if (m, d) >= (sm, sd):
            last = sign
    return last

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Gender(str, Enum):
    M = "M"
    F = "F"
    OTHER = "other"


class MatchStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    ENDED = "ended"


class MessageType(str, Enum):
    TEXT = "text"
    PHOTO = "photo"
    VOICE = "voice"
    STICKER = "sticker"
    ANIMATION = "animation"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255))
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    birth_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    age_confirmed_18: Mapped[bool] = mapped_column(Boolean, default=False)
    rules_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    locale: Mapped[str] = mapped_column(String(5), default="ru")  # ru / en

    # Геолокация (опционально)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Анкета
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    looking_for: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # M, F, all
    city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    profile_photo_file_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    interests: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)  # comma-separated tags
    movies_music: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)  # deprecated, use movies/series/music
    movies: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    series: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    music: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    zodiac: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    profile_filled: Mapped[bool] = mapped_column(Boolean, default=False)

    matches_as_1: Mapped[list["Match"]] = relationship(
        "Match", foreign_keys="Match.user_1_id", back_populates="user_1"
    )
    matches_as_2: Mapped[list["Match"]] = relationship(
        "Match", foreign_keys="Match.user_2_id", back_populates="user_2"
    )
    likes_sent: Mapped[list["Like"]] = relationship(
        "Like", foreign_keys="Like.sender_id", back_populates="sender"
    )
    likes_received: Mapped[list["Like"]] = relationship(
        "Like", foreign_keys="Like.receiver_id", back_populates="receiver"
    )

    def is_registered(self) -> bool:
        return (
            self.first_name is not None
            and self.age_confirmed_18
            and self.rules_accepted
        )

    def is_profile_filled(self) -> bool:
        return bool(
            self.profile_filled
            and self.display_name
            and self.age is not None
            and self.gender
            and self.looking_for
            and self.profile_photo_file_id
        )


class Like(Base):
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id], back_populates="likes_sent")
    receiver: Mapped["User"] = relationship("User", foreign_keys=[receiver_id], back_populates="likes_received")

    __table_args__ = (Index("ix_likes_sender_receiver", "sender_id", "receiver_id", unique=True),)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_1_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_2_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default=MatchStatus.ACTIVE.value)
    blocked_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user_1: Mapped["User"] = relationship("User", foreign_keys=[user_1_id], back_populates="matches_as_1")
    user_2: Mapped["User"] = relationship("User", foreign_keys=[user_2_id], back_populates="matches_as_2")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="match")
    destiny_index: Mapped[Optional["DestinyIndex"]] = relationship(
        "DestinyIndex", back_populates="match", uselist=False
    )

    __table_args__ = (
        Index("ix_matches_user_1_user_2", "user_1_id", "user_2_id", unique=True),
        Index("ix_matches_status", "status"),
        Index("ix_matches_created_at", "created_at"),
    )

    def partner_of(self, user_id: int) -> Optional["User"]:
        if self.user_1_id == user_id:
            return self.user_2
        if self.user_2_id == user_id:
            return self.user_1
        return None

    def other_user_id(self, user_id: int) -> int:
        return self.user_2_id if self.user_1_id == user_id else self.user_1_id


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(20), default=MessageType.TEXT.value)
    length: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    file_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recipient_delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    match: Mapped["Match"] = relationship("Match", back_populates="messages")

    __table_args__ = (Index("ix_messages_match_created", "match_id", "created_at"),)


class DestinyIndex(Base):
    __tablename__ = "destiny_index"

    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    current_percent: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    frozen_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    flag_playlist: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_challenges: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_cloud: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_voting: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_pdf: Mapped[bool] = mapped_column(Boolean, default=False)

    match: Mapped["Match"] = relationship("Match", back_populates="destiny_index")


class DestinyEvent(Base):
    __tablename__ = "destiny_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    delta: Mapped[float] = mapped_column(Float)
    reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_destiny_events_updated", "match_id", "created_at"),)
