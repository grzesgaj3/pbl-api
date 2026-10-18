"""Unit tests for the security helpers."""

from __future__ import annotations

from app.core.security import generate_api_key, hash_api_key, verify_admin_key, verify_api_key


def test_generated_keys_are_unique_and_long():
    first = generate_api_key()
    second = generate_api_key()
    assert first != second
    assert len(first) >= 40


def test_hash_is_deterministic_and_not_the_key():
    key = generate_api_key()
    assert hash_api_key(key) == hash_api_key(key)
    assert hash_api_key(key) != key
    assert len(hash_api_key(key)) == 64


def test_verify_api_key_matches_only_the_right_key():
    key = generate_api_key()
    digest = hash_api_key(key)
    assert verify_api_key(key, digest) is True
    assert verify_api_key(generate_api_key(), digest) is False


def test_verify_admin_key_is_exact():
    assert verify_admin_key("s3cret", "s3cret") is True
    assert verify_admin_key("s3cret", "other") is False
