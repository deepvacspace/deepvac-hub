"""Organization lifecycle and membership management.

Every function takes the acting user and authorizes via services/auth.py
before touching data -- see docs/threat-model.md threat #9 (cross-org
access must be enforced in the service layer, not just the route).
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from licensing.exceptions import ConflictError, NotFoundError
from licensing.models.enums import MembershipRole, MembershipStatus, OrganizationStatus
from licensing.models.organizations import Organization, OrganizationMembership
from licensing.models.users import User
from licensing.pagination import Page, paginate
from licensing.services import auth as auth_service

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def slugify(name: str) -> str:
    """Best-effort default slug suggestion; the admin can still edit it."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "org"


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        raise ConflictError(
            "Slug must be lowercase letters, numbers, and hyphens only (e.g. 'acme-labs')."
        )


def _active_admin_count(session: Session, organization_id: uuid.UUID) -> int:
    return session.execute(
        select(func.count()).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == MembershipRole.ORGANIZATION_ADMIN,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
    ).scalar_one()


def create_organization(session: Session, *, actor: User, name: str, slug: str) -> Organization:
    auth_service.require_vendor(actor, write=True)
    _validate_slug(slug)
    existing = session.execute(
        select(Organization).where(Organization.slug == slug)
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"An organization with slug {slug!r} already exists.")
    org = Organization(name=name, slug=slug, status=OrganizationStatus.ACTIVE)
    session.add(org)
    session.flush()
    return org


def get_organization(
    session: Session, *, actor: User, organization_id: uuid.UUID
) -> Organization:
    org = session.get(Organization, organization_id)
    if org is None:
        raise NotFoundError(f"Organization {organization_id} not found.")
    auth_service.require_org_view(session, actor, organization_id)
    return org


def list_organizations(
    session: Session,
    *,
    actor: User,
    q: str | None = None,
    status: OrganizationStatus | None = None,
    page: int = 1,
    per_page: int = 25,
) -> Page[Organization]:
    auth_service.require_vendor(actor)
    stmt = select(Organization).order_by(Organization.name)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Organization.name.ilike(like), Organization.slug.ilike(like)))
    if status is not None:
        stmt = stmt.where(Organization.status == status)
    return paginate(session, stmt, page=page, per_page=per_page)


def update_organization(
    session: Session, *, actor: User, organization_id: uuid.UUID, name: str, slug: str
) -> Organization:
    auth_service.require_vendor(actor, write=True)
    org = session.get(Organization, organization_id)
    if org is None:
        raise NotFoundError(f"Organization {organization_id} not found.")
    if slug != org.slug:
        _validate_slug(slug)
        existing = session.execute(
            select(Organization).where(Organization.slug == slug)
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(f"An organization with slug {slug!r} already exists.")
    org.name = name
    org.slug = slug
    session.flush()
    return org


def set_organization_status(
    session: Session, *, actor: User, organization_id: uuid.UUID, status: OrganizationStatus
) -> Organization:
    auth_service.require_vendor(actor, write=True)
    org = session.get(Organization, organization_id)
    if org is None:
        raise NotFoundError(f"Organization {organization_id} not found.")
    org.status = status
    session.flush()
    return org


def list_memberships(
    session: Session, *, actor: User, organization_id: uuid.UUID
) -> list[OrganizationMembership]:
    auth_service.require_org_view(session, actor, organization_id)
    return list(
        session.execute(
            select(OrganizationMembership)
            .where(OrganizationMembership.organization_id == organization_id)
            .where(OrganizationMembership.status == MembershipStatus.ACTIVE)
            .join(User, OrganizationMembership.user_id == User.id)
            .order_by(User.display_name)
        ).scalars()
    )


def add_membership(
    session: Session,
    *,
    actor: User,
    organization_id: uuid.UUID,
    user_email: str,
    role: MembershipRole,
) -> OrganizationMembership:
    auth_service.require_org_admin(session, actor, organization_id)
    normalized_email = user_email.strip().lower()
    target_user = session.execute(
        select(User).where(User.normalized_email == normalized_email)
    ).scalar_one_or_none()
    if target_user is None:
        raise NotFoundError(
            f"No user found with email {user_email!r}. Create the user first."
        )
    existing = auth_service.get_active_membership(
        session, user_id=target_user.id, organization_id=organization_id
    )
    if existing is not None:
        raise ConflictError(f"{user_email} is already a member of this organization.")
    membership = OrganizationMembership(
        organization_id=organization_id,
        user_id=target_user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
        joined_at=datetime.now(UTC),
    )
    session.add(membership)
    session.flush()
    return membership


def _get_membership_in_org(
    session: Session, *, organization_id: uuid.UUID, membership_id: uuid.UUID
) -> OrganizationMembership:
    membership = session.get(OrganizationMembership, membership_id)
    if membership is None or membership.organization_id != organization_id:
        raise NotFoundError(f"Membership {membership_id} not found in this organization.")
    return membership


def remove_membership(
    session: Session, *, actor: User, organization_id: uuid.UUID, membership_id: uuid.UUID
) -> None:
    auth_service.require_org_admin(session, actor, organization_id)
    membership = _get_membership_in_org(
        session, organization_id=organization_id, membership_id=membership_id
    )
    if (
        membership.role == MembershipRole.ORGANIZATION_ADMIN
        and membership.status == MembershipStatus.ACTIVE
        and _active_admin_count(session, organization_id) <= 1
    ):
        raise ConflictError(
            "Cannot remove the last organization admin. Promote another member first."
        )
    membership.status = MembershipStatus.REMOVED
    membership.removed_at = datetime.now(UTC)
    session.flush()


def change_membership_role(
    session: Session,
    *,
    actor: User,
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    role: MembershipRole,
) -> OrganizationMembership:
    auth_service.require_org_admin(session, actor, organization_id)
    membership = _get_membership_in_org(
        session, organization_id=organization_id, membership_id=membership_id
    )
    if (
        membership.role == MembershipRole.ORGANIZATION_ADMIN
        and role != MembershipRole.ORGANIZATION_ADMIN
        and _active_admin_count(session, organization_id) <= 1
    ):
        raise ConflictError(
            "Cannot demote the last organization admin. Promote another member first."
        )
    membership.role = role
    session.flush()
    return membership
