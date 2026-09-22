"""Organization-scoped chamber registry for desktop sync."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from licensing.exceptions import NotFoundError
from licensing.models.chambers import Chamber


def list_for_organization(session: Session, organization_id: uuid.UUID) -> list[Chamber]:
    rows = session.execute(
        select(Chamber).where(Chamber.organization_id == organization_id).order_by(Chamber.name)
    ).scalars()
    return list(rows)


def create(
    session: Session,
    *,
    organization_id: uuid.UUID,
    name: str,
    host: str,
    port: int,
    created_by_user_id: uuid.UUID | None,
) -> Chamber:
    chamber = Chamber(
        organization_id=organization_id,
        name=name,
        host=host,
        port=port,
        created_by_user_id=created_by_user_id,
    )
    session.add(chamber)
    session.flush()
    return chamber


def replace_content(
    session: Session,
    *,
    chamber_id: uuid.UUID,
    organization_id: uuid.UUID,
    name: str,
    host: str,
    port: int,
) -> Chamber:
    chamber = session.execute(
        select(Chamber).where(Chamber.id == chamber_id, Chamber.organization_id == organization_id)
    ).scalar_one_or_none()
    if chamber is None:
        raise NotFoundError("Chamber not found.")
    chamber.name = name
    chamber.host = host
    chamber.port = port
    session.flush()
    return chamber
