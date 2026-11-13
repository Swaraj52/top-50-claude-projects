"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-12 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )

    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('csrf_token', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sessions_user_id'), ['user_id'], unique=False)

    op.create_table(
        'habits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('intention', sa.Text(), nullable=False),
        sa.Column('cue', sa.String(length=160), nullable=False),
        sa.Column('days', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('active', 'paused', 'archived')", name='ck_habits_status'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('habits', schema=None) as batch_op:
        batch_op.create_index('ix_habits_user_status', ['user_id', 'status'], unique=False)

    op.create_table(
        'habit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('habit_id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('note', sa.String(length=300), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('done', 'skipped')", name='ck_logs_status'),
        sa.ForeignKeyConstraint(['habit_id'], ['habits.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('habit_id', 'day', name='uq_logs_habit_day'),
    )
    with op.batch_alter_table('habit_logs', schema=None) as batch_op:
        batch_op.create_index('ix_logs_user_day', ['user_id', 'day'], unique=False)
        batch_op.create_index('ix_logs_habit_day', ['habit_id', 'day'], unique=False)

    op.create_table(
        'reflections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('mood', sa.Integer(), nullable=False),
        sa.Column('worked', sa.Text(), nullable=False),
        sa.Column('friction', sa.Text(), nullable=False),
        sa.Column('change', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('mood BETWEEN 1 AND 5', name='ck_reflections_mood'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'week_start', name='uq_reflections_user_week'),
    )

    op.create_table(
        'suggestions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('habit_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=140), nullable=False),
        sa.Column('rationale', sa.String(length=400), nullable=False),
        sa.Column('source', sa.String(length=10), nullable=False),
        sa.Column('model', sa.String(length=80), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("source IN ('local', 'claude')", name='ck_suggestions_source'),
        sa.ForeignKeyConstraint(['habit_id'], ['habits.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('suggestions', schema=None) as batch_op:
        batch_op.create_index('ix_suggestions_habit_created', ['habit_id', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('suggestions', schema=None) as batch_op:
        batch_op.drop_index('ix_suggestions_habit_created')

    op.drop_table('suggestions')

    op.drop_table('reflections')

    with op.batch_alter_table('habit_logs', schema=None) as batch_op:
        batch_op.drop_index('ix_logs_habit_day')
        batch_op.drop_index('ix_logs_user_day')

    op.drop_table('habit_logs')

    with op.batch_alter_table('habits', schema=None) as batch_op:
        batch_op.drop_index('ix_habits_user_status')

    op.drop_table('habits')

    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sessions_user_id'))

    op.drop_table('sessions')
    op.drop_table('users')
