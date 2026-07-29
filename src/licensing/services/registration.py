"""Public self-service signup.

Unlike every other user/organization creation path in this codebase, there
is no authenticated actor here -- an anonymous visitor creates their own
Organization and becomes its sole organization_admin in one step. This
module therefore does not go through services/auth.py's require_vendor
gate the way services/organizations.py and services/users.py do.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from licensing.exceptions import ConflictError
from licensing.models.enums import (
    MembershipRole,
    MembershipStatus,
    OrganizationStatus,
    UserStatus,
)
from licensing.models.organizations import Organization, OrganizationMembership
from licensing.models.users import User
from licensing.security.passwords import hash_password
from licensing.services.organizations import slugify
from licensing.services.users import MIN_PASSWORD_LENGTH


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ConflictError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")


def _unique_slug(session: Session, base_slug: str) -> str:
    slug = base_slug
    suffix = 2
    while (
        session.execute(select(Organization).where(Organization.slug == slug)).scalar_one_or_none()
        is not None
    ):
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


def register_organization_and_owner(
    session: Session,
    *,
    organization_name: str,
    email: str,
    display_name: str,
    password: str,
) -> tuple[Organization, User]:
    _validate_password(password)
    normalized_email = email.strip().lower()
    existing_user = session.execute(
        select(User).where(User.normalized_email == normalized_email)
    ).scalar_one_or_none()
    if existing_user is not None:
        raise ConflictError(f"A user with email {email!r} already exists.")

    slug = _unique_slug(session, slugify(organization_name))
    org = Organization(name=organization_name.strip(), slug=slug, status=OrganizationStatus.ACTIVE)
    session.add(org)
    session.flush()

    user = User(
        email=email.strip(),
        normalized_email=normalized_email,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        email_verified_at=datetime.now(UTC),
    )
    session.add(user)
    session.flush()

    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role=MembershipRole.ORGANIZATION_ADMIN,
        status=MembershipStatus.ACTIVE,
        joined_at=datetime.now(UTC),
    )
    session.add(membership)
    session.flush()

    return org, user
