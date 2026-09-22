from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from licensing.database import Base
from licensing.models.chambers import Chamber
from licensing.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AlarmRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A threshold rule for one organization chamber, shared across its devices."""

    __tablename__ = "alarm_rules"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    chamber_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chambers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    variable: Mapped[str] = mapped_column(String(200), nullable=False)
    condition: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    value2: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    deadband: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    delay_s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    chamber: Mapped[Chamber] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AlarmRule {self.id} chamber={self.chamber_id} {self.name!r}>"
