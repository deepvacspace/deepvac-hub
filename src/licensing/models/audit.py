from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from licensing.database import Base
from licensing.models.mixins import UUIDPrimaryKeyMixin
from licensing.models.organizations import Organization
from licensing.models.users import User


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    """Administrative/security audit trail.

    `metadata_` is JSONB but is never a free-for-all: writers must go through
    licensing.audit.record_event(), which validates keys against
    licensing.audit.allowlist.ALLOWED_METADATA_KEYS before persisting,
    so experiment-shaped data structurally cannot end up here. See
    docs/privacy.md.
    """

    __tablename__ = "audit_events"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    source_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_metadata: Mapped[dict[str, object] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    actor: Mapped[User | None] = relationship()
    organization: Mapped[Organization | None] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditEvent {self.id} {self.event_type}>"
