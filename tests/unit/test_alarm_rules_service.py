from __future__ import annotations

import pytest
from tests.factories import make_organization

from licensing.exceptions import NotFoundError
from licensing.services import alarm_rules as alarm_rules_service
from licensing.services import chambers as chambers_service


def _make_chamber(session, org):
    return chambers_service.create(
        session,
        organization_id=org.id,
        name="Chamber 1",
        host="127.0.0.1",
        port=5555,
        created_by_user_id=None,
    )


def _rule_kwargs(**overrides):
    kwargs = {
        "name": "High Temp",
        "variable": "temp",
        "condition": "above",
        "value": 85.0,
        "value2": None,
        "severity": "Critical",
        "deadband": 0.5,
        "delay_s": 10.0,
        "enabled": True,
        "created_by_user_id": None,
    }
    kwargs.update(overrides)
    return kwargs


def test_create_and_list_for_organization(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)
    chamber = _make_chamber(db_session, org)

    created = alarm_rules_service.create(
        db_session, organization_id=org.id, chamber_id=chamber.id, **_rule_kwargs()
    )

    rules = alarm_rules_service.list_for_organization(db_session, org.id)
    assert [r.id for r in rules] == [created.id]
    assert rules[0].chamber_id == chamber.id


def test_create_rejects_chamber_from_another_organization(db_session) -> None:  # type: ignore[no-untyped-def]
    org_a = make_organization(db_session)
    org_b = make_organization(db_session)
    chamber = _make_chamber(db_session, org_a)

    with pytest.raises(NotFoundError):
        alarm_rules_service.create(
            db_session, organization_id=org_b.id, chamber_id=chamber.id, **_rule_kwargs()
        )


def test_list_for_organization_excludes_other_organizations(db_session) -> None:  # type: ignore[no-untyped-def]
    org_a = make_organization(db_session)
    org_b = make_organization(db_session)
    chamber = _make_chamber(db_session, org_a)
    alarm_rules_service.create(
        db_session, organization_id=org_a.id, chamber_id=chamber.id, **_rule_kwargs()
    )

    assert alarm_rules_service.list_for_organization(db_session, org_b.id) == []


def test_replace_content_updates_thresholds(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)
    chamber = _make_chamber(db_session, org)
    rule = alarm_rules_service.create(
        db_session, organization_id=org.id, chamber_id=chamber.id, **_rule_kwargs()
    )

    updated = alarm_rules_service.replace_content(
        db_session,
        rule_id=rule.id,
        organization_id=org.id,
        name="High Temp",
        variable="temp",
        condition="above",
        value=90.0,
        value2=None,
        severity="Critical",
        deadband=1.0,
        delay_s=5.0,
        enabled=False,
    )

    assert updated.value == 90.0
    assert updated.enabled is False
