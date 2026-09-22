from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from licensing.database import Base
from licensing.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Chamber(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named chamber connection (host/port) shared within an organization."""

    __tablename__ = "chambers"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Chamber {self.id} org={self.organization_id} {self.name!r}>"
