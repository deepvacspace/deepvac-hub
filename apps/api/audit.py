"""Thin FastAPI-aware wrapper around licensing.audit.record_event, mirroring
apps/web/audit.py for the desktop-facing API.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from licensing.audit import record_event


def log_event(
    request: Request,
    session: Session,
    *,
    event_type: str,
    actor_user_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    record_event(
        session,
        event_type=event_type,
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        target_type=target_type,
        target_id=target_id,
        request_id=getattr(request.state, "request_id", None),
        source_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        metadata=metadata,
    )
