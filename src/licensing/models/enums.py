"""Status/role enums shared across models. Kept as plain str Enums so both
SQLAlchemy (native Postgres ENUM) and Pydantic schemas can reuse them
directly without duplication.
"""

from __future__ import annotations

from enum import StrEnum


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class VendorRole(StrEnum):
    """Global, not organization-scoped. Lives on User.vendor_role. A vendor
    support user does NOT automatically gain organization_admin rights over
    any organization — support access is a separate, explicitly constrained
    and audited code path, added in Phase C/F.
    """

    VENDOR_SUPER_ADMIN = "vendor_super_admin"
    VENDOR_SUPPORT = "vendor_support"


class MembershipRole(StrEnum):
    """Organization-scoped roles only, held via OrganizationMembership."""

    ORGANIZATION_ADMIN = "organization_admin"
    ORGANIZATION_MEMBER = "organization_member"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"


class ProductStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class EditionStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


class OrganizationLicenseStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"


class DeviceActivationStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"
    REPLACED = "replaced"


class ActivationRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CONSUMED = "consumed"


class IssuedCertificateStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


class SigningKeyStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"
