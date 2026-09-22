"""add alarm_rules

Revision ID: e7a1c3d9f5b2
Revises: d4e8f0a2b6c1
Create Date: 2026-09-22 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a1c3d9f5b2'
down_revision: Union[str, None] = 'd4e8f0a2b6c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'alarm_rules',
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('chamber_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('variable', sa.String(length=200), nullable=False),
        sa.Column('condition', sa.String(length=50), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('value2', sa.Float(), nullable=True),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('deadband', sa.Float(), nullable=False),
        sa.Column('delay_s', sa.Float(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['chamber_id'], ['chambers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_alarm_rules_organization_id'), 'alarm_rules', ['organization_id'], unique=False,
    )
    op.create_index(
        op.f('ix_alarm_rules_chamber_id'), 'alarm_rules', ['chamber_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_alarm_rules_chamber_id'), table_name='alarm_rules')
    op.drop_index(op.f('ix_alarm_rules_organization_id'), table_name='alarm_rules')
    op.drop_table('alarm_rules')
