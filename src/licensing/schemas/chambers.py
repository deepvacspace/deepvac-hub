"""Pydantic schemas for the desktop-facing chamber sync endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChamberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    host: str
    port: int


class ChamberOut(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    name: str
    host: str
    port: int
    created_at: datetime
    updated_at: datetime


class ChamberListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chambers: list[ChamberOut]
