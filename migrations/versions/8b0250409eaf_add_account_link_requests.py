"""add account_link_requests

Revision ID: 8b0250409eaf
Revises: fa66924fa288
Create Date: 2026-08-04 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8b0250409eaf'
down_revision: Union[str, None] = 'fa66924fa288'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'account_link_requests',
        sa.Column('user_code_hash', sa.String(length=128), nullable=False),
        sa.Column(
            'status',
            postgresql.ENUM(
                'pending', 'approved', 'denied', 'expired', 'consumed',
                name='activation_request_status',
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column('requested_organization_id', sa.UUID(), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approved_by_user_id', sa.UUID(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['requested_organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_account_link_requests_expires_at'),
        'account_link_requests', ['expires_at'], unique=False,
    )
    op.create_index(
        op.f('ix_account_link_requests_requested_organization_id'),
        'account_link_requests', ['requested_organization_id'], unique=False,
    )
    op.create_index(
        op.f('ix_account_link_requests_user_code_hash'),
        'account_link_requests', ['user_code_hash'], unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_account_link_requests_user_code_hash'), table_name='account_link_requests'
    )
    op.drop_index(
        op.f('ix_account_link_requests_requested_organization_id'),
        table_name='account_link_requests',
    )
    op.drop_index(
        op.f('ix_account_link_requests_expires_at'), table_name='account_link_requests'
    )
    op.drop_table('account_link_requests')
