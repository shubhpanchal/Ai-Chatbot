"""Security and cryptographic utilities for HMAC-SHA-256 API key management."""

import hmac
import secrets
from hashlib import sha256


def generate_raw_api_key(prefix: str = "ak_dev") -> str:
    """Generate a secure, random raw API key with a readable prefix."""
    token = secrets.token_hex(24)
    return f"{prefix}_{token}"


def hash_api_key(raw_key: str, secret: str) -> str:
    """Compute HMAC-SHA-256 digest of a raw API key using a server-side secret."""
    if not secret:
        raise ValueError("API_KEY_SECRET must be configured and non-empty.")
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_key.encode("utf-8"),
        digestmod=sha256,
    ).hexdigest()


def verify_api_key(raw_key: str, hashed_key: str, secret: str) -> bool:
    """Verify raw API key against stored HMAC-SHA-256 hash using constant-time comparison."""
    computed_hash = hash_api_key(raw_key, secret)
    return hmac.compare_digest(computed_hash, hashed_key)
