"""Test-profile sync endpoints, scoped to the calling device's organization."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.dependencies import DeviceContext, get_db, get_device_context
from licensing.schemas.test_profiles import (
    TestProfileIn,
    TestProfileListResponse,
    TestProfileOut,
)
from licensing.services import test_profiles as test_profiles_service

router = APIRouter(tags=["test-profiles"])


@router.get("/test-profiles", response_model=TestProfileListResponse)
def list_test_profiles(
    db: Session = Depends(get_db),
    device: DeviceContext = Depends(get_device_context),
) -> TestProfileListResponse:
    profiles = test_profiles_service.list_for_organization(db, device.organization_id)
    return TestProfileListResponse(profiles=[TestProfileOut.model_validate(p) for p in profiles])


@router.post("/test-profiles", response_model=TestProfileOut, status_code=201)
def create_test_profile(
    payload: TestProfileIn,
    db: Session = Depends(get_db),
    device: DeviceContext = Depends(get_device_context),
) -> TestProfileOut:
    profile = test_profiles_service.create(
        db,
        organization_id=device.organization_id,
        name=payload.name,
        description=payload.description,
        steps=[step.model_dump() for step in payload.steps],
        created_by_user_id=None,
    )
    return TestProfileOut.model_validate(profile)


@router.post("/test-profiles/{profile_id}/replace", response_model=TestProfileOut)
def replace_test_profile(
    profile_id: uuid.UUID,
    payload: TestProfileIn,
    db: Session = Depends(get_db),
    device: DeviceContext = Depends(get_device_context),
) -> TestProfileOut:
    profile = test_profiles_service.replace_content(
        db,
        profile_id=profile_id,
        organization_id=device.organization_id,
        name=payload.name,
        description=payload.description,
        steps=[step.model_dump() for step in payload.steps],
    )
    return TestProfileOut.model_validate(profile)
