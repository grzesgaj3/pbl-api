from __future__ import annotations

import hashlib
import hmac
import secrets

_KEY_BYTES = 32


def generate_api_key() -> str:
    return secrets.token_urlsafe(_KEY_BYTES)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(api_key), expected_hash)


def verify_admin_key(api_key: str, expected: str) -> bool:
    return hmac.compare_digest(api_key.encode("utf-8"), expected.encode("utf-8"))
