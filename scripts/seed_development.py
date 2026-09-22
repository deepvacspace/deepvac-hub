#!/usr/bin/env python
"""Seed development reference data: the deepvac-insight product, its
editions and features; (if a generated keypair is present) the signing_keys
row for the active signing key; and a demo organization/user/license so
the desktop activation flow can be verified end to end locally.

Idempotent — safe to run multiple times.

Usage:
    python scripts/seed_development.py [--key-id ID --public-key-file PATH]
"""

from __future__ import annotations

import argparse
import base64
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from licensing.database import session_scope  # noqa: E402
from licensing.models.certificates import SigningKey  # noqa: E402
from licensing.models.enums import (  # noqa: E402
    EditionStatus,
    MembershipRole,
    MembershipStatus,
    OrganizationLicenseStatus,
    OrganizationStatus,
    ProductStatus,
    SigningKeyStatus,
    UserStatus,
    VendorRole,
)
from licensing.models.licenses import OrganizationLicense  # noqa: E402
from licensing.models.organizations import Organization, OrganizationMembership  # noqa: E402
from licensing.models.products import Edition, EditionFeature, Feature, Product  # noqa: E402
from licensing.models.users import User  # noqa: E402
from licensing.security.passwords import hash_password  # noqa: E402

DEMO_USER_EMAIL = "demo@example.com"
DEMO_USER_PASSWORD = "DemoPass123!"
DEMO_ORG_SLUG = "demo-org"
DEMO_EDITION_CODE = "standard"

ADMIN_DEMO_EMAIL = "admin-demo@example.com"
ADMIN_DEMO_PASSWORD = "AdminDemoPass123!"

ADMIN_DEMO_EMAIL = "admin-demo@example.com"
ADMIN_DEMO_PASSWORD = "AdminDemoPass123!"

PRODUCT_CODE = "deepvac-insight"

EDITIONS = ["standard"]

FEATURES = {
    "collaboration": "Real-time experiment collaboration",
    "annotations": "Experiment annotations",
    "reports": "Automated report generation",
}


def _get_or_create_product(session) -> Product:  # type: ignore[no-untyped-def]
    product = session.query(Product).filter(Product.code == PRODUCT_CODE).one_or_none()
    if product is None:
        product = Product(code=PRODUCT_CODE, name="deepvac Insight", status=ProductStatus.ACTIVE)
        session.add(product)
        session.flush()
    return product


def _get_or_create_feature(session, code: str, name: str) -> Feature:  # type: ignore[no-untyped-def]
    feature = session.query(Feature).filter(Feature.code == code).one_or_none()
    if feature is None:
        feature = Feature(code=code, name=name)
        session.add(feature)
        session.flush()
    return feature


def _get_or_create_edition(session, product: Product, code: str) -> Edition:  # type: ignore[no-untyped-def]
    edition = (
        session.query(Edition)
        .filter(Edition.product_id == product.id, Edition.code == code)
        .one_or_none()
    )
    if edition is None:
        edition = Edition(
            product_id=product.id, code=code, name=code.capitalize(), status=EditionStatus.ACTIVE
        )
        session.add(edition)
        session.flush()
    return edition


def seed_catalog(session) -> None:  # type: ignore[no-untyped-def]
    product = _get_or_create_product(session)
    features = {
        code: _get_or_create_feature(session, code, name) for code, name in FEATURES.items()
    }
    for edition_code in EDITIONS:
        edition = _get_or_create_edition(session, product, edition_code)
        for feature in features.values():
            exists = (
                session.query(EditionFeature)
                .filter(
                    EditionFeature.edition_id == edition.id,
                    EditionFeature.feature_id == feature.id,
                )
                .one_or_none()
            )
            if exists is None:
                session.add(EditionFeature(edition_id=edition.id, feature_id=feature.id))
    print(f"Seeded product {PRODUCT_CODE!r} with editions {EDITIONS} and features {list(FEATURES)}")


def seed_signing_key(session, key_id: str | None, public_key_file: str | None) -> None:  # type: ignore[no-untyped-def]
    if not key_id or not public_key_file:
        print("No --key-id/--public-key-file given; skipping signing_keys seed. "
              "Run scripts/generate_signing_key.py first if you need one.")
        return
    existing = session.query(SigningKey).filter(SigningKey.key_id == key_id).one_or_none()
    if existing is not None:
        print(f"signing_keys row for {key_id!r} already exists; leaving as-is.")
        return
    public_key_b64 = Path(public_key_file).read_text().strip()
    public_key_bytes = base64.urlsafe_b64decode(public_key_b64)
    now = datetime.now(UTC)
    session.add(
        SigningKey(
            key_id=key_id,
            algorithm="ed25519",
            public_key=public_key_bytes,
            status=SigningKeyStatus.ACTIVE,
            activated_at=now,
            created_at=now,
        )
    )
    print(f"Seeded signing_keys row for {key_id!r}")


