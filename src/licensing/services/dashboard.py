"""Vendor-console summary counts. No audit-derived widgets here on purpose
-- the filterable /audit page is Phase F's job, not this dashboard's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from licensing.models.enums import OrganizationLicenseStatus, OrganizationStatus
from licensing.models.licenses import OrganizationLicense
from licensing.models.organizations import Organization
from licensing.models.users import User
from licensing.services import auth as auth_service


@dataclass
class DashboardSummary:
    active_organizations: int
    active_licenses: int
    expiring_licenses: list[OrganizationLicense]


def get_summary(
    session: Session, *, actor: User, expiring_within_days: int = 30
) -> DashboardSummary:
    auth_service.require_vendor(actor)

    active_organizations = session.execute(
        select(func.count()).where(Organization.status == OrganizationStatus.ACTIVE)
    ).scalar_one()

    active_licenses = session.execute(
        select(func.count()).where(
            OrganizationLicense.status == OrganizationLicenseStatus.ACTIVE
        )
    ).scalar_one()

    horizon = datetime.now(UTC) + timedelta(days=expiring_within_days)
    expiring_licenses = list(
        session.execute(
            select(OrganizationLicense)
            .where(
                OrganizationLicense.status == OrganizationLicenseStatus.ACTIVE,
                OrganizationLicense.expires_at <= horizon,
            )
            .order_by(OrganizationLicense.expires_at)
        ).scalars()
    )

    return DashboardSummary(
        active_organizations=active_organizations,
        active_licenses=active_licenses,
        expiring_licenses=expiring_licenses,
    )
