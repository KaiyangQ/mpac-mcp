"""Authentication module — has several known bugs for testing."""
import hashlib
import time
import hmac


# FIXED: Added token expiry validation
def validate_token(token: str) -> dict:
    """Validate a bearer token and return user info."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    header, payload, signature = parts

    expected_sig = hashlib.sha256(f"{header}.{payload}".encode()).hexdigest()[:16]
    if signature != expected_sig:
        raise ValueError("Invalid signature")

    # FIXED: Now checking if token is expired
    import json, base64
    data = json.loads(base64.b64decode(payload + "=="))
    
    if 'exp' in data and data['exp'] < time.time():
        raise ValueError("Token expired")
    
    return data


# FIXED: Timing side-channel — constant-time comparison
def authenticate(username: str, password: str, user_db: dict) -> bool:
    """Authenticate user against database."""
    # Always compute hash to prevent timing attacks
    input_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if username not in user_db:
        # Perform dummy comparison with constant timing
        dummy_hash = "0" * 64
        hmac.compare_digest(input_hash, dummy_hash)
        return False

    stored_hash = user_db[username]["password_hash"]
    
    # FIXED: Use constant-time comparison
    return hmac.compare_digest(stored_hash, input_hash)


def create_token(user_id: str, username: str, ttl_seconds: int = 3600) -> str:
    """Create a new bearer token."""
    import json, base64
    header = base64.b64encode(json.dumps({"alg": "sha256"}).encode()).decode().rstrip("=")
    payload = base64.b64encode(json.dumps({
        "user_id": user_id, "username": username,
        "exp": int(time.time()) + ttl_seconds,
    }).encode()).decode().rstrip("=")
    signature = hashlib.sha256(f"{header}.{payload}".encode()).hexdigest()[:16]
    return f"{header}.{payload}.{signature}"