def seed_demo_organization(session) -> None:  # type: ignore[no-untyped-def]
    """Creates a demo user + organization + active license, so the desktop
    app's activation flow has something real to activate against without
    any manual DB setup. Any active member of the org can activate -- there
    is no separate seat-assignment step.
    """
    now = datetime.now(UTC)

    user = session.query(User).filter(User.normalized_email == DEMO_USER_EMAIL).one_or_none()
    if user is None:
        user = User(
            email=DEMO_USER_EMAIL,
            normalized_email=DEMO_USER_EMAIL,
            password_hash=hash_password(DEMO_USER_PASSWORD),
            display_name="Demo User",
            status=UserStatus.ACTIVE,
            email_verified_at=now,
        )
        session.add(user)
        session.flush()

    org = session.query(Organization).filter(Organization.slug == DEMO_ORG_SLUG).one_or_none()
    if org is None:
        org = Organization(name="Demo Org", slug=DEMO_ORG_SLUG, status=OrganizationStatus.ACTIVE)
        session.add(org)
        session.flush()

    membership = (
        session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == MembershipStatus.ACTIVE,
        )
        .one_or_none()
    )
    if membership is None:
        session.add(
            OrganizationMembership(
                organization_id=org.id,
                user_id=user.id,
                role=MembershipRole.ORGANIZATION_ADMIN,
                status=MembershipStatus.ACTIVE,
                joined_at=now,
            )
        )
        session.flush()

    product = session.query(Product).filter(Product.code == PRODUCT_CODE).one()
    edition = (
        session.query(Edition)
        .filter(Edition.product_id == product.id, Edition.code == DEMO_EDITION_CODE)
        .one()
    )

    org_license = (
        session.query(OrganizationLicense)
        .filter(
            OrganizationLicense.organization_id == org.id,
            OrganizationLicense.product_id == product.id,
            OrganizationLicense.edition_id == edition.id,
        )
        .one_or_none()
    )
    if org_license is None:
        org_license = OrganizationLicense(
            organization_id=org.id,
            product_id=product.id,
            edition_id=edition.id,
            status=OrganizationLicenseStatus.ACTIVE,
            device_limit_per_user=3,
            starts_at=now,
            expires_at=now + timedelta(days=365),
            offline_validity_days=36500,  # lifetime grant; see README's Phase D notes
        )
        session.add(org_license)
        session.flush()

    print(
        f"Seeded demo organization {DEMO_ORG_SLUG!r} with an active "
        f"{DEMO_EDITION_CODE} license for {PRODUCT_CODE!r}.\n"
        f"Demo portal login: {DEMO_USER_EMAIL} / {DEMO_USER_PASSWORD}"
    )


def seed_vendor_admin(session) -> None:  # type: ignore[no-untyped-def]
    """Creates a vendor_super_admin portal login for exercising vendor-only
    screens locally."""
    now = datetime.now(UTC)
    user = session.query(User).filter(User.normalized_email == ADMIN_DEMO_EMAIL).one_or_none()
    if user is None:
        user = User(
            email=ADMIN_DEMO_EMAIL,
            normalized_email=ADMIN_DEMO_EMAIL,
            password_hash=hash_password(ADMIN_DEMO_PASSWORD),
            display_name="Admin Demo",
            status=UserStatus.ACTIVE,
            vendor_role=VendorRole.VENDOR_SUPER_ADMIN,
            email_verified_at=now,
        )
        session.add(user)
        session.flush()
    print(f"Seeded vendor_super_admin portal login: {ADMIN_DEMO_EMAIL} / {ADMIN_DEMO_PASSWORD}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-id", default=None)
    parser.add_argument("--public-key-file", default=None)
    args = parser.parse_args()

    with session_scope() as session:
        seed_catalog(session)
        seed_signing_key(session, args.key_id, args.public_key_file)
        seed_demo_organization(session)
        seed_vendor_admin(session)


if __name__ == "__main__":
    main()
