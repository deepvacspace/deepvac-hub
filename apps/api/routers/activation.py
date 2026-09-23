"""Device-code activation endpoints: POST /activations, GET /activations/{id},
POST /activations/{id}/complete. See docs/sequences.md.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from apps.api.audit import log_event
from apps.api.dependencies import SigningContext, get_db, get_signing_context
from licensing.config import get_settings
from licensing.exceptions import NotFoundError
from licensing.schemas.account_link import ActivationCompleteResponse, SignedAccountInfo
from licensing.schemas.activation import (
    ActivationCompleteRequest,
    ActivationStartRequest,
    ActivationStartResponse,
    ActivationStatusResponse,
)
from licensing.schemas.license import SignedLicenseEnvelope
from licensing.services import activation as activation_service

router = APIRouter(tags=["activation"])

_POLLING_INTERVAL_SECONDS = 5


@router.post("/activations", response_model=ActivationStartResponse, status_code=201)
def start_activation(
    payload: ActivationStartRequest, db: Session = Depends(get_db)
) -> ActivationStartResponse:
    settings = get_settings()
    request, raw_code = activation_service.start_activation(
        db,
        product_code=payload.product_code,
        edition_code=payload.edition_code,
        ttl_seconds=settings.activation_ttl_seconds,
    )
    verification_url = f"{settings.management_base_url}/activate?user_code={raw_code}"
    return ActivationStartResponse(
        activation_id=request.id,
        user_code=raw_code,
        verification_url=verification_url,
        expires_at=request.expires_at,
        polling_interval_seconds=_POLLING_INTERVAL_SECONDS,
    )


@router.get("/activations/{activation_id}", response_model=ActivationStatusResponse)
def get_activation_status(
    activation_id: uuid.UUID, db: Session = Depends(get_db)
) -> ActivationStatusResponse:
    request = activation_service.get_activation(db, activation_id)
    if request is None:
        raise NotFoundError("Activation request not found.")
    return ActivationStatusResponse(
        status=activation_service.effective_status(request).value,
        expires_at=request.expires_at,
    )


@router.post("/activations/{activation_id}/complete", response_model=ActivationCompleteResponse)
def complete_activation(
    activation_id: uuid.UUID,
    payload: ActivationCompleteRequest,
    request: Request,
    db: Session = Depends(get_db),
    signing_ctx: SigningContext = Depends(get_signing_context),
) -> ActivationCompleteResponse:
    settings = get_settings()
    device_public_key = activation_service.device_public_key_from_b64(payload.device_public_key)
    license_envelope, account_envelope = activation_service.complete_activation(
        db,
        activation_id=activation_id,
        device_public_key=device_public_key,
        display_name=payload.display_name,
        signing_key_id=signing_ctx.key_id,
        private_key=signing_ctx.private_key,
        default_validity_days=settings.default_license_validity_days,
    )
    log_event(
        request,
        db,
        event_type="activation_completed",
        actor_user_id=uuid.UUID(account_envelope.payload["user_id"]),
        organization_id=uuid.UUID(account_envelope.payload["organization_id"]),
        target_type="activation_request",
        target_id=str(activation_id),
    )
    return ActivationCompleteResponse(
        license=SignedLicenseEnvelope(**license_envelope.to_dict()),
        account=SignedAccountInfo(**account_envelope.to_dict()),
    )
