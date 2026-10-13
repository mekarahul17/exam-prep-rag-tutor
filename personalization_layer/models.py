"""
SQLAlchemy ORM models for student profiles and topic-wise mastery.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    grade: Mapped[str] = mapped_column(String, default="")
    preferred_language: Mapped[str] = mapped_column(String, default="en")

    mastery_records: Mapped[list["TopicMastery"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )

    interactions: Mapped[list["InteractionLog"]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )


class TopicMastery(Base):
    __tablename__ = "topic_mastery"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.id")
    )

    subject: Mapped[str] = mapped_column(String)
    topic: Mapped[str] = mapped_column(String)

    mastery_score: Mapped[float] = mapped_column(
        Float,
        default=0.5,
    )

    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )

    student: Mapped["Student"] = relationship(
        back_populates="mastery_records"
    )


class InteractionLog(Base):
    __tablename__ = "interaction_log"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.id")
    )

    subject: Mapped[str] = mapped_column(String)
    topic: Mapped[str] = mapped_column(String)
    correct: Mapped[bool] = mapped_column(Boolean)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )

    student: Mapped["Student"] = relationship(
        back_populates="interactions"
    )