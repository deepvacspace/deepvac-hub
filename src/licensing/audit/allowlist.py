"""Allow-list of metadata keys permitted in audit_events.metadata.

This exists so that a future change adding, say, `filename` or
`experiment_id` to an audit call raises immediately in tests and at
runtime, rather than silently persisting customer experiment data into the
vendor cloud. See docs/privacy.md.

Extend this list only with licensing/identity/administrative fields. If a
field name overlaps with the prohibited terms in
tests/security/test_privacy_boundary.py, it will not be addable here without
also updating that test's judgment — treat that as a deliberate speed bump,
not friction to route around.
"""

from __future__ import annotations

ALLOWED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "organization_slug",
        "user_email_domain",
        "product_code",
        "edition_code",
        "device_limit_per_user",
        "device_display_name",
        "role",
        "reason",
        "previous_status",
        "new_status",
        "signing_key_id",
        "activation_id",
        "organization_license_id",
    }
)


def assert_allowed_metadata(metadata: dict[str, object] | None) -> None:
    if not metadata:
        return
    disallowed = set(metadata.keys()) - ALLOWED_METADATA_KEYS
    if disallowed:
        from licensing.exceptions import ProhibitedFieldError

        raise ProhibitedFieldError(
            f"Audit metadata contains disallowed keys: {sorted(disallowed)}"
        )
