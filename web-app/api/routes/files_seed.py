"""Initial demo filesystem for a freshly created project.

Extracted verbatim from the frontend's former ``MOCK_FILES``/``MOCK_CODE``
pair so the look-and-feel of an empty project stays the same after we
moved file storage server-side. When ``list_files`` sees a project with
zero rows, it inserts these so the user always has something to click on.

If you want blank projects instead, replace ``DEMO_FILES`` with ``[]``.
"""
from __future__ import annotations

# Order here becomes the insertion order; list_files sorts by path on read.
DEMO_FILES: list[tuple[str, str]] = [
    ("src/auth.py", '''"""JWT-based auth for the Task API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from flask import current_app, request

ALG = "HS256"
ACCESS_TTL = timedelta(minutes=15)


def issue_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + ACCESS_TTL,
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=ALG)


def verify_token(token: str) -> Optional[dict]:
    """Verify a JWT and return the claims dict, or None on failure."""
    try:
        return jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[ALG],
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def current_user() -> Optional[dict]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return verify_token(auth[7:])
'''),
    ("src/api.py", '''"""Task CRUD endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from .auth import current_user
from .models import Task, store
from .utils.validators import validate_task_payload

bp = Blueprint("api", __name__, url_prefix="/api/tasks")


@bp.get("")
def list_tasks():
    user = current_user()
    if not user:
        return {"error": "unauthorized"}, 401
    return jsonify([t.to_dict() for t in store.for_user(user["sub"])])


@bp.post("")
def create_task():
    user = current_user()
    if not user:
        return {"error": "unauthorized"}, 401
    body = request.get_json(silent=True) or {}
    err = validate_task_payload(body)
    if err:
        return {"error": err}, 400
    task = Task(owner_id=user["sub"], title=body["title"], done=False)
    store.add(task)
    return task.to_dict(), 201


@bp.delete("/<int:task_id>")
def delete_task(task_id: int):
    user = current_user()
    if not user:
        return {"error": "unauthorized"}, 401
    if not store.delete(task_id, owner_id=user["sub"]):
        return {"error": "not found"}, 404
    return "", 204
'''),
    ("src/models.py", '''"""In-memory Task store for the demo."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from itertools import count
from typing import Dict, List, Optional

_ids = count(1)


@dataclass
class Task:
    owner_id: str
    title: str
    done: bool = False
    id: int = field(default_factory=lambda: next(_ids))

    def to_dict(self) -> dict:
        return asdict(self)


class TaskStore:
    def __init__(self) -> None:
        self._by_id: Dict[int, Task] = {}

    def add(self, task: Task) -> None:
        self._by_id[task.id] = task

    def for_user(self, owner_id: str) -> List[Task]:
        return [t for t in self._by_id.values() if t.owner_id == owner_id]

    def delete(self, task_id: int, *, owner_id: str) -> bool:
        t = self._by_id.get(task_id)
        if t is None or t.owner_id != owner_id:
            return False
        del self._by_id[task_id]
        return True


store = TaskStore()
'''),
    ("src/utils/helpers.py", '''"""Small formatting helpers used across the API layer."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_iso() -> str:
    """RFC 3339 timestamp for the current moment."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))
'''),
    ("src/utils/validators.py", '''"""Payload validation for the Task API."""
from __future__ import annotations

from typing import Optional

MAX_TITLE_LEN = 200


def validate_task_payload(body: dict) -> Optional[str]:
    """Return an error string if invalid, else None."""
    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        return "title is required and must be a non-empty string"
    if len(title) > MAX_TITLE_LEN:
        return f"title exceeds {MAX_TITLE_LEN} chars"
    done = body.get("done", False)
    if not isinstance(done, bool):
        return "done must be a boolean"
    return None
'''),
    ("tests/test_auth.py", '''"""Auth tests — currently only happy-path; refresh token coverage TODO."""
from __future__ import annotations

import time

import pytest
from flask import Flask

from src.auth import issue_token, verify_token


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"
    with app.app_context():
        yield app


def test_issue_and_verify_roundtrip(app):
    token = issue_token(42, "a@b.com")
    claims = verify_token(token)
    assert claims["sub"] == "42"
    assert claims["email"] == "a@b.com"


def test_invalid_token_returns_none(app):
    assert verify_token("garbage") is None
'''),
    ("tests/test_api.py", '''"""Endpoint tests. Coverage is thin — expand this!"""
from __future__ import annotations

import pytest
from flask import Flask

from src.api import bp as api_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"
    app.register_blueprint(api_bp)
    with app.test_client() as c:
        yield c


def test_list_unauthorized(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 401
'''),
    ("README.md", '''# Task API — MPAC demo project

Tiny Flask-based task tracker used to exercise the Multi-Principal Agent
Coordination protocol. Humans and AI agents share the same repo; MPAC keeps
them from stepping on each other's toes via explicit intent announcements
and scope-overlap detection.

## Module map

```
src/
├── auth.py         # JWT issue / verify (no refresh tokens yet)
├── api.py          # Blueprint with /api/tasks CRUD
├── models.py       # In-memory Task dataclass + TaskStore
└── utils/
    ├── helpers.py      # clamp, utc_iso
    └── validators.py   # validate_task_payload

tests/
├── test_auth.py
└── test_api.py
```

## Known gaps (good targets for agent work)

- No refresh token flow in `auth.py`.
- `api.py` is missing `PUT /api/tasks/<id>` (update/toggle-done).
- `validators.py` doesn't validate `done` on partial updates.
- Test coverage in `test_api.py` is placeholder-only.
'''),
]
