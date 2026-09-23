"""Read-side queries for the audit trail: the vendor-wide log, and the
per-organization view scoped to that organization's chamber/alarm-rule
activity."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from licensing.models.audit import AuditEvent
from licensing.models.users import User
from licensing.pagination import Page, paginate
from licensing.services import auth as auth_service


def list_events(
    session: Session,
    *,
    actor: User,
    event_type: str | None = None,
    organization_id: uuid.UUID | None = None,
    page: int = 1,
    per_page: int = 50,
) -> Page[AuditEvent]:
    auth_service.require_vendor(actor)
    stmt = (
        select(AuditEvent)
        .options(selectinload(AuditEvent.actor), selectinload(AuditEvent.organization))
        .order_by(AuditEvent.created_at.desc())
    )
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if organization_id is not None:
        stmt = stmt.where(AuditEvent.organization_id == organization_id)
    return paginate(session, stmt, page=page, per_page=per_page)


def list_event_types(session: Session, *, actor: User) -> list[str]:
    auth_service.require_vendor(actor)
    rows = session.execute(
        select(AuditEvent.event_type).distinct().order_by(AuditEvent.event_type)
    ).scalars()
    return list(rows)


CHAMBER_TARGET_TYPES = ("chamber", "alarm_rule")


def list_chamber_events_for_organization(
    session: Session,
    *,
    actor: User,
    organization_id: uuid.UUID,
    page: int = 1,
    per_page: int = 50,
) -> Page[AuditEvent]:
    """Chamber and alarm-rule activity for one organization, for that
    organization's own admins to review."""
    auth_service.require_org_admin(session, actor, organization_id)
    stmt = (
        select(AuditEvent)
        .options(selectinload(AuditEvent.actor))
        .where(
            AuditEvent.organization_id == organization_id,
            AuditEvent.target_type.in_(CHAMBER_TARGET_TYPES),
        )
        .order_by(AuditEvent.created_at.desc())
    )
    return paginate(session, stmt, page=page, per_page=per_page)
