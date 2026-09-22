from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.factories import make_membership, make_organization, make_user

from licensing.exceptions import PermissionDeniedError
from licensing.models.certificates import SigningKey
from licensing.models.enums import MembershipRole
from licensing.security.signing import generate_keypair, public_key_to_raw_bytes
from licensing.services import account_links as account_links_service


def _make_signing_key(session, key_id: str = "test-signing-key"):  # type: ignore[no-untyped-def]
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


def test_complete_link_succeeds_for_active_member(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)
    member = make_user(db_session)
    make_membership(
        db_session, organization=org, user=member, role=MembershipRole.ORGANIZATION_MEMBER
    )

    request, _raw_code = account_links_service.start_link(
        db_session, organization_id=org.id, ttl_seconds=600
    )
    account_links_service.approve_link(db_session, link_id=request.id, approving_user=member)

    signing_key_id, signing_private_key = _make_signing_key(db_session)
    envelope = account_links_service.complete_link(
        db_session,
        link_id=request.id,
        signing_key_id=signing_key_id,
        private_key=signing_private_key,
    )

    assert envelope.payload["user_id"] == str(member.id)
    assert envelope.payload["email"] == member.email
    assert envelope.payload["organization_id"] == str(org.id)
    assert envelope.payload["organization_name"] == org.name


def test_approve_link_rejects_non_member(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)
    outsider = make_user(db_session)

    request, _raw_code = account_links_service.start_link(
        db_session, organization_id=org.id, ttl_seconds=600
    )
    with pytest.raises(PermissionDeniedError):
        account_links_service.approve_link(db_session, link_id=request.id, approving_user=outsider)


def test_approve_link_rejects_member_of_a_different_org(db_session) -> None:  # type: ignore[no-untyped-def]
    """The link is scoped to the org the device is already licensed under --
    being an active member of *some* org isn't enough."""
    device_org = make_organization(db_session)
    other_org = make_organization(db_session)
    member_elsewhere = make_user(db_session)
    make_membership(
        db_session,
        organization=other_org,
        user=member_elsewhere,
        role=MembershipRole.ORGANIZATION_MEMBER,
    )

    request, _raw_code = account_links_service.start_link(
        db_session, organization_id=device_org.id, ttl_seconds=600
    )
    with pytest.raises(PermissionDeniedError):
        account_links_service.approve_link(
            db_session, link_id=request.id, approving_user=member_elsewhere
        )
