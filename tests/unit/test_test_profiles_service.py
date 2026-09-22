from __future__ import annotations

from tests.factories import make_organization

from licensing.services import test_profiles as test_profiles_service

_STEPS = [
    {"step_order": 0, "setpoint_temp": 25.0, "setpoint_pressure": None, "duration_s": 60.0, "label": "warm-up"},
    {"step_order": 1, "setpoint_temp": 85.0, "setpoint_pressure": None, "duration_s": 300.0, "label": "hold"},
]


def test_create_and_list_for_organization(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)

    created = test_profiles_service.create(
        db_session,
        organization_id=org.id,
        name="Thermal Test A",
        description="",
        steps=_STEPS,
        created_by_user_id=None,
    )

    profiles = test_profiles_service.list_for_organization(db_session, org.id)

    assert [p.id for p in profiles] == [created.id]
    assert [s.label for s in profiles[0].steps] == ["warm-up", "hold"]


def test_list_for_organization_excludes_other_organizations(db_session) -> None:  # type: ignore[no-untyped-def]
    org_a = make_organization(db_session)
    org_b = make_organization(db_session)
    test_profiles_service.create(
        db_session,
        organization_id=org_a.id,
        name="Org A Profile",
        description="",
        steps=_STEPS,
        created_by_user_id=None,
    )

    assert test_profiles_service.list_for_organization(db_session, org_b.id) == []


def test_replace_content_updates_steps(db_session) -> None:  # type: ignore[no-untyped-def]
    org = make_organization(db_session)
    profile = test_profiles_service.create(
        db_session,
        organization_id=org.id,
        name="Thermal Test A",
        description="",
        steps=_STEPS,
        created_by_user_id=None,
    )

    updated = test_profiles_service.replace_content(
        db_session,
        profile_id=profile.id,
        organization_id=org.id,
        name="Thermal Test A",
        description="revised",
        steps=[{"step_order": 0, "setpoint_temp": 30.0, "setpoint_pressure": None, "duration_s": 10.0, "label": "quick"}],
    )

    assert updated.description == "revised"
    assert [s.label for s in updated.steps] == ["quick"]
