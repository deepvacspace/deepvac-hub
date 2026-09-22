from __future__ import annotations

from tests.factories import make_organization

from licensing.services import chambers as chambers_service


def test_create_and_list_for_organization(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)

    created = chambers_service.create(
        db_session,
        organization_id=org.id,
        name="Chamber 1",
        host="127.0.0.1",
        port=5555,
        created_by_user_id=None,
    )

    chambers = chambers_service.list_for_organization(db_session, org.id)

    assert [c.id for c in chambers] == [created.id]
    assert chambers[0].host == "127.0.0.1"


def test_list_for_organization_excludes_other_organizations(db_session) -> None:  # type: ignore[no-untyped-def]
    org_a = make_organization(db_session)
    org_b = make_organization(db_session)
    chambers_service.create(
        db_session,
        organization_id=org_a.id,
        name="Org A Chamber",
        host="10.0.0.1",
        port=5555,
        created_by_user_id=None,
    )

    assert chambers_service.list_for_organization(db_session, org_b.id) == []


def test_replace_content_updates_fields(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)
    chamber = chambers_service.create(
        db_session,
        organization_id=org.id,
        name="Chamber 1",
        host="127.0.0.1",
        port=5555,
        created_by_user_id=None,
    )

    updated = chambers_service.replace_content(
        db_session,
        chamber_id=chamber.id,
        organization_id=org.id,
        name="Chamber 1",
        host="10.0.0.5",
        port=6000,
    )

    assert updated.host == "10.0.0.5"
    assert updated.port == 6000
