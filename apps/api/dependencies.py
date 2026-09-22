"""FastAPI dependency providers. Thin wiring only — no business logic."""

from __future__ import annotations

import base64
from collections.abc import Generator
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from licensing.config import get_settings
from licensing.database import get_sessionmaker
from licensing.exceptions import InvalidSignatureError
from licensing.models.licenses import OrganizationLicense
from licensing.security.signing import load_private_key_from_file
from licensing.services import devices as devices_service


def get_db() -> Generator[Session, None, None]:
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@dataclass(frozen=True)
class SigningContext:
    key_id: str
    private_key: Ed25519PrivateKey


@lru_cache
def get_signing_context() -> SigningContext:
    """Loaded once per process from the deployment secret file -- never from
    the database, never logged (see docs/license-format.md key rotation).
    """
    settings = get_settings()
    key_path = settings.require_signing_key_path()
    private_key = load_private_key_from_file(key_path)
    return SigningContext(key_id=settings.license_signing_key_id, private_key=private_key)


@dataclass(frozen=True)
class DeviceContext:
    device_activation_id: UUID
    organization_id: UUID


async def get_device_context(request: Request, db: Session = Depends(get_db)) -> DeviceContext:
    """Authenticates a request by its device's Ed25519 signature and returns
    its licensed organization."""
    key_hash = request.headers.get("X-Device-Key-Hash")
    signature_b64 = request.headers.get("X-Device-Signature")
    if not key_hash or not signature_b64:
        raise InvalidSignatureError("Missing device signature headers.")

    device = devices_service.get_active_by_public_key_hash(db, key_hash)
    if device is None:
        raise InvalidSignatureError("Unknown or inactive device.")

    body = await request.body()
    try:
        signature = base64.urlsafe_b64decode(signature_b64)
        Ed25519PublicKey.from_public_bytes(device.device_public_key).verify(signature, body)
    except (InvalidSignature, ValueError) as exc:
        raise InvalidSignatureError("Device signature verification failed.") from exc

    org_license = db.get(OrganizationLicense, device.organization_license_id)
    assert org_license is not None
    return DeviceContext(
        device_activation_id=device.id, organization_id=org_license.organization_id
    )
