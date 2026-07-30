from __future__ import annotations

from tests.factories import make_user

from licensing.models.organizations import Organization, OrganizationMembership
from licensing.models.users import User


def test_register_creates_org_and_logs_in(flask_client, db_session) -> None:  # type: ignore[no-untyped-def]
    response = flask_client.post(
        "/register",
        data={
            "organization_name": "Acme Labs",
            "display_name": "Owner Person",
            "email": "newowner@example.com",
            "password": "correct-horse-battery",
            "confirm_password": "correct-horse-battery",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    user = db_session.query(User).filter_by(normalized_email="newowner@example.com").one()
    org = db_session.query(Organization).filter_by(slug="acme-labs").one()
    membership = (
        db_session.query(OrganizationMembership)
        .filter_by(organization_id=org.id, user_id=user.id)
        .one()
    )
    assert membership.role.value == "organization_admin"

    with flask_client.session_transaction() as session:
        assert session.get("user_id") == str(user.id)


def test_register_rejects_duplicate_email(flask_client, db_session) -> None:  # type: ignore[no-untyped-def]
    make_user(db_session, email="dupe@example.com")

    response = flask_client.post(
        "/register",
        data={
            "organization_name": "Another Org",
            "display_name": "Someone",
            "email": "dupe@example.com",
            "password": "correct-horse-battery",
            "confirm_password": "correct-horse-battery",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"already exists" in response.data


def test_register_rejects_password_mismatch(flask_client, db_session) -> None:  # type: ignore[no-untyped-def]
    response = flask_client.post(
        "/register",
        data={
            "organization_name": "Acme Labs",
            "display_name": "Owner Person",
            "email": "mismatch@example.com",
            "password": "correct-horse-battery",
            "confirm_password": "does-not-match",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Passwords must match" in response.data
