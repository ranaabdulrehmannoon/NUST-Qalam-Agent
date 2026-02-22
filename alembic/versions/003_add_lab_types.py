"""Add lab/lecture type fields for assessments and attendance.

Revision ID: 003_add_lab_types
Revises: 002_add_session_number
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "003_add_lab_types"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quizzes",
        sa.Column("assessment_type", sa.String(length=20), nullable=False, server_default="Lecture"),
    )
    op.add_column(
        "assignments",
        sa.Column("assessment_type", sa.String(length=20), nullable=False, server_default="Lecture"),
    )
    op.add_column(
        "attendance_records",
        sa.Column("session_type", sa.String(length=20), nullable=False, server_default="Lecture"),
    )

    op.drop_constraint("uq_quiz_course_title", "quizzes", type_="unique")
    op.drop_constraint("uq_assignment_course_title", "assignments", type_="unique")
    op.drop_constraint("uq_attendance_course_date_session", "attendance_records", type_="unique")

    op.create_unique_constraint(
        "uq_quiz_course_title",
        "quizzes",
        ["course_id", "title", "assessment_type"],
    )
    op.create_unique_constraint(
        "uq_assignment_course_title",
        "assignments",
        ["course_id", "title", "assessment_type"],
    )
    op.create_unique_constraint(
        "uq_attendance_course_date_session",
        "attendance_records",
        ["course_id", "attendance_date", "session_number", "session_type"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_quiz_course_title", "quizzes", type_="unique")
    op.drop_constraint("uq_assignment_course_title", "assignments", type_="unique")
    op.drop_constraint("uq_attendance_course_date_session", "attendance_records", type_="unique")

    op.create_unique_constraint(
        "uq_quiz_course_title",
        "quizzes",
        ["course_id", "title"],
    )
    op.create_unique_constraint(
        "uq_assignment_course_title",
        "assignments",
        ["course_id", "title"],
    )
    op.create_unique_constraint(
        "uq_attendance_course_date_session",
        "attendance_records",
        ["course_id", "attendance_date", "session_number"],
    )

    op.drop_column("attendance_records", "session_type")
    op.drop_column("assignments", "assessment_type")
    op.drop_column("quizzes", "assessment_type")
