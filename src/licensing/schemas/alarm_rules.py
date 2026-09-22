"""Pydantic schemas for the desktop-facing alarm-rule sync endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlarmRuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chamber_id: uuid.UUID
    name: str
    variable: str
    condition: str
    value: float
    value2: float | None = None
    severity: str
    deadband: float = 0.0
    delay_s: float = 0.0
    enabled: bool = True


class AlarmRuleOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    chamber_id: uuid.UUID
    name: str
    variable: str
    condition: str
    value: float
    value2: float | None
    severity: str
    deadband: float
    delay_s: float
    enabled: bool
    created_at: datetime
    updated_at: datetime


class AlarmRuleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alarm_rules: list[AlarmRuleOut]
