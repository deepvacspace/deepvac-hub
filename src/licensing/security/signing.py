"""Ed25519 license signing and verification.

The private key object is held only in memory for the lifetime of the
process that loaded it (apps/api), constructed once from a file path
supplied by deployment secret storage. It is never logged, never returned
from any function other than the loader, and never serialized.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from licensing.exceptions import InvalidSignatureError
from licensing.licensing.canonical import REQUIRED_PAYLOAD_KEYS, canonicalize

ALGORITHM = "ed25519"


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def private_key_to_raw_bytes(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.private_bytes(
        encoding=Encoding.Raw, format=PrivateFormat.Raw, encryption_algorithm=NoEncryption()
    )


def public_key_to_raw_bytes(public_key: Ed25519PublicKey) -> bytes:
    return public_key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)


def load_private_key_from_file(path: str | Path) -> Ed25519PrivateKey:
    """Load a raw 32-byte Ed25519 private key from a file.

    Never call this outside the signing process (apps/api). Never log
    `path` contents or the returned object.
    """
    raw = Path(path).read_bytes()
    return Ed25519PrivateKey.from_private_bytes(raw)


def public_key_from_raw_bytes(raw: bytes) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(raw)


@dataclass(frozen=True)
class SignedEnvelope:
    envelope_version: int
    payload: dict[str, Any]
    signature_b64: str
    key_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_version": self.envelope_version,
            "payload": self.payload,
            "signature": self.signature_b64,
            "key_id": self.key_id,
        }


def sign_payload(
    payload: dict[str, Any],
    private_key: Ed25519PrivateKey,
    key_id: str,
    *,
    required_keys: frozenset[str] = REQUIRED_PAYLOAD_KEYS,
) -> SignedEnvelope:
    canonical_bytes = canonicalize(payload, required_keys=required_keys)
    signature = private_key.sign(canonical_bytes)
    return SignedEnvelope(
        envelope_version=1,
        payload=payload,
        signature_b64=base64.urlsafe_b64encode(signature).decode("ascii"),
        key_id=key_id,
    )


def verify_envelope(
    envelope: dict[str, Any],
    public_key: Ed25519PublicKey,
    *,
    required_keys: frozenset[str] = REQUIRED_PAYLOAD_KEYS,
) -> dict[str, Any]:
    """Verify a signed envelope's signature over its canonical payload bytes.

    Returns the payload dict on success. Raises InvalidSignatureError on any
    tamper (payload modification, wrong signature, wrong key). Does not
    check expiry/not_before — that is the caller's responsibility, since
    "now" is a policy concern, not a signature-verification concern.
    """
    canonical_bytes = canonicalize(envelope["payload"], required_keys=required_keys)
    signature = base64.urlsafe_b64decode(envelope["signature"])
    try:
        public_key.verify(signature, canonical_bytes)
    except InvalidSignature as exc:
        raise InvalidSignatureError("License signature verification failed") from exc
    payload: dict[str, Any] = envelope["payload"]
    return payload
