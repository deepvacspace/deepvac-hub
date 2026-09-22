"""Alarm-rule sync endpoints, scoped to the calling device's organization."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.dependencies import DeviceContext, get_db, get_device_context
from licensing.schemas.alarm_rules import AlarmRuleIn, AlarmRuleListResponse, AlarmRuleOut
from licensing.services import alarm_rules as alarm_rules_service

router = APIRouter(tags=["alarm-rules"])


@router.get("/alarm-rules", response_model=AlarmRuleListResponse)
def list_alarm_rules(
    db: Session = Depends(get_db),
    device: DeviceContext = Depends(get_device_context),
) -> AlarmRuleListResponse:
    rules = alarm_rules_service.list_for_organization(db, device.organization_id)
    return AlarmRuleListResponse(alarm_rules=[AlarmRuleOut.model_validate(r) for r in rules])


@router.post("/alarm-rules", response_model=AlarmRuleOut, status_code=201)
def create_alarm_rule(
    payload: AlarmRuleIn,
    db: Session = Depends(get_db),
    device: DeviceContext = Depends(get_device_context),
) -> AlarmRuleOut:
    rule = alarm_rules_service.create(
        db,
        organization_id=device.organization_id,
        chamber_id=payload.chamber_id,
        name=payload.name,
        variable=payload.variable,
        condition=payload.condition,
        value=payload.value,
        value2=payload.value2,
        severity=payload.severity,
        deadband=payload.deadband,
        delay_s=payload.delay_s,
        enabled=payload.enabled,
        created_by_user_id=None,
    )
    return AlarmRuleOut.model_validate(rule)


@router.post("/alarm-rules/{rule_id}/replace", response_model=AlarmRuleOut)
def replace_alarm_rule(
    rule_id: uuid.UUID,
    payload: AlarmRuleIn,
    db: Session = Depends(get_db),
    device: DeviceContext = Depends(get_device_context),
) -> AlarmRuleOut:
    rule = alarm_rules_service.replace_content(
        db,
        rule_id=rule_id,
        organization_id=device.organization_id,
        name=payload.name,
        variable=payload.variable,
        condition=payload.condition,
        value=payload.value,
        value2=payload.value2,
        severity=payload.severity,
        deadband=payload.deadband,
        delay_s=payload.delay_s,
        enabled=payload.enabled,
    )
    return AlarmRuleOut.model_validate(rule)
