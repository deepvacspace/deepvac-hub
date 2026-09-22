"""Organization-scoped test-profile storage for desktop sync."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from licensing.exceptions import NotFoundError
from licensing.models.test_profiles import TestProfile, TestProfileStep


def list_for_organization(session: Session, organization_id: uuid.UUID) -> list[TestProfile]:
    rows = session.execute(
        select(TestProfile)
        .where(TestProfile.organization_id == organization_id)
        .options(selectinload(TestProfile.steps))
        .order_by(TestProfile.name)
    ).scalars()
    return list(rows)


def _replace_steps(profile: TestProfile, steps: list[dict]) -> None:
    profile.steps = [
        TestProfileStep(
            step_order=step["step_order"],
            setpoint_temp=step.get("setpoint_temp"),
            setpoint_pressure=step.get("setpoint_pressure"),
            duration_s=step["duration_s"],
            label=step.get("label") or "",
        )
        for step in steps
    ]


def create(
    session: Session,
    *,
    organization_id: uuid.UUID,
    name: str,
    description: str,
    steps: list[dict],
    created_by_user_id: uuid.UUID | None,
) -> TestProfile:
    profile = TestProfile(
        organization_id=organization_id,
        name=name,
        description=description,
        created_by_user_id=created_by_user_id,
    )
    _replace_steps(profile, steps)
    session.add(profile)
    session.flush()
    return profile


def replace_content(
    session: Session,
    *,
    profile_id: uuid.UUID,
    organization_id: uuid.UUID,
    name: str,
    description: str,
    steps: list[dict],
) -> TestProfile:
    profile = session.execute(
        select(TestProfile).where(
            TestProfile.id == profile_id, TestProfile.organization_id == organization_id
        )
    ).scalar_one_or_none()
    if profile is None:
        raise NotFoundError("Test profile not found.")
    profile.name = name
    profile.description = description
    _replace_steps(profile, steps)
    session.flush()
    return profile
