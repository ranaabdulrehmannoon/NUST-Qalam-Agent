"""Add session_number to attendance_records.

Revision ID: 002
Down Revision: 001
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add session_number column and update unique constraint."""
    # Add session_number column with default value 1
    op.add_column(
        "attendance_records",
        sa.Column("session_number", sa.Integer(), nullable=False, server_default="1")
    )
    
    # Drop the old unique constraint
    op.drop_constraint("uq_attendance_course_date", "attendance_records", type_="unique")
    
    # Add new unique constraint with session_number
    op.create_unique_constraint(
        "uq_attendance_course_date_session",
        "attendance_records",
        ["course_id", "attendance_date", "session_number"]
    )


def downgrade() -> None:
    """Revert to previous schema."""
    # Drop the new unique constraint
    op.drop_constraint("uq_attendance_course_date_session", "attendance_records", type_="unique")
    
    # Add back old unique constraint
    op.create_unique_constraint(
        "uq_attendance_course_date",
        "attendance_records",
        ["course_id", "attendance_date"]
    )
    
    # Remove session_number column
    op.drop_column("attendance_records", "session_number")
