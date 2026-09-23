"""add deleted user status

Revision ID: f4a2d8c6b1e9
Revises: e7a1c3d9f5b2
Create Date: 2026-09-22 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f4a2d8c6b1e9'
down_revision: Union[str, None] = 'e7a1c3d9f5b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_status ADD VALUE IF NOT EXISTS 'deleted'")


def downgrade() -> None:
    pass
