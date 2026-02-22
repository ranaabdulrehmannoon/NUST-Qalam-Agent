"""add class_average and percentage columns to quizzes and assignments"""

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    """Add class_average and percentage columns to quizzes and assignments tables."""
    # Add columns to quizzes table
    op.add_column(
        'quizzes',
        sa.Column('class_average', sa.Numeric(precision=7, scale=2), nullable=True)
    )
    op.add_column(
        'quizzes',
        sa.Column('percentage', sa.Numeric(precision=5, scale=2), nullable=True)
    )
    
    # Add columns to assignments table
    op.add_column(
        'assignments',
        sa.Column('class_average', sa.Numeric(precision=7, scale=2), nullable=True)
    )
    op.add_column(
        'assignments',
        sa.Column('percentage', sa.Numeric(precision=5, scale=2), nullable=True)
    )


def downgrade() -> None:
    """Remove class_average and percentage columns from quizzes and assignments tables."""
    # Remove columns from assignments table
    op.drop_column('assignments', 'percentage')
    op.drop_column('assignments', 'class_average')
    
    # Remove columns from quizzes table
    op.drop_column('quizzes', 'percentage')
    op.drop_column('quizzes', 'class_average')
