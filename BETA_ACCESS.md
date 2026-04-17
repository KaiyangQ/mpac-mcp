# MPAC Semi-Public Beta — access credentials

> **🔒 PRIVATE — do NOT share, do NOT paste into public channels, do NOT
> commit to `mpac-protocol`, `mpac-mcp`, or any other public repo.**
>
> This file lives only on the private `Agent_talking` repo's `main` branch.
> It contains plaintext credentials that give access to the hosted beta.

Hosted at:

| | URL |
|---|---|
| Frontend | <https://mpac-web-app.fly.dev> |
| Backend  | <https://mpac-web-api.fly.dev> |

---

## 🧪 Internal test accounts (4)

Seeded directly into `users` on the fly.io SQLite volume — they bypass
the invite-code gate, so they don't consume any of the 10 beta codes
below. Same password across all four for convenience during dogfooding.

| Display name | Email | Password |
|---|---|---|
| **Alice** | `alice@mpac.test` | `mpac-test-2026` |
| **Bob**   | `bob@mpac.test`   | `mpac-test-2026` |
| **Carol** | `carol@mpac.test` | `mpac-test-2026` |
| **Dave**  | `dave@mpac.test`  | `mpac-test-2026` |

Sign in at <https://mpac-web-app.fly.dev/login> — **no invite code
needed** because these rows already exist.

### BYOK state

None of the four accounts has an Anthropic API key on file yet.
Until one is added via **Settings → Anthropic API key (BYOK)**, the
AI chat endpoint returns `HTTP 402` (UX: a "Add API key in Settings →"
banner appears in the chat pane). Presence / invite / conflict UI
keeps working without a key.

To share one key across all four: sign in as Alice, add your key in
Settings, then ask Claude to `UPDATE users SET
anthropic_api_key_encrypted = (SELECT ... FROM alice) WHERE email IN
(bob, carol, dave)` over `fly ssh`. Because `MPAC_WEB_ENCRYPTION_KEY`
is shared, the ciphertext decrypts identically for every user.

---

## 🎟 Single-use beta invite codes (10)

Seeded from `MPAC_WEB_INVITE_CODES` on startup into `signup_codes`.
Each code can be used by **one** real (non-test) user to self-register at
<https://mpac-web-app.fly.dev/register>. Once claimed, the row is marked
`used_by_id` / `used_at` and the code is burned — even if it's still in
the env var list.

| # | Invite link (click-to-register with code prefilled) |
|---|---|
| 1  | <https://mpac-web-app.fly.dev/register?invite=mpac-beta-4j9fvg> |
| 2  | <https://mpac-web-app.fly.dev/register?invite=mpac-beta-vzneutmv> |
| 3  | <https://mpac-web-app.fly.dev/register?invite=mpac-beta-crsrgyd> |
| 4  | <https://mpac-web-app.fly.dev/register?invite=mpac-beta-rsyi5ux> |
| 5  | <https://mpac-web-app.fly.dev/register?invite=mpac-beta-sh9ql6dc> |
| 6  | <https://mpac-web-app.fly.dev/register?invite=mpac-beta-5pq1zyc> |
| 7  | <https://mpac-web-app.fly.dev/register?invite=mpac-beta-cdw9qie3> |
| 8  | <https://mpac-web-app.fly.dev/register?invite=mpac-beta-dsnchglx> |
| 9  | <https://mpac-web-app.fly.dev/register?invite=mpac-beta-sy8dmfc> |
| 10 | <https://mpac-web-app.fly.dev/register?invite=mpac-beta-a6p2nx6> |

> The raw `mpac-beta-xxxx` string is also accepted if someone goes to
> `/register` manually and pastes the code.

### Checking which codes are still live

From the repo root:

```bash
fly ssh console --app mpac-web-api -C \
  "python3 -c 'import sqlite3; c=sqlite3.connect(\"/data/mpac_web.db\"); \
   [print(r) for r in c.execute(\"SELECT code, used_by_id, used_at FROM signup_codes ORDER BY id\").fetchall()]'"
```

### Rotating codes

If a code leaks or you want to issue a fresh batch, re-run the deploy
script — it generates new codes if `deploy/scripts/.invite-codes.txt`
is absent, or reuses the existing list if present. Used rows are
preserved by the `SignupCode` seed logic in `api/main.py`:

```bash
rm deploy/scripts/.invite-codes.txt
./deploy/scripts/deploy-webapp.sh --skip-deploy   # only updates secrets
fly deploy --app mpac-web-api                     # apply staged secrets
```

---

## 🔑 Platform secrets (fly.io, not here)

These are set via `fly secrets set` and only exist on the API machine —
**never committed anywhere**. If you lose them you can rotate via the
deploy script (`JWT_SECRET` / `ENCRYPTION_KEY` regen on every run).

| Name | What it guards |
|---|---|
| `MPAC_WEB_JWT_SECRET` | Signs user JWTs; rotating invalidates all logins |
| `MPAC_WEB_ENCRYPTION_KEY` | Fernet key for BYOK Anthropic keys; rotating forgets every stored key |
| `MPAC_WEB_INVITE_CODES` | CSV that seeds `signup_codes` on startup |
| `MPAC_WEB_ALLOWED_ORIGINS` | CORS + WebSocket origin allowlist |
