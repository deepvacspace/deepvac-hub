from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.factories import (
    make_license,
    make_membership,
    make_organization,
    make_product_and_edition,
    make_user,
)

from licensing.exceptions import EntitlementError, PermissionDeniedError
from licensing.models.certificates import SigningKey
from licensing.models.enums import MembershipRole
from licensing.security.signing import generate_keypair, public_key_to_raw_bytes
from licensing.services import activation as activation_service


def _make_signing_key(session, key_id: str = "test-signing-key"):  # type: ignore[no-untyped-def]
    """Registers a SigningKey row (issued_license_certificates has a real
    FK to signing_keys.key_id) and returns the matching private key to
    sign with."""
    private_key, public_key = generate_keypair()
    now = datetime.now(UTC)
    session.add(
        SigningKey(
            key_id=key_id,
            public_key=public_key_to_raw_bytes(public_key),
            activated_at=now,
            created_at=now,
        )
    )
    session.flush()
    return key_id, private_key


def test_complete_activation_succeeds_for_any_active_member_no_seat_needed(  # type: ignore[no-untyped-def]
    db_session,
) -> None:
    """The core behavior this test locks in: an organization license
    entitles every active member to the product -- there is no per-user
    seat limit or seat-assignment step. A plain ORGANIZATION_MEMBER (not
    admin) activates directly."""
    org = make_organization(db_session)
    product, edition = make_product_and_edition(db_session)
    make_license(db_session, organization=org, product=product, edition=edition)
    member = make_user(db_session)
    make_membership(
        db_session, organization=org, user=member, role=MembershipRole.ORGANIZATION_MEMBER
    )

    request, raw_code = activation_service.start_activation(
        db_session, product_code=product.code, edition_code=edition.code, ttl_seconds=600
    )
    activation_service.approve_activation(
        db_session, activation_id=request.id, approving_user=member, organization_id=org.id
    )

    signing_key_id, signing_private_key = _make_signing_key(db_session)
    _, device_public_key = generate_keypair()

    license_envelope, account_envelope = activation_service.complete_activation(
        db_session,
        activation_id=request.id,
        device_public_key=public_key_to_raw_bytes(device_public_key),
        display_name="Test Device",
        signing_key_id=signing_key_id,
        private_key=signing_private_key,
        default_validity_days=365,
    )

    assert license_envelope.payload["organization_id"] == str(org.id)
    assert account_envelope.payload["organization_id"] == str(org.id)
    assert account_envelope.payload["user_id"] == str(member.id)
    assert account_envelope.payload["email"] == member.email
    assert account_envelope.payload["organization_name"] == org.name


def test_approve_activation_rejects_non_member(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)
    product, _edition = make_product_and_edition(db_session)
    outsider = make_user(db_session)

    request, _raw_code = activation_service.start_activation(
        db_session, product_code=product.code, edition_code=None, ttl_seconds=600
    )
    with pytest.raises(PermissionDeniedError):
        activation_service.approve_activation(
            db_session, activation_id=request.id, approving_user=outsider, organization_id=org.id
        )


def test_complete_activation_rejects_no_active_license(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)
    product, edition = make_product_and_edition(db_session)
    member = make_user(db_session)
    make_membership(
        db_session, organization=org, user=member, role=MembershipRole.ORGANIZATION_MEMBER
    )
    # No license created for this org/product.

    request, _raw_code = activation_service.start_activation(
        db_session, product_code=product.code, edition_code=edition.code, ttl_seconds=600
    )
    activation_service.approve_activation(
        db_session, activation_id=request.id, approving_user=member, organization_id=org.id
    )

    signing_private_key, _ = generate_keypair()
    _, device_public_key = generate_keypair()

    with pytest.raises(EntitlementError):
        activation_service.complete_activation(
            db_session,
            activation_id=request.id,
            device_public_key=public_key_to_raw_bytes(device_public_key),
            display_name="Test Device",
            signing_key_id="test-signing-key",
            private_key=signing_private_key,
            default_validity_days=365,
        )
