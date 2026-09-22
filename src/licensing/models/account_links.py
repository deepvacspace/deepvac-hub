from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from licensing.database import Base
from licensing.models.enums import ActivationRequestStatus
from licensing.models.mixins import UUIDPrimaryKeyMixin, pg_enum


class AccountLinkRequest(UUIDPrimaryKeyMixin, Base):
    """A single device-code request to attach a desktop installation's local
    profile to a hub user/organization identity."""

    __tablename__ = "account_link_requests"

    user_code_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    status: Mapped[ActivationRequestStatus] = mapped_column(
        pg_enum(ActivationRequestStatus, name="activation_request_status"),
        nullable=False,
        default=ActivationRequestStatus.PENDING,
    )
    requested_organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    """The organization that already owns this device's license."""
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AccountLinkRequest {self.id} status={self.status}>"
