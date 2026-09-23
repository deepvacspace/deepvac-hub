from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from tests.factories import (
    make_membership,
    make_organization,
    make_user,
    make_vendor_super_admin,
)

from licensing.audit import record_event
from licensing.exceptions import PermissionDeniedError
from licensing.models.enums import MembershipRole
from licensing.services import audit as audit_service


def test_list_events_requires_vendor(db_session) -> None:  # type: ignore[no-untyped-def]
    non_vendor = make_user(db_session)
    with pytest.raises(PermissionDeniedError):
        audit_service.list_events(db_session, actor=non_vendor)


def test_list_events_filters_by_event_type(db_session) -> None:  # type: ignore[no-untyped-def]
    admin = make_vendor_super_admin(db_session)
    org = make_organization(db_session)
    wanted_type = f"test_event_{uuid.uuid4()}"
    record_event(db_session, event_type=wanted_type, organization_id=org.id)
    record_event(db_session, event_type=f"test_event_{uuid.uuid4()}", organization_id=org.id)
    db_session.flush()

    page = audit_service.list_events(db_session, actor=admin, event_type=wanted_type)

    assert [e.event_type for e in page.items] == [wanted_type]


def test_list_events_orders_newest_first(db_session) -> None:  # type: ignore[no-untyped-def]
    admin = make_vendor_super_admin(db_session)
    event_type = f"test_event_{uuid.uuid4()}"
    first = record_event(db_session, event_type=event_type)
    db_session.flush()
    first.created_at = datetime.now(UTC) - timedelta(minutes=5)
    second = record_event(db_session, event_type=event_type)
    db_session.flush()

    page = audit_service.list_events(db_session, actor=admin, event_type=event_type)

    assert [e.id for e in page.items] == [second.id, first.id]


def test_list_event_types_requires_vendor(db_session) -> None:  # type: ignore[no-untyped-def]
    non_vendor = make_user(db_session)
    with pytest.raises(PermissionDeniedError):
        audit_service.list_event_types(db_session, actor=non_vendor)


def test_list_chamber_events_rejects_non_admin(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)
    member = make_user(db_session)
    make_membership(
        db_session, organization=org, user=member, role=MembershipRole.ORGANIZATION_MEMBER
    )
    with pytest.raises(PermissionDeniedError):
        audit_service.list_chamber_events_for_organization(
            db_session, actor=member, organization_id=org.id
        )


def test_list_chamber_events_allows_org_admin(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)
    admin = make_user(db_session)
    make_membership(
        db_session, organization=org, user=admin, role=MembershipRole.ORGANIZATION_ADMIN
    )
    record_event(
        db_session,
        event_type="chamber_created",
        organization_id=org.id,
        target_type="chamber",
        target_id="c1",
    )
    db_session.flush()

    page = audit_service.list_chamber_events_for_organization(
        db_session, actor=admin, organization_id=org.id
    )

    assert [e.event_type for e in page.items] == ["chamber_created"]


def test_list_chamber_events_excludes_other_target_types(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)
    admin = make_user(db_session)
    make_membership(
        db_session, organization=org, user=admin, role=MembershipRole.ORGANIZATION_ADMIN
    )
    record_event(
        db_session,
        event_type="chamber_created",
        organization_id=org.id,
        target_type="chamber",
        target_id="c1",
    )
    record_event(
        db_session,
        event_type="test_profile_created",
        organization_id=org.id,
        target_type="test_profile",
        target_id="t1",
    )
    db_session.flush()

    page = audit_service.list_chamber_events_for_organization(
        db_session, actor=admin, organization_id=org.id
    )

    assert [e.event_type for e in page.items] == ["chamber_created"]


def test_list_chamber_events_excludes_other_organizations(db_session) -> None:  # type: ignore[no-untyped-def]
    org_a = make_organization(db_session)
    org_b = make_organization(db_session)
    admin = make_user(db_session)
    make_membership(
        db_session, organization=org_a, user=admin, role=MembershipRole.ORGANIZATION_ADMIN
    )
    record_event(
        db_session,
        event_type="chamber_created",
        organization_id=org_b.id,
        target_type="chamber",
        target_id="c1",
    )
    db_session.flush()

    page = audit_service.list_chamber_events_for_organization(
        db_session, actor=admin, organization_id=org_a.id
    )

    assert page.items == []
