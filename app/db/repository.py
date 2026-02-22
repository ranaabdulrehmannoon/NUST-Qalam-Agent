"""Repository layer for persisting scraped Qalam data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..security.validation import ValidationError, validate_percentage
from .models import Assignment, AttendanceRecord, Course, Invoice, Quiz


class RepositoryError(RuntimeError):
    """Raised when persistence operations fail."""


def _to_decimal(value: float | int | str | None) -> Decimal | None:
    """Convert numeric-like values to Decimal safely."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise RepositoryError("Boolean value is not valid numeric input")
    if not isinstance(value, (float, int, str)):
        raise RepositoryError("Invalid numeric type in payload")
    return Decimal(str(value))


def _to_percentage_decimal(value: float | int | str | None) -> Decimal | None:
    """Convert and validate percentage values before storing."""
    if value is None:
        return None
    try:
        return Decimal(str(validate_percentage(float(value))))
    except (ValidationError, ValueError, TypeError) as exc:
        raise RepositoryError("Invalid percentage value in payload") from exc


def save_course(session: Session, payload: dict[str, Any]) -> Course:
    """Create or update a course by unique course name."""
    try:
        course = session.scalar(
            select(Course).where(Course.course_name == payload["name"])
        )
        if course is None:
            course = Course(
                course_name=payload["name"],
                course_url=payload.get("url"),
                instructor=payload.get("instructor"),
            )
            session.add(course)
            session.flush()
        else:
            course.course_url = payload.get("url")
            course.instructor = payload.get("instructor")

        return course
    except SQLAlchemyError as exc:
        raise RepositoryError("Failed to save course") from exc


def save_quizzes(session: Session, course: Course, payloads: list[dict[str, Any]]) -> None:
    """Create or update quiz rows for a course."""
    try:
        for payload in payloads:
            assessment_type = payload.get("assessment_type", "Lecture")
            quiz = session.scalar(
                select(Quiz).where(
                    Quiz.course_id == course.id,
                    Quiz.title == payload["title"],
                    Quiz.assessment_type == assessment_type,
                )
            )
            if quiz is None:
                quiz = Quiz(
                    course_id=course.id,
                    title=payload["title"],
                    assessment_type=assessment_type,
                )
                session.add(quiz)
            else:
                quiz.assessment_type = assessment_type

            quiz.obtained_mark = _to_decimal(payload.get("obtained_mark"))
            quiz.total_mark = _to_decimal(payload.get("total_mark"))
            quiz.class_average = _to_decimal(payload.get("class_average"))
            quiz.percentage = _to_percentage_decimal(payload.get("percentage"))
    except SQLAlchemyError as exc:
        raise RepositoryError("Failed to save quizzes") from exc


def save_assignments(session: Session, course: Course, payloads: list[dict[str, Any]]) -> None:
    """Create or update assignment rows for a course."""
    try:
        for payload in payloads:
            assessment_type = payload.get("assessment_type", "Lecture")
            assignment = session.scalar(
                select(Assignment).where(
                    Assignment.course_id == course.id,
                    Assignment.title == payload["title"],
                    Assignment.assessment_type == assessment_type,
                )
            )
            if assignment is None:
                assignment = Assignment(
                    course_id=course.id,
                    title=payload["title"],
                    assessment_type=assessment_type,
                )
                session.add(assignment)
            else:
                assignment.assessment_type = assessment_type

            assignment.obtained_mark = _to_decimal(payload.get("obtained_mark"))
            assignment.total_mark = _to_decimal(payload.get("total_mark"))
            assignment.class_average = _to_decimal(payload.get("class_average"))
            assignment.percentage = _to_percentage_decimal(payload.get("percentage"))
    except SQLAlchemyError as exc:
        raise RepositoryError("Failed to save assignments") from exc


def save_attendance(
    session: Session,
    course: Course,
    attendance_percentage: float | int | None,
    records: list[dict[str, Any]],
) -> None:
    """Persist attendance percentage and daily records."""
    try:
        course.attendance_percentage = _to_percentage_decimal(attendance_percentage)

        for payload in records:
            record_date = date.fromisoformat(str(payload["attendance_date"]))
            session_num = int(payload.get("session_number", 1))
            session_type = str(payload.get("session_type", "Lecture"))
            record = session.scalar(
                select(AttendanceRecord).where(
                    AttendanceRecord.course_id == course.id,
                    AttendanceRecord.attendance_date == record_date,
                    AttendanceRecord.session_number == session_num,
                    AttendanceRecord.session_type == session_type,
                )
            )
            if record is None:
                record = AttendanceRecord(
                    course_id=course.id,
                    attendance_date=record_date,
                    session_number=session_num,
                    session_type=session_type,
                    status=str(payload["status"]),
                )
                session.add(record)
            else:
                record.status = str(payload["status"])
                record.session_type = session_type
    except (SQLAlchemyError, ValueError, TypeError) as exc:
        raise RepositoryError("Failed to save attendance") from exc


def save_invoices(session: Session, payloads: list[dict[str, Any]]) -> None:
    """Save invoices from the student's invoice list."""
    try:
        for payload in payloads:
            # Check if invoice already exists by challan_id
            invoice = session.scalar(
                select(Invoice).where(Invoice.challan_id == payload["challan_id"])
            )
            if invoice is None:
                invoice = Invoice(
                    challan_id=payload["challan_id"],
                )
                session.add(invoice)
            
            # Update all fields
            if payload.get("invoice_date"):
                invoice.invoice_date = date.fromisoformat(str(payload["invoice_date"]))
            if payload.get("due_date"):
                invoice.due_date = date.fromisoformat(str(payload["due_date"]))
            if payload.get("paid_date"):
                invoice.paid_date = date.fromisoformat(str(payload["paid_date"]))
            
            invoice.term = payload.get("term")
            invoice.challan_type = payload.get("challan_type")
            invoice.scholarship_percentage = _to_decimal(payload.get("scholarship_percentage"))
            invoice.payable_amount = _to_decimal(payload.get("payable_amount"))
            invoice.status = payload.get("status")
            
    except (SQLAlchemyError, ValueError, TypeError) as exc:
        raise RepositoryError("Failed to save invoices") from exc

