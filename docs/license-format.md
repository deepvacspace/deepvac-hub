# Cryptographic License Format

## Decision

* **Algorithm: Ed25519** (via the `cryptography` package,
  `cryptography.hazmat.primitives.asymmetric.ed25519`). Deterministic
  signatures, small keys (32-byte public, 32-byte seed), fast verification on
  desktop hardware, no parameter choices to get wrong (unlike RSA padding or
  ECDSA curve/nonce selection). No documented compatibility reason to deviate.
* **Signing is for authenticity/integrity, not secrecy.** The payload is
  transmitted and stored as plaintext JSON; only the signature is
  cryptographic. This is intentional per the spec — do not encrypt.
* **Canonical serialization: JCS-style deterministic JSON** — see below.
* **Envelope**, returned to the desktop app as a single versioned JSON object:

```json
{
  "envelope_version": 1,
  "payload": {
    "schema_version": 1,
    "license_id": "b6f2b8b0-...-uuid",
    "user_id": "uuid",
    "organization_id": "uuid",
    "device_id": "uuid",
    "device_public_key_hash": "base64url-sha256-of-device-public-key",
    "product_code": "deepvac-insight",
    "edition_code": "professional",
    "features": ["collaboration", "annotations", "reports"],
    "issued_at": "2026-07-17T00:00:00Z",
    "not_before": "2026-07-17T00:00:00Z",
    "expires_at": "2026-08-17T00:00:00Z",
    "key_id": "license-signing-key-2026-01",
    "license_version": 1
  },
  "signature": "base64url-ed25519-signature-over-canonical-payload-bytes",
  "key_id": "license-signing-key-2026-01"
}
```

## Canonical serialization rule

To make "the bytes that were signed" unambiguous and reproducible in any
language:

1. Take the payload as a JSON object with **exactly** the keys defined by the
   schema (no extra keys, no omitted keys).
2. Serialize using JSON with:
   * UTF-8 encoding
   * Object keys sorted lexicographically by Unicode code point
     (`sort_keys=True`)
   * No insignificant whitespace (`separators=(",", ":")`)
   * No trailing newline
3. The resulting byte string is the message signed/verified by Ed25519.

This is implemented once, in `src/licensing/licensing/canonical.py`, and used
identically for signing (server) and for the reference verifier (tests, and
later the desktop client port). It is deliberately a subset of RFC 8785 (JCS)
sufficient for our fixed, flat/shallow schema — full JCS number/unicode
normalization is unnecessary because every field is a string, int, or list of
strings.

## Field trust rules

* `product_code`, `edition_code`, `features`, `organization_id`, `device_id`
  are **never taken from client input** at issuance time — they are derived
  server-side from the authenticated device activation, its organization
  license, and the edition's granted features at the moment of signing.
  Issuance happens exactly once, at activation completion — there is no
  renewal call that re-derives/re-signs these later (licenses are lifetime
  grants; see `docs/threat-model.md`).
* `device_public_key_hash` is SHA-256 of the exact public key bytes stored in
  `device_activations.device_public_key` — binding the certificate to one
  registered device.
* Clients only ever supply: the activation user code (during activation) and
  the device public key (once, at registration). Neither influences payload
  field values directly; they gate *whether* a payload is issued and *which*
  device it is bound to.

## Verification (desktop side, and test suite)

```
verify(envelope, trusted_public_keys) -> Payload:
    key = trusted_public_keys[envelope.key_id]   # reject unknown key_id
    canonical_bytes = canonicalize(envelope.payload)
    key.verify(envelope.signature, canonical_bytes)   # raises on tamper
    assert envelope.payload.schema_version == 1
    assert now_utc() >= payload.not_before
    assert now_utc() <  payload.expires_at
    assert sha256(local_device_public_key) == payload.device_public_key_hash
    return payload
```

Any bit-level change to `payload` (including key reordering that changes
canonical bytes only if values change — reordering keys alone does **not**
change canonical bytes, which is the point of canonicalization) invalidates
the signature. Test vectors covering exact byte sequences live in
`tests/unit/test_license_signing.py` and `tests/security/test_license_tamper.py`.

## Key rotation

* `signing_keys` table stores only public metadata (`key_id`, `algorithm`,
  `public_key`, `status: active|retired`, `activated_at`, `retired_at`).
* The private key is loaded at process start from
  `LICENSE_SIGNING_PRIVATE_KEY_PATH` (a file mounted from a secret store),
  identified by `LICENSE_SIGNING_KEY_ID`. It is never written to the database,
  never logged, never serialized into an API response.
* To rotate: generate a new keypair with `scripts/generate_signing_key.py`,
  insert its public key as a new `signing_keys` row with `status=active`,
  deploy the new private key + key_id to the signing environment, then mark
  the previous key `status=retired` (kept, not deleted, so certificates it
  already signed remain verifiable until they naturally expire).
* `GET /api/v1/licensing/public-keys` returns all `active` and any `retired`
  keys that still have non-expired certificates outstanding, so clients
  holding older certificates can still verify them through natural expiry.
