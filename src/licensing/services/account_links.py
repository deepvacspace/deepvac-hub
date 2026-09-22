"""Account linking: attaches a desktop installation's local profile to a
hub user/organization via a device-code approval flow."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from licensing.exceptions import (
    AccountDisabledError,
    ActivationAlreadyConsumedError,
    ActivationExpiredError,
    ActivationNotApprovedError,
    NotFoundError,
    PermissionDeniedError,
)
from licensing.licensing.canonical import ACCOUNT_INFO_REQUIRED_KEYS
from licensing.models.account_links import AccountLinkRequest
from licensing.models.enums import ActivationRequestStatus, MembershipStatus, UserStatus
from licensing.models.organizations import Organization, OrganizationMembership
from licensing.models.users import User
from licensing.security.signing import SignedEnvelope, sign_payload
from licensing.security.tokens import generate_user_code, hash_lookup_token


def start_link(
    session: Session, *, organization_id: uuid.UUID, ttl_seconds: int
) -> tuple[AccountLinkRequest, str]:
    now = datetime.now(UTC)
    raw_code = generate_user_code()
    request = AccountLinkRequest(
        user_code_hash=hash_lookup_token(raw_code),
        status=ActivationRequestStatus.PENDING,
        requested_organization_id=organization_id,
        requested_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    session.add(request)
    session.flush()
    return request, raw_code


def effective_status(request: AccountLinkRequest) -> ActivationRequestStatus:
    """Status as of now, without mutating the row -- a request left PENDING
    or APPROVED past its expiry reads as EXPIRED without needing a
    background sweeper."""
    if (
        request.status in (ActivationRequestStatus.PENDING, ActivationRequestStatus.APPROVED)
        and datetime.now(UTC) >= request.expires_at
    ):
        return ActivationRequestStatus.EXPIRED
    return request.status


def get_link(session: Session, link_id: uuid.UUID) -> AccountLinkRequest | None:
    return session.get(AccountLinkRequest, link_id)


def find_by_user_code(session: Session, raw_user_code: str) -> AccountLinkRequest | None:
    code_hash = hash_lookup_token(raw_user_code)
    return session.execute(
        select(AccountLinkRequest).where(AccountLinkRequest.user_code_hash == code_hash)
    ).scalar_one_or_none()


def approve_link(
    session: Session, *, link_id: uuid.UUID, approving_user: User
) -> AccountLinkRequest:
    """Approves a pending link request. The approving user must be an active
    member of the organization the link was requested against."""
    request = session.get(AccountLinkRequest, link_id)
    if request is None:
        raise NotFoundError("Account link request not found.")
    if effective_status(request) != ActivationRequestStatus.PENDING:
        raise ActivationAlreadyConsumedError(
            f"Account link request is {effective_status(request).value}, not pending."
        )

    membership = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == request.requested_organization_id,
            OrganizationMembership.user_id == approving_user.id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise PermissionDeniedError(
            "You are not an active member of the organization this device is licensed under."
        )

    request.status = ActivationRequestStatus.APPROVED
    request.approved_by_user_id = approving_user.id
    request.approved_at = datetime.now(UTC)
    session.flush()
    return request


def build_and_sign_account_info(
    session: Session,
    *,
    user: User,
    organization_id: uuid.UUID,
    signing_key_id: str,
    private_key: Ed25519PrivateKey,
) -> SignedEnvelope:
    """Builds and signs the AccountInfo payload for (user, organization_id)."""
    organization = session.get(Organization, organization_id)
    assert organization is not None
    payload = {
        "schema_version": 1,
        "user_id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "organization_id": str(organization_id),
        "organization_name": organization.name,
    }
    return sign_payload(
        payload, private_key, key_id=signing_key_id, required_keys=ACCOUNT_INFO_REQUIRED_KEYS
    )


def complete_link(
    session: Session,
    *,
    link_id: uuid.UUID,
    signing_key_id: str,
    private_key: Ed25519PrivateKey,
) -> SignedEnvelope:
    request = session.execute(
        select(AccountLinkRequest).where(AccountLinkRequest.id == link_id).with_for_update()
    ).scalar_one_or_none()
    if request is None:
        raise NotFoundError("Account link request not found.")

    status = effective_status(request)
    if status == ActivationRequestStatus.CONSUMED:
        raise ActivationAlreadyConsumedError("Account link request already consumed.")
    if status == ActivationRequestStatus.EXPIRED:
        raise ActivationExpiredError("Account link request has expired.")
    if status != ActivationRequestStatus.APPROVED:
        raise ActivationNotApprovedError(
            f"Account link request is {status.value}, not approved."
        )

    assert request.approved_by_user_id is not None
    user = session.get(User, request.approved_by_user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise AccountDisabledError("The approving user is not active.")

    membership = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == request.requested_organization_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise PermissionDeniedError("Membership is no longer active.")

    envelope = build_and_sign_account_info(
        session,
        user=user,
        organization_id=request.requested_organization_id,
        signing_key_id=signing_key_id,
        private_key=private_key,
    )

    request.status = ActivationRequestStatus.CONSUMED
    request.consumed_at = datetime.now(UTC)
    session.flush()
    return envelope
