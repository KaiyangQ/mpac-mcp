# MPAC Semi-Public Beta — access credentials

> **🔒 PRIVATE — do NOT share, do NOT paste into public channels, do NOT
> commit to `mpac-protocol`, `mpac-mcp`, or any other public repo.**
>
> This file lives only on the private `Agent_talking` repo's `main` branch.
> It contains plaintext credentials that give access to the hosted beta.

Hosted at:

| | URL |
|---|---|
| Frontend + Backend (single-origin) | <https://mpac-web.duckdns.org> |
| Infra | AWS Lightsail `$12/mo` instance, `us-west-2a` (Oregon) |
| TLS | Let's Encrypt via certbot (auto-renew) |
| DNS | DuckDNS (free subdomain, swap to a real domain anytime) |

Architecture: both Next.js and FastAPI run as Docker containers on one
Lightsail host behind nginx. `/api/*` and `/ws/*` route to FastAPI
(port 8001); everything else to Next.js (port 3000). No fly.io anymore.

---

## 🧪 Internal test accounts (4)

Seeded directly into `users` on `/var/mpac/data/mpac_web.db` — they
bypass the invite-code gate, so they don't consume any of the 10 beta
codes below. Same password across all four for convenience during
dogfooding.

| Display name | Email | Password |
|---|---|---|
| **Alice** | `alice@mpac.test` | `mpac-test-2026` |
| **Bob**   | `bob@mpac.test`   | `mpac-test-2026` |
| **Carol** | `carol@mpac.test` | `mpac-test-2026` |
| **Dave**  | `dave@mpac.test`  | `mpac-test-2026` |

Sign in at <https://mpac-web.duckdns.org/login> — **no invite code
needed** because these rows already exist.

### BYOK state

None of the four accounts has an Anthropic API key on file yet.
Until one is added via **Settings → Anthropic API key (BYOK)**, the
AI chat endpoint returns `HTTP 402` (UX: a "Add API key in Settings →"
banner appears in the chat pane). Presence / invite / conflict UI
keeps working without a key.

To share one key across all four: sign in as Alice, add your key in
Settings, then SSH to the Lightsail host and:

```bash
sudo sqlite3 /var/mpac/data/mpac_web.db "
  UPDATE users
     SET anthropic_api_key_encrypted = (
           SELECT anthropic_api_key_encrypted FROM users WHERE email='alice@mpac.test'
         )
   WHERE email IN ('bob@mpac.test','carol@mpac.test','dave@mpac.test');
"
```

Because `MPAC_WEB_ENCRYPTION_KEY` is shared across all users, the same
ciphertext decrypts identically for each account.

---

## 🎟 Single-use beta invite codes (10)

Seeded from `MPAC_WEB_INVITE_CODES` (in `/etc/mpac/api.env` on the
Lightsail host) into `signup_codes` on startup. Each code can be used
by **one** real (non-test) user to self-register at
<https://mpac-web.duckdns.org/register>. Once claimed, the row is marked
`used_by_id` / `used_at` and the code is burned — even if it's still in
the env var list.

| # | Invite link (click-to-register with code prefilled) |
|---|---|
| 1  | <https://mpac-web.duckdns.org/register?invite=mpac-beta-4j9fvg> |
| 2  | <https://mpac-web.duckdns.org/register?invite=mpac-beta-vzneutmv> |
| 3  | <https://mpac-web.duckdns.org/register?invite=mpac-beta-crsrgyd> |
| 4  | <https://mpac-web.duckdns.org/register?invite=mpac-beta-rsyi5ux> |
| 5  | <https://mpac-web.duckdns.org/register?invite=mpac-beta-sh9ql6dc> |
| 6  | <https://mpac-web.duckdns.org/register?invite=mpac-beta-5pq1zyc> |
| 7  | <https://mpac-web.duckdns.org/register?invite=mpac-beta-cdw9qie3> |
| 8  | <https://mpac-web.duckdns.org/register?invite=mpac-beta-dsnchglx> |
| 9  | <https://mpac-web.duckdns.org/register?invite=mpac-beta-sy8dmfc> |
| 10 | <https://mpac-web.duckdns.org/register?invite=mpac-beta-a6p2nx6> |

> The raw `mpac-beta-xxxx` string is also accepted if someone goes to
> `/register` manually and pastes the code.

### Checking which codes are still live

SSH into Lightsail:

```bash
ssh -i ~/Downloads/LightsailDefaultKey-us-west-2.pem ubuntu@184.32.168.112
sudo sqlite3 /var/mpac/data/mpac_web.db \
    'SELECT code, used_by_id, used_at FROM signup_codes ORDER BY id;'
```

### Rotating codes

Edit `/etc/mpac/api.env` on the instance, change
`MPAC_WEB_INVITE_CODES=...`, then restart the api container:

```bash
cd ~/Agent_talking
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml \
    --env-file /etc/mpac/compose.env restart api
```

API startup re-reads the CSV and inserts new codes into `signup_codes`.
Existing rows (including used ones) are untouched — no code ever
resurrects itself.

---

## 🔑 Platform secrets (on Lightsail, not here)

These live in `/etc/mpac/api.env` on the Lightsail host (root:root
0640) and `/etc/mpac/compose.env`. Never committed anywhere.

| Name | What it guards |
|---|---|
| `MPAC_WEB_JWT_SECRET` | Signs user JWTs; rotating invalidates all logins |
| `MPAC_WEB_ENCRYPTION_KEY` | Fernet key for BYOK Anthropic keys; rotating forgets every stored key |
| `MPAC_WEB_INVITE_CODES` | CSV that seeds `signup_codes` on startup |
| `MPAC_WEB_ALLOWED_ORIGINS` | CORS + WebSocket origin allowlist (https only) |
| `NEXT_PUBLIC_API_URL` | Baked into Next bundle at build time (`compose.env`) |

Rotating either `JWT_SECRET` or `ENCRYPTION_KEY` requires every user
to re-login / re-add their BYOK key respectively — only do this if one
leaks. `INVITE_CODES` can be rotated freely without affecting users.

---

## 🚚 Day-2 ops quickref

| Task | Command (on Lightsail host) |
|---|---|
| Pull new code + rebuild | `cd ~/Agent_talking && git pull && sudo docker compose -f deploy/aws-lightsail/docker-compose.yml --env-file /etc/mpac/compose.env up -d --build` |
| Tail api logs | `sudo docker compose -f deploy/aws-lightsail/docker-compose.yml logs -f api` |
| Tail app logs | `sudo docker compose -f deploy/aws-lightsail/docker-compose.yml logs -f app` |
| nginx access log | `sudo tail -f /var/log/nginx/access.log` |
| Check certbot next renewal | `sudo certbot certificates` |
| SQLite dump backup | `sudo sqlite3 /var/mpac/data/mpac_web.db ".backup /tmp/backup.db"` |
