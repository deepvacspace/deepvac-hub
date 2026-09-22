"""Chamber-registry sync endpoints, scoped to the calling device's organization."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.dependencies import DeviceContext, get_db, get_device_context
from licensing.schemas.chambers import ChamberIn, ChamberListResponse, ChamberOut
from licensing.services import chambers as chambers_service

router = APIRouter(tags=["chambers"])


@router.get("/chambers", response_model=ChamberListResponse)
def list_chambers(
    db: Session = Depends(get_db),
    device: DeviceContext = Depends(get_device_context),
) -> ChamberListResponse:
    chambers = chambers_service.list_for_organization(db, device.organization_id)
    return ChamberListResponse(chambers=[ChamberOut.model_validate(c) for c in chambers])


@router.post("/chambers", response_model=ChamberOut, status_code=201)
def create_chamber(
    payload: ChamberIn,
    db: Session = Depends(get_db),
    device: DeviceContext = Depends(get_device_context),
) -> ChamberOut:
    chamber = chambers_service.create(
        db,
        organization_id=device.organization_id,
        name=payload.name,
        host=payload.host,
        port=payload.port,
        created_by_user_id=None,
    )
    return ChamberOut.model_validate(chamber)


@router.post("/chambers/{chamber_id}/replace", response_model=ChamberOut)
def replace_chamber(
    chamber_id: uuid.UUID,
    payload: ChamberIn,
    db: Session = Depends(get_db),
    device: DeviceContext = Depends(get_device_context),
) -> ChamberOut:
    chamber = chambers_service.replace_content(
        db,
        chamber_id=chamber_id,
        organization_id=device.organization_id,
        name=payload.name,
        host=payload.host,
        port=payload.port,
    )
    return ChamberOut.model_validate(chamber)
