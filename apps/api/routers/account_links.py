"""Account-link endpoints for attaching a desktop installation to a hub
user/organization identity."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.dependencies import SigningContext, get_db, get_signing_context
from licensing.config import get_settings
from licensing.exceptions import NotFoundError
from licensing.schemas.account_link import (
    AccountLinkStartRequest,
    AccountLinkStartResponse,
    AccountLinkStatusResponse,
    SignedAccountInfo,
)
from licensing.services import account_links as account_links_service

router = APIRouter(tags=["account-links"])

_POLLING_INTERVAL_SECONDS = 5


@router.post("/account-links", response_model=AccountLinkStartResponse, status_code=201)
def start_link(
    payload: AccountLinkStartRequest, db: Session = Depends(get_db)
) -> AccountLinkStartResponse:
    settings = get_settings()
    request, raw_code = account_links_service.start_link(
        db,
        organization_id=payload.organization_id,
        ttl_seconds=settings.activation_ttl_seconds,
    )
    verification_url = f"{settings.management_base_url}/link-account?user_code={raw_code}"
    return AccountLinkStartResponse(
        link_id=request.id,
        user_code=raw_code,
        verification_url=verification_url,
        expires_at=request.expires_at,
        polling_interval_seconds=_POLLING_INTERVAL_SECONDS,
    )


@router.get("/account-links/{link_id}", response_model=AccountLinkStatusResponse)
def get_link_status(link_id: uuid.UUID, db: Session = Depends(get_db)) -> AccountLinkStatusResponse:
    request = account_links_service.get_link(db, link_id)
    if request is None:
        raise NotFoundError("Account link request not found.")
    return AccountLinkStatusResponse(
        status=account_links_service.effective_status(request).value,
        expires_at=request.expires_at,
    )


@router.post("/account-links/{link_id}/complete", response_model=SignedAccountInfo)
def complete_link(
    link_id: uuid.UUID,
    db: Session = Depends(get_db),
    signing_ctx: SigningContext = Depends(get_signing_context),
) -> SignedAccountInfo:
    envelope = account_links_service.complete_link(
        db,
        link_id=link_id,
        signing_key_id=signing_ctx.key_id,
        private_key=signing_ctx.private_key,
    )
    return SignedAccountInfo(**envelope.to_dict())
