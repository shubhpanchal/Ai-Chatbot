"""Unit tests for cryptographic security and HMAC-SHA-256 utilities."""

import pytest

from app.core.security import generate_raw_api_key, hash_api_key, verify_api_key


def test_generate_raw_api_key() -> None:
    """Test raw API key format and randomness."""
    key1 = generate_raw_api_key()
    key2 = generate_raw_api_key()

    assert key1.startswith("ak_dev_")
    assert len(key1) > 40
    assert key1 != key2


def test_hash_api_key_deterministic() -> None:
    """Test HMAC hashing is deterministic for identical key and secret."""
    raw_key = "ak_dev_1234567890abcdef12345678"
    secret = "test-secret-key-for-unit-testing"

    hash1 = hash_api_key(raw_key, secret)
    hash2 = hash_api_key(raw_key, secret)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex digest length


def test_hash_api_key_different_secrets() -> None:
    """Test different secrets produce distinct digests."""
    raw_key = "ak_dev_1234567890abcdef12345678"
    hash1 = hash_api_key(raw_key, "secret-a")
    hash2 = hash_api_key(raw_key, "secret-b")

    assert hash1 != hash2


def test_verify_api_key() -> None:
    """Test constant-time API key verification."""
    raw_key = generate_raw_api_key("ak_test")
    secret = "production-pepper-secret-32-chars"
    key_hash = hash_api_key(raw_key, secret)

    # Valid key and secret
    assert verify_api_key(raw_key, key_hash, secret) is True

    # Invalid raw key
    assert verify_api_key("ak_test_wrong_token_1234", key_hash, secret) is False

    # Invalid secret
    assert verify_api_key(raw_key, key_hash, "wrong-secret") is False


def test_hash_api_key_empty_secret_raises() -> None:
    """Test that empty secret raises ValueError."""
    with pytest.raises(ValueError, match="API_KEY_SECRET must be configured"):
        hash_api_key("ak_test_123", "")
