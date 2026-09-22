"""Static privacy-boundary check (section 11 of the spec / docs/privacy.md).

Fails the build if any SQLAlchemy model column, Pydantic schema field, or
audit-metadata allow-list entry uses a name that suggests experiment data
has crept into the licensing control plane's schema. This is a coarse,
name-based check by design — it is meant to catch accidental regressions
early and cheaply, not to replace human review of new fields.
"""

from __future__ import annotations

import re

from sqlalchemy import inspect as sa_inspect

import licensing.models  # noqa: F401
from licensing.audit.allowlist import ALLOWED_METADATA_KEYS
from licensing.database import Base
from licensing.schemas.account_link import AccountInfo, SignedAccountInfo
from licensing.schemas.license import LicensePayload, SignedLicenseEnvelope

PROHIBITED_TERMS = [
    "experiment",
    "filename",
    "file_path",
    "filepath",
    "measurement",
    "channel",
    "annotation",
    "project",
]

# device_public_key_hash / device_public_key legitimately contain "hash"/"key"
# but never any of the prohibited terms above, so no allow-list exceptions
# are needed for the current schema.

_PROHIBITED_RE = re.compile("|".join(PROHIBITED_TERMS), re.IGNORECASE)


def _offending(names: set[str]) -> list[str]:
    return sorted(n for n in names if _PROHIBITED_RE.search(n))


def test_no_prohibited_fields_in_sqlalchemy_models() -> None:
    offenders: dict[str, list[str]] = {}
    for mapper in Base.registry.mappers:
        table_name = (
            mapper.local_table.name
            if mapper.local_table is not None
            else mapper.class_.__name__
        )
        column_names = {column.name for column in mapper.columns}
        bad = _offending(column_names)
        if bad:
            offenders[table_name] = bad
    assert not offenders, f"Prohibited experiment-shaped columns found: {offenders}"


def test_no_prohibited_fields_in_license_schemas() -> None:
    for schema in (LicensePayload, SignedLicenseEnvelope, AccountInfo, SignedAccountInfo):
        bad = _offending(set(schema.model_fields.keys()))
        assert not bad, f"{schema.__name__} has prohibited fields: {bad}"


def test_audit_metadata_allowlist_has_no_prohibited_terms() -> None:
    bad = _offending(set(ALLOWED_METADATA_KEYS))
    assert not bad, f"Audit metadata allow-list has prohibited terms: {bad}"


def test_inspect_smoke() -> None:
    # Sanity check that sa_inspect works on at least one mapped class, so the
    # main assertion above isn't silently iterating over zero mappers.
    from licensing.models.users import User

    assert sa_inspect(User).columns.keys()
