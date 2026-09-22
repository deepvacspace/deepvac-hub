"""Jinja filters for presenting domain enums in the portal UI."""

from __future__ import annotations

from licensing.models.enums import MembershipRole, MembershipStatus, VendorRole
from licensing.models.users import User

_MEMBERSHIP_ROLE_LABELS = {
    MembershipRole.ORGANIZATION_ADMIN: "Administrator",
    MembershipRole.ORGANIZATION_MEMBER: "Member",
}

_VENDOR_ROLE_LABELS = {
    VendorRole.VENDOR_SUPER_ADMIN: "Vendor Administrator",
    VendorRole.VENDOR_SUPPORT: "Vendor",
}


def membership_role_label(role: MembershipRole) -> str:
    return _MEMBERSHIP_ROLE_LABELS[MembershipRole(role)]


def user_role_label(user: User) -> str:
    """Single combined role label for the user directory."""
    if user.vendor_role is not None:
        return _VENDOR_ROLE_LABELS[user.vendor_role]
    active_roles = {m.role for m in user.memberships if m.status == MembershipStatus.ACTIVE}
    if MembershipRole.ORGANIZATION_ADMIN in active_roles:
        return "Administrator"
    if MembershipRole.ORGANIZATION_MEMBER in active_roles:
        return "Member"
    return "—"


def user_organizations_label(user: User) -> str:
    names = sorted(
        {m.organization.name for m in user.memberships if m.status == MembershipStatus.ACTIVE}
    )
    return ", ".join(names) if names else "—"
