"""Device-activation registration and lookup.

Never accepts a device fingerprint derived from MAC address, CPU/disk
serial, or hostname (see docs/threat-model.md) -- the only identity here is
the device's own Ed25519 public key, supplied by the desktop client.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from licensing.exceptions import ConflictError, DeviceLimitExceededError
from licensing.models.devices import DeviceActivation
from licensing.models.enums import DeviceActivationStatus
from licensing.models.licenses import OrganizationLicense


def public_key_hash(device_public_key: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(device_public_key).digest()).decode("ascii")


def get_active_by_public_key_hash(session: Session, key_hash: str) -> DeviceActivation | None:
    device = session.execute(
        select(DeviceActivation).where(DeviceActivation.device_public_key_hash == key_hash)
    ).scalar_one_or_none()
    if device is None or device.status != DeviceActivationStatus.ACTIVE:
        return None
    return device


def register_device(
    session: Session,
    *,
    organization_license: OrganizationLicense,
    user_id: uuid.UUID,
    device_public_key: bytes,
    display_name: str | None = None,
) -> DeviceActivation:
    key_hash = public_key_hash(device_public_key)

    existing = session.execute(
        select(DeviceActivation).where(DeviceActivation.device_public_key_hash == key_hash)
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("This device public key is already registered.")

    active_device_count = session.execute(
        select(func.count()).where(
            DeviceActivation.organization_license_id == organization_license.id,
            DeviceActivation.user_id == user_id,
            DeviceActivation.status == DeviceActivationStatus.ACTIVE,
        )
    ).scalar_one()
    if active_device_count >= organization_license.device_limit_per_user:
        raise DeviceLimitExceededError(
            f"User {user_id} has reached the device limit "
            f"({active_device_count}/{organization_license.device_limit_per_user}) "
            f"for this license."
        )

    now = datetime.now(UTC)
    device = DeviceActivation(
        organization_license_id=organization_license.id,
        user_id=user_id,
        device_public_key=device_public_key,
        device_public_key_hash=key_hash,
        display_name=display_name,
        status=DeviceActivationStatus.ACTIVE,
        activated_at=now,
        last_renewed_at=now,
    )
    session.add(device)
    session.flush()
    return device
