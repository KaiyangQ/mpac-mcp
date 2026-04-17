"""End-to-end smoke test for the web-app FastAPI backend.

Exercises the full happy-path: register 2 users → owner creates project →
owner creates invite → invitee accepts → both can fetch their MPAC tokens →
owner can see the project in their list.

Run against a live server: ``python -m api.smoke [base_url]``.
Default base_url: http://127.0.0.1:8001
"""
from __future__ import annotations
import json
import sys
import urllib.request
import urllib.error


def call(method: str, url: str, body: dict | None = None, token: str | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body_s = e.read().decode()
        raise AssertionError(f"{method} {url} → {e.code}: {body_s}") from None


def check(label: str, cond: bool, detail: str = "") -> None:
    mark = "\033[32m✅\033[0m" if cond else "\033[31m❌\033[0m"
    print(f"  {mark} {label}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        raise SystemExit(1)


def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"
    print(f"Running smoke against {base}\n")

    # ── 1. Register Alice + Bob ───────────────────────────
    print("1. Register two users")
    alice = call("POST", f"{base}/api/register", {
        "email": "alice@test.com", "password": "pw-alice-123", "display_name": "Alice",
    })
    check("alice registered", alice["email"] == "alice@test.com", f"user_id={alice['user_id']}")
    bob = call("POST", f"{base}/api/register", {
        "email": "bob@test.com", "password": "pw-bob-123", "display_name": "Bob",
    })
    check("bob registered", bob["email"] == "bob@test.com", f"user_id={bob['user_id']}")

    # ── 2. Duplicate registration rejected ────────────────
    print("\n2. Duplicate email rejected")
    try:
        call("POST", f"{base}/api/register", {
            "email": "alice@test.com", "password": "x", "display_name": "Imposter",
        })
        check("duplicate rejected", False, "unexpected 200")
    except AssertionError as e:
        check("duplicate rejected", "400" in str(e), "HTTP 400 on duplicate")

    # ── 3. Login round-trip ───────────────────────────────
    print("\n3. Login")
    alice_login = call("POST", f"{base}/api/login", {
        "email": "alice@test.com", "password": "pw-alice-123",
    })
    check("alice login ok", bool(alice_login["token"]))
    try:
        call("POST", f"{base}/api/login", {
            "email": "alice@test.com", "password": "wrong",
        })
        check("wrong password rejected", False, "unexpected 200")
    except AssertionError as e:
        check("wrong password rejected", "401" in str(e), "HTTP 401")

    # ── 4. /me (JWT header actually read) ─────────────────
    print("\n4. /me with Authorization header")
    me = call("GET", f"{base}/api/me", token=alice["token"])
    check("/me returns Alice", me["email"] == "alice@test.com")
    try:
        call("GET", f"{base}/api/me")
        check("missing header → 401", False, "unexpected 200")
    except AssertionError as e:
        check("missing header → 401", "401" in str(e))
    try:
        call("GET", f"{base}/api/me", token="garbage.jwt.token")
        check("bad JWT → 401", False, "unexpected 200")
    except AssertionError as e:
        check("bad JWT → 401", "401" in str(e))

    # ── 5. Alice creates a project ────────────────────────
    print("\n5. Alice creates project")
    project = call("POST", f"{base}/api/projects", {"name": "proj-alpha"}, token=alice["token"])
    check("project created", project["name"] == "proj-alpha", f"id={project['id']} sid={project['session_id']}")
    check("session_id format", project["session_id"].startswith("proj-"))

    # ── 6. Alice gets her MPAC token for the project ──────
    print("\n6. Alice gets MPAC token")
    alice_mpac = call("GET", f"{base}/api/projects/{project['id']}/token", token=alice["token"])
    check("owner token exists", bool(alice_mpac["token_value"]))
    check("owner role", "owner" in alice_mpac["roles"], f"roles={alice_mpac['roles']}")

    # ── 7. Alice lists her projects ───────────────────────
    print("\n7. Alice lists projects")
    alice_list = call("GET", f"{base}/api/projects", token=alice["token"])
    check("alice sees 1 project", len(alice_list["projects"]) == 1)

    # ── 8. Bob initially sees no projects ─────────────────
    print("\n8. Bob sees 0 projects before invite")
    bob_list = call("GET", f"{base}/api/projects", token=bob["token"])
    check("bob sees 0 projects", len(bob_list["projects"]) == 0)

    # ── 9. Bob cannot peek at Alice's project directly ────
    print("\n9. Non-member cannot fetch token")
    try:
        call("GET", f"{base}/api/projects/{project['id']}/token", token=bob["token"])
        check("bob token → 404", False, "unexpected 200")
    except AssertionError as e:
        check("bob token → 404", "404" in str(e))

    # ── 10. Bob cannot create an invite (not the owner) ──
    print("\n10. Non-owner cannot create invite")
    try:
        call("POST", f"{base}/api/projects/{project['id']}/invite", {"roles": ["contributor"]},
             token=bob["token"])
        check("bob invite → 403", False, "unexpected 200")
    except AssertionError as e:
        check("bob invite → 403", "403" in str(e))

    # ── 11. Alice creates an invite ──────────────────────
    print("\n11. Alice creates invite")
    invite = call("POST", f"{base}/api/projects/{project['id']}/invite",
                  {"roles": ["contributor"]}, token=alice["token"])
    check("invite created", bool(invite["invite_code"]))
    check("invite carries session_id", invite["session_id"] == project["session_id"])

    # ── 12. Public invite preview (no auth) ──────────────
    print("\n12. Invite preview is public (no auth)")
    preview = call("GET", f"{base}/api/invites/{invite['invite_code']}")
    check("preview project name", preview["project_name"] == "proj-alpha")
    check("preview invited_by", preview["invited_by"] == "Alice")
    check("preview not used", preview["used"] is False)

    # ── 13. Bob accepts the invite ────────────────────────
    print("\n13. Bob accepts")
    bob_token = call("POST", f"{base}/api/invites/accept",
                     {"invite_code": invite["invite_code"]}, token=bob["token"])
    check("bob got token", bool(bob_token["token_value"]))
    check("bob's session_id matches", bob_token["session_id"] == project["session_id"])
    check("bob has contributor role", "contributor" in bob_token["roles"])
    check("alice and bob have DIFFERENT mpac tokens",
          alice_mpac["token_value"] != bob_token["token_value"])

    # ── 14. Invite can't be reused by a third party ──────
    print("\n14. Invite can't be reused")
    charlie = call("POST", f"{base}/api/register", {
        "email": "charlie@test.com", "password": "pw-c-123", "display_name": "Charlie",
    })
    try:
        call("POST", f"{base}/api/invites/accept",
             {"invite_code": invite["invite_code"]}, token=charlie["token"])
        check("reuse → 404", False, "unexpected 200")
    except AssertionError as e:
        check("reuse → 404", "404" in str(e))

    # ── 15. Bob now sees the project ─────────────────────
    print("\n15. Bob's project list has 1 entry")
    bob_list = call("GET", f"{base}/api/projects", token=bob["token"])
    check("bob sees 1 project", len(bob_list["projects"]) == 1)
    check("same project", bob_list["projects"][0]["id"] == project["id"])

    # ── 16. Bob can fetch project metadata ───────────────
    print("\n16. Bob can GET /projects/{id}")
    bob_project = call("GET", f"{base}/api/projects/{project['id']}", token=bob["token"])
    check("bob sees project name", bob_project["name"] == "proj-alpha")

    # ── 17. Bob's MPAC token is stable ───────────────────
    print("\n17. Bob's MPAC token retrieval is idempotent")
    bob_mpac2 = call("GET", f"{base}/api/projects/{project['id']}/token", token=bob["token"])
    check("same token on second GET", bob_mpac2["token_value"] == bob_token["token_value"])

    print("\n\033[32mAll checks passed ✓\033[0m")


if __name__ == "__main__":
    main()
