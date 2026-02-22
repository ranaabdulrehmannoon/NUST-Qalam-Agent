"""ORM models for Qalam monitoring data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Course(Base):
    """Course entity holding unique course metadata and aggregate attendance."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    course_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    instructor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attendance_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    quizzes: Mapped[list[Quiz]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attendance_records: Mapped[list[AttendanceRecord]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Quiz(Base):
    """Quiz marks for a course."""

    __tablename__ = "quizzes"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "title",
            "assessment_type",
            name="uq_quiz_course_title",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(20), nullable=False, default="Lecture")
    obtained_mark: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    total_mark: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    class_average: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    course: Mapped[Course] = relationship(back_populates="quizzes")


class Assignment(Base):
    """Assignment marks for a course."""

    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "title",
            "assessment_type",
            name="uq_assignment_course_title",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(20), nullable=False, default="Lecture")
    obtained_mark: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    total_mark: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    class_average: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    course: Mapped[Course] = relationship(back_populates="assignments")


class AttendanceRecord(Base):
    """Daily attendance record for a course session (each day/session tracked separately)."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "attendance_date",
            "session_number",
            "session_type",
            name="uq_attendance_course_date_session",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    session_number: Mapped[int] = mapped_column(nullable=False, default=1)
    session_type: Mapped[str] = mapped_column(String(20), nullable=False, default="Lecture")
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    course: Mapped[Course] = relationship(back_populates="attendance_records")


class Invoice(Base):
    """Student invoice details (tuition, fees, etc.)."""

    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("challan_id", name="uq_invoice_challan_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    term: Mapped[str | None] = mapped_column(String(100), nullable=True)
    challan_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    challan_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    scholarship_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    payable_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)

