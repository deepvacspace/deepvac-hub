"""Pydantic schemas for the desktop-facing account-link endpoints, and the
signed identity payload also returned alongside activation."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from licensing.schemas.license import SignedLicenseEnvelope


class AccountLinkStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: uuid.UUID


class AccountLinkStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_id: uuid.UUID
    user_code: str
    verification_url: str
    expires_at: datetime
    polling_interval_seconds: int


class AccountLinkStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    expires_at: datetime


class AccountInfo(BaseModel):
    """Unsigned identity payload for a linked user/organization."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    user_id: uuid.UUID
    email: str
    display_name: str
    organization_id: uuid.UUID
    organization_name: str


class SignedAccountInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    envelope_version: int = 1
    payload: AccountInfo
    signature: str = Field(description="base64url-encoded Ed25519 signature")
    key_id: str


class ActivationCompleteResponse(BaseModel):
    """Response of POST /activations/{id}/complete: the signed license
    certificate plus a signed AccountInfo for the approving user/org."""

    model_config = ConfigDict(extra="forbid")

    license: SignedLicenseEnvelope
    account: SignedAccountInfo
