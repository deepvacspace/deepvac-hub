"""add test_profiles

Revision ID: c1f2a9b7d3e4
Revises: 8b0250409eaf
Create Date: 2026-09-22 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f2a9b7d3e4'
down_revision: Union[str, None] = '8b0250409eaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'test_profiles',
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_test_profiles_organization_id'), 'test_profiles', ['organization_id'], unique=False,
    )
    op.create_table(
        'test_profile_steps',
        sa.Column('test_profile_id', sa.UUID(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('setpoint_temp', sa.Float(), nullable=True),
        sa.Column('setpoint_pressure', sa.Float(), nullable=True),
        sa.Column('duration_s', sa.Float(), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['test_profile_id'], ['test_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_test_profile_steps_test_profile_id'),
        'test_profile_steps', ['test_profile_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_test_profile_steps_test_profile_id'), table_name='test_profile_steps')
    op.drop_table('test_profile_steps')
    op.drop_index(op.f('ix_test_profiles_organization_id'), table_name='test_profiles')
    op.drop_table('test_profiles')
