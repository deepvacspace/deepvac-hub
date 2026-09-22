"""Device-code activation: start, approve (from the web portal), status, and
completion (device-key registration + license issuance).

See docs/sequences.md for the full flow this module implements.
"""

from __future__ import annotations

import base64
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
    EntitlementError,
    NotFoundError,
    PermissionDeniedError,
)
from licensing.models.activation import ActivationRequest
from licensing.models.enums import (
    ActivationRequestStatus,
    MembershipStatus,
    OrganizationLicenseStatus,
    UserStatus,
)
from licensing.models.licenses import OrganizationLicense
from licensing.models.organizations import Organization, OrganizationMembership
from licensing.models.products import Edition, Product
from licensing.models.users import User
from licensing.security.signing import SignedEnvelope
from licensing.security.tokens import generate_user_code, hash_lookup_token
from licensing.services import account_links as account_links_service
from licensing.services import devices as devices_service
from licensing.services import issuance as issuance_service


def start_activation(
    session: Session,
    *,
    product_code: str,
    edition_code: str | None,
    ttl_seconds: int,
) -> tuple[ActivationRequest, str]:
    now = datetime.now(UTC)
    raw_code = generate_user_code()
    request = ActivationRequest(
        user_code_hash=hash_lookup_token(raw_code),
        status=ActivationRequestStatus.PENDING,
        requested_product_code=product_code,
        requested_edition_code=edition_code,
        requested_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    session.add(request)
    session.flush()
    return request, raw_code


def effective_status(request: ActivationRequest) -> ActivationRequestStatus:
    """Status as of now, without mutating the row -- a request left PENDING
    or APPROVED past its expiry reads as EXPIRED without needing a
    background sweeper."""
    if (
        request.status in (ActivationRequestStatus.PENDING, ActivationRequestStatus.APPROVED)
        and datetime.now(UTC) >= request.expires_at
    ):
        return ActivationRequestStatus.EXPIRED
    return request.status


def get_activation(session: Session, activation_id: uuid.UUID) -> ActivationRequest | None:
    return session.get(ActivationRequest, activation_id)


def find_by_user_code(session: Session, raw_user_code: str) -> ActivationRequest | None:
    code_hash = hash_lookup_token(raw_user_code)
    return session.execute(
        select(ActivationRequest).where(ActivationRequest.user_code_hash == code_hash)
    ).scalar_one_or_none()


def list_eligible_organizations(
    session: Session, *, user: User, product_code: str
) -> list[Organization]:
    """Organizations the user actively belongs to that also have an active
    license for the requested product -- used to populate the approval
    page's organization picker."""
    rows = session.execute(
        select(Organization)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .join(OrganizationLicense, OrganizationLicense.organization_id == Organization.id)
        .join(Product, Product.id == OrganizationLicense.product_id)
        .where(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
            OrganizationLicense.status == OrganizationLicenseStatus.ACTIVE,
            Product.code == product_code,
        )
        .distinct()
    ).scalars()
    return list(rows)


def approve_activation(
    session: Session,
    *,
    activation_id: uuid.UUID,
    approving_user: User,
    organization_id: uuid.UUID,
) -> ActivationRequest:
    request = session.get(ActivationRequest, activation_id)
    if request is None:
        raise NotFoundError("Activation request not found.")
    if effective_status(request) != ActivationRequestStatus.PENDING:
        raise ActivationAlreadyConsumedError(
            f"Activation request is {effective_status(request).value}, not pending."
        )

    membership = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == approving_user.id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise PermissionDeniedError("You are not an active member of that organization.")

    request.status = ActivationRequestStatus.APPROVED
    request.approved_by_user_id = approving_user.id
    request.approved_organization_id = organization_id
    request.approved_at = datetime.now(UTC)
    session.flush()
    return request


def complete_activation(
    session: Session,
    *,
    activation_id: uuid.UUID,
    device_public_key: bytes,
    display_name: str | None,
    signing_key_id: str,
    private_key: Ed25519PrivateKey,
    default_validity_days: int,
) -> tuple[SignedEnvelope, SignedEnvelope]:
    """Completes activation, returning the signed license envelope and a
    signed AccountInfo envelope for the approving user/organization."""
    request = session.execute(
        select(ActivationRequest).where(ActivationRequest.id == activation_id).with_for_update()
    ).scalar_one_or_none()
    if request is None:
        raise NotFoundError("Activation request not found.")

    status = effective_status(request)
    if status == ActivationRequestStatus.CONSUMED:
        raise ActivationAlreadyConsumedError("Activation request already consumed.")
    if status == ActivationRequestStatus.EXPIRED:
        raise ActivationExpiredError("Activation request has expired.")
    if status != ActivationRequestStatus.APPROVED:
        raise ActivationNotApprovedError(f"Activation request is {status.value}, not approved.")

    assert request.approved_by_user_id is not None
    assert request.approved_organization_id is not None

    user = session.get(User, request.approved_by_user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise AccountDisabledError("The approving user is not active.")

    membership = session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == request.approved_organization_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise PermissionDeniedError("Membership is no longer active.")

    org_license_query = select(OrganizationLicense).join(
        Product, Product.id == OrganizationLicense.product_id
    ).where(
        OrganizationLicense.organization_id == request.approved_organization_id,
        OrganizationLicense.status == OrganizationLicenseStatus.ACTIVE,
        Product.code == request.requested_product_code,
    )
    if request.requested_edition_code:
        org_license_query = org_license_query.join(
            Edition, Edition.id == OrganizationLicense.edition_id
        ).where(Edition.code == request.requested_edition_code)
    org_license = session.execute(org_license_query).scalars().first()
    if org_license is None:
        raise EntitlementError(
            "No active license for the requested product/edition in this organization."
        )
    now = datetime.now(UTC)
    if not (org_license.starts_at <= now <= org_license.expires_at):
        raise EntitlementError("Organization license is not currently within its validity period.")

    edition = session.get(Edition, org_license.edition_id)
    assert edition is not None

    device = devices_service.register_device(
        session,
        organization_license=org_license,
        user_id=user.id,
        device_public_key=device_public_key,
        display_name=display_name,
    )

    license_envelope = issuance_service.issue_certificate(
        session,
        device_activation=device,
        user_id=user.id,
        organization_id=request.approved_organization_id,
        product_code=request.requested_product_code,
        edition=edition,
        signing_key_id=signing_key_id,
        private_key=private_key,
        validity_days=org_license.offline_validity_days or default_validity_days,
    )
    account_envelope = account_links_service.build_and_sign_account_info(
        session,
        user=user,
        organization_id=request.approved_organization_id,
        signing_key_id=signing_key_id,
        private_key=private_key,
    )

    request.status = ActivationRequestStatus.CONSUMED
    request.consumed_at = now
    session.flush()
    return license_envelope, account_envelope


def device_public_key_from_b64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value)
