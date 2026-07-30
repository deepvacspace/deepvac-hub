from __future__ import annotations

import pytest
from tests.factories import make_organization, make_user

from licensing.exceptions import ConflictError
from licensing.models.enums import MembershipRole, MembershipStatus
from licensing.models.organizations import OrganizationMembership
from licensing.services import registration as registration_service


def test_register_creates_org_user_and_admin_membership(db_session) -> None:  # type: ignore[no-untyped-def]
    org, user = registration_service.register_organization_and_owner(
        db_session,
        organization_name="Acme Labs",
        email="owner@example.com",
        display_name="Owner Person",
        password="correct-horse-battery",
    )

    assert org.slug == "acme-labs"
    assert user.normalized_email == "owner@example.com"

    membership = db_session.query(OrganizationMembership).filter_by(
        organization_id=org.id, user_id=user.id
    ).one()
    assert membership.role == MembershipRole.ORGANIZATION_ADMIN
    assert membership.status == MembershipStatus.ACTIVE


def test_register_rejects_duplicate_email(db_session) -> None:  # type: ignore[no-untyped-def]
    make_user(db_session, email="taken@example.com")
    with pytest.raises(ConflictError):
        registration_service.register_organization_and_owner(
            db_session,
            organization_name="Acme Labs",
            email="taken@example.com",
            display_name="Owner Person",
            password="correct-horse-battery",
        )


def test_register_rejects_short_password(db_session) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ConflictError):
        registration_service.register_organization_and_owner(
            db_session,
            organization_name="Acme Labs",
            email="owner2@example.com",
            display_name="Owner Person",
            password="short",
        )


def test_register_deduplicates_slug_collision(db_session) -> None:  # type: ignore[no-untyped-def]
    make_organization(db_session, name="acme-labs")

    org, _user = registration_service.register_organization_and_owner(
        db_session,
        organization_name="Acme Labs",
        email="owner3@example.com",
        display_name="Owner Person",
        password="correct-horse-battery",
    )

    assert org.slug == "acme-labs-2"
