"""API-key generation, hashing and constant-time comparison helpers.

Bridge keys are random 256-bit tokens; only their SHA-256 hash is stored.
Because the tokens already carry full entropy, a fast hash is sufficient
(unlike password hashing, where a slow KDF is required).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_KEY_BYTES = 32


def generate_api_key() -> str:
    """Return a new URL-safe random API key (plaintext)."""
    return secrets.token_urlsafe(_KEY_BYTES)


def hash_api_key(api_key: str) -> str:
    """Return the hex-encoded SHA-256 digest of ``api_key``."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, expected_hash: str) -> bool:
    """Constant-time check that ``api_key`` matches a stored hash."""
    return hmac.compare_digest(hash_api_key(api_key), expected_hash)


def verify_admin_key(api_key: str, expected: str) -> bool:
    """Constant-time comparison of a supplied admin key against the configured one."""
    return hmac.compare_digest(api_key.encode("utf-8"), expected.encode("utf-8"))
