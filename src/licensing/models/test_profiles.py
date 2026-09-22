from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from licensing.database import Base
from licensing.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TestProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named multi-step test schedule shared within an organization."""

    __tablename__ = "test_profiles"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    steps: Mapped[list[TestProfileStep]] = relationship(
        back_populates="test_profile",
        cascade="all, delete-orphan",
        order_by="TestProfileStep.step_order",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TestProfile {self.id} org={self.organization_id} {self.name!r}>"


class TestProfileStep(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "test_profile_steps"

    test_profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("test_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    setpoint_temp: Mapped[float | None] = mapped_column(Float, nullable=True)
    setpoint_pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_s: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    test_profile: Mapped[TestProfile] = relationship(back_populates="steps")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TestProfileStep {self.id} profile={self.test_profile_id} order={self.step_order}>"
