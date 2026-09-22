"""Pydantic schemas for the desktop-facing test-profile sync endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TestProfileStepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_order: int
    setpoint_temp: float | None = None
    setpoint_pressure: float | None = None
    duration_s: float
    label: str = ""


class TestProfileStepOut(TestProfileStepIn):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID


class TestProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    steps: list[TestProfileStepIn]


class TestProfileOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    steps: list[TestProfileStepOut]
    created_at: datetime
    updated_at: datetime


class TestProfileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles: list[TestProfileOut]
