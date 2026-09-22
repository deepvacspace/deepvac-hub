"""Organization-scoped alarm-rule storage for desktop sync."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from licensing.exceptions import NotFoundError
from licensing.models.alarm_rules import AlarmRule
from licensing.models.chambers import Chamber


def list_for_organization(session: Session, organization_id: uuid.UUID) -> list[AlarmRule]:
    rows = session.execute(
        select(AlarmRule)
        .where(AlarmRule.organization_id == organization_id)
        .options(selectinload(AlarmRule.chamber))
        .order_by(AlarmRule.name)
    ).scalars()
    return list(rows)


def _require_chamber(session: Session, chamber_id: uuid.UUID, organization_id: uuid.UUID) -> None:
    chamber = session.execute(
        select(Chamber).where(Chamber.id == chamber_id, Chamber.organization_id == organization_id)
    ).scalar_one_or_none()
    if chamber is None:
        raise NotFoundError("Chamber not found in this organization.")


def create(
    session: Session,
    *,
    organization_id: uuid.UUID,
    chamber_id: uuid.UUID,
    name: str,
    variable: str,
    condition: str,
    value: float,
    value2: float | None,
    severity: str,
    deadband: float,
    delay_s: float,
    enabled: bool,
    created_by_user_id: uuid.UUID | None,
) -> AlarmRule:
    _require_chamber(session, chamber_id, organization_id)
    rule = AlarmRule(
        organization_id=organization_id,
        chamber_id=chamber_id,
        name=name,
        variable=variable,
        condition=condition,
        value=value,
        value2=value2,
        severity=severity,
        deadband=deadband,
        delay_s=delay_s,
        enabled=enabled,
        created_by_user_id=created_by_user_id,
    )
    session.add(rule)
    session.flush()
    return rule


def replace_content(
    session: Session,
    *,
    rule_id: uuid.UUID,
    organization_id: uuid.UUID,
    name: str,
    variable: str,
    condition: str,
    value: float,
    value2: float | None,
    severity: str,
    deadband: float,
    delay_s: float,
    enabled: bool,
) -> AlarmRule:
    rule = session.execute(
        select(AlarmRule).where(
            AlarmRule.id == rule_id, AlarmRule.organization_id == organization_id
        )
    ).scalar_one_or_none()
    if rule is None:
        raise NotFoundError("Alarm rule not found.")
    rule.name = name
    rule.variable = variable
    rule.condition = condition
    rule.value = value
    rule.value2 = value2
    rule.severity = severity
    rule.deadband = deadband
    rule.delay_s = delay_s
    rule.enabled = enabled
    session.flush()
    return rule
