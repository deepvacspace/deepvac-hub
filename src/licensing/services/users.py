"""Vendor-managed user directory: the global identity list, vendor-only.

Organization membership (who belongs to which org) is managed via
services/organizations.py -- this module owns the account records
themselves (creation, status, password, vendor role).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from licensing.exceptions import ConflictError, NotFoundError
from licensing.models.enums import MembershipRole, MembershipStatus, UserStatus, VendorRole
from licensing.models.organizations import OrganizationMembership
from licensing.models.users import User
from licensing.pagination import Page, paginate
from licensing.services import auth as auth_service

MIN_PASSWORD_LENGTH = 12


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ConflictError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")


def _require_not_deleted(user: User) -> None:
    if user.status == UserStatus.DELETED:
        raise ConflictError("This account has been deleted.")


def create_user(
    session: Session, *, actor: User, email: str, display_name: str, password: str
) -> User:
    from licensing.security.passwords import hash_password

    auth_service.require_vendor(actor, write=True)
    _validate_password(password)
    normalized_email = email.strip().lower()
    existing = session.execute(
        select(User).where(User.normalized_email == normalized_email)
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"A user with email {email!r} already exists.")
    user = User(
        email=email.strip(),
        normalized_email=normalized_email,
        display_name=display_name,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        email_verified_at=datetime.now(UTC),
    )
    session.add(user)
    session.flush()
    return user


def change_own_password(
    session: Session, *, user: User, current_password: str, new_password: str
) -> None:
    """Self-service password change -- no vendor/org authorization needed,
    the acting user is only ever touching their own account."""
    from licensing.exceptions import InvalidCredentialsError
    from licensing.security.passwords import hash_password, verify_password

    if not verify_password(current_password, user.password_hash):
        raise InvalidCredentialsError("Current password is incorrect.")
    _validate_password(new_password)
    user.password_hash = hash_password(new_password)
    session.flush()


def get_user(session: Session, *, actor: User, user_id: uuid.UUID) -> User:
    auth_service.require_vendor(actor)
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found.")
    return user


def list_users(
    session: Session,
    *,
    actor: User,
    q: str | None = None,
    status: UserStatus | None = None,
    page: int = 1,
    per_page: int = 25,
) -> Page[User]:
    auth_service.require_vendor(actor)
    stmt = (
        select(User)
        .options(selectinload(User.memberships).selectinload(OrganizationMembership.organization))
        .order_by(User.display_name)
    )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(User.display_name.ilike(like), User.normalized_email.ilike(like)))
    if status is not None:
        stmt = stmt.where(User.status == status)
    return paginate(session, stmt, page=page, per_page=per_page)


def set_user_status(
    session: Session, *, actor: User, user_id: uuid.UUID, status: UserStatus
) -> User:
    auth_service.require_vendor(actor, write=True)
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found.")
    _require_not_deleted(user)
    user.status = status
    session.flush()
    return user


def set_user_password(
    session: Session, *, actor: User, user_id: uuid.UUID, new_password: str
) -> User:
    from licensing.security.passwords import hash_password

    auth_service.require_vendor(actor, write=True)
    _validate_password(new_password)
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found.")
    _require_not_deleted(user)
    user.password_hash = hash_password(new_password)
    session.flush()
    return user


def set_vendor_role(
    session: Session, *, actor: User, user_id: uuid.UUID, vendor_role: VendorRole | None
) -> User:
    auth_service.require_vendor(actor, write=True)
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found.")
    _require_not_deleted(user)
    user.vendor_role = vendor_role
    session.flush()
    return user


def list_memberships_for_user(
    session: Session, *, actor: User, user_id: uuid.UUID
) -> list[OrganizationMembership]:
    auth_service.require_vendor(actor)
    return list(
        session.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.status == MembershipStatus.ACTIVE,
            )
        ).scalars()
    )


def _is_last_active_admin(
    session: Session, *, organization_id: uuid.UUID, membership_id: uuid.UUID
) -> bool:
    other_admins = session.execute(
        select(func.count()).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == MembershipRole.ORGANIZATION_ADMIN,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
            OrganizationMembership.id != membership_id,
        )
    ).scalar_one()
    return other_admins == 0


def delete_own_account(session: Session, *, user: User, current_password: str) -> None:
    """Self-service account deletion -- no vendor/org authorization needed,
    the acting user is only ever touching their own account. Soft-deletes:
    clears PII and marks the account deleted without removing the row."""
    from licensing.exceptions import InvalidCredentialsError
    from licensing.security.passwords import hash_password, verify_password

    if not verify_password(current_password, user.password_hash):
        raise InvalidCredentialsError("Password is incorrect.")

    active_memberships = [m for m in user.memberships if m.status == MembershipStatus.ACTIVE]
    for membership in active_memberships:
        if membership.role == MembershipRole.ORGANIZATION_ADMIN and _is_last_active_admin(
            session, organization_id=membership.organization_id, membership_id=membership.id
        ):
            raise ConflictError(
                "You are the last admin of an organization you belong to. "
                "Promote another member to admin before deleting your account."
            )

    now = datetime.now(UTC)
    for membership in active_memberships:
        membership.status = MembershipStatus.REMOVED
        membership.removed_at = now

    user.display_name = "Deleted user"
    user.email = f"deleted-{user.id}@deleted.invalid"
    user.normalized_email = f"deleted-{user.id}@deleted.invalid"
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    user.vendor_role = None
    user.status = UserStatus.DELETED
    session.flush()
