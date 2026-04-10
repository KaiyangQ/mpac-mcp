"""Authentication module — minimal stateless token validation"""
import hashlib
import time
import json
import base64


def validate_token(token: str) -> dict:
    """Validate a bearer token and return user info."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    header, payload, signature = parts

    expected_sig = hashlib.sha256(f"{header}.{payload}".encode()).hexdigest()[:16]
    if signature != expected_sig:
        raise ValueError("Invalid signature")

    data = json.loads(base64.b64decode(payload + "=="))
    
    if data.get('exp', 0) < time.time():
        raise ValueError("Token expired")
    
    return data