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

## 🤖 Connect Claude (local-bridge mode, no API key needed)

Shipped 2026-04-19. Users on the beta can now route the in-browser AI
chat through their **local Claude Code subscription** instead of filling
in an Anthropic API key. Zero cost to them beyond the Claude Pro / Max
subscription they already have.

### One-time laptop setup

```bash
# 1. Claude Code CLI
npm install -g @anthropic-ai/claude-code

# 2. Bind the subscription to this machine (OAuth in browser)
claude /login

# 3. Install the MPAC bridge package
pip install mpac-mcp   # needs >= 0.2.0 for the `mpac-mcp-relay` command
```

No API key anywhere in the loop. `claude -p` reads
`~/.claude/sessions/` credential files which are set by step 2.

### Per-project connect flow

1. Log into <https://mpac-web.duckdns.org>, open a project.
2. Click **"Connect Claude"** in the header (to the left of Invite).
3. The modal shows a ready-to-run command like:
   ```bash
   mpac-mcp-relay \
     --project-url wss://mpac-web.duckdns.org/ws/relay/<project_id> \
     --token <opaque-44-char-token>
   ```
4. Paste into a terminal and run. The modal status strip flips to
   green **`● Connected`** within ~2 s.
5. Leave the `mpac-mcp-relay` process running in the background. The
   in-browser AI chat now routes to Claude running on that laptop.

Inside the chat, Claude has six MPAC-aware tools:
`list_project_files`, `read_project_file`, `write_project_file`,
`check_overlap`, `announce_intent`, `withdraw_intent`. It uses them
to actually read and edit the shared project files (not your local
filesystem), and its intents are visible to everyone else in the
session's WHO'S WORKING panel.

### Stopping / switching

- **Stop your relay:** `Ctrl+C` the running process. Claude's avatar
  goes offline in the session within seconds.
- **Rotate your token:** reopening the modal while a relay is already
  connected simply shows the existing command again (we intentionally
  don't rotate to avoid killing the running relay). To force a new
  token, stop the relay first, then reopen the modal.
- **Quota:** each user's chat messages consume THEIR OWN Claude Code
  subscription quota. Nobody shares a pool.

### Fallback

If no relay is connected and the user has a BYOK Anthropic key on file,
`/api/chat` falls back to the old API-key path. If neither is set, the
chat returns `HTTP 402` with a hint to either Connect Claude or add a
key.

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

## 🚚 Day-2 ops — updating the live site

The Lightsail instance tracks the `deploy` branch (a thin-slice of main,
only the files needed to build and run). To ship a change:

### From your laptop — promote main to deploy

```bash
# After committing whatever you want to release to main:
./deploy/scripts/sync-deploy-branch.sh
```

The script:
1. Archives the current `origin/deploy` as `deploy-archive-YYYY-MM-DD`
   (on GitHub too, so rollback is always possible).
2. Builds a fresh orphan commit containing only the whitelist
   (`deploy/` + `web-app/` + 4 root files) from `main`'s current HEAD.
3. Force-pushes that commit to `origin/deploy`.

### On Lightsail — pull the new snapshot

```bash
ssh -i ~/Downloads/LightsailDefaultKey-us-west-2.pem ubuntu@184.32.168.112
cd ~/Agent_talking
git fetch origin deploy
git reset --hard origin/deploy        # NOT `git pull` — deploy force-pushes
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml \
    --env-file /etc/mpac/compose.env up -d --build
```

`docker compose up -d --build` rebuilds only the services whose image
source changed, and recreates the corresponding container. Running
sessions on the OTHER service keep going.

### Rollback (if a release breaks the site)

```bash
# From your laptop:
git push origin deploy-archive-2026-04-17:deploy --force
# Then on Lightsail, same fetch + reset + compose up as above.
```

### Other ops

| Task | Command (on Lightsail host) |
|---|---|
| Tail api logs | `sudo docker compose -f deploy/aws-lightsail/docker-compose.yml logs -f api` |
| Tail app logs | `sudo docker compose -f deploy/aws-lightsail/docker-compose.yml logs -f app` |
| Tail nginx access log | `sudo tail -f /var/log/nginx/access.log` |
| Check certbot next renewal | `sudo certbot certificates` |
| SQLite one-shot backup | `sudo sqlite3 /var/mpac/data/mpac_web.db ".backup /tmp/backup.db"` |
| List invite codes on disk | `sudo sqlite3 /var/mpac/data/mpac_web.db 'SELECT code, used_by_id FROM signup_codes'` |

## 🗂 Branch layout (private `Agent_talking`)

| Branch | What it contains | Lives where |
|---|---|---|
| `main` | Full development history — daily reports, version history, docs, ref-impl, mpac-package/mpac-mcp source, web-app, everything. | Local laptop + private GitHub |
| `deploy` | Thin-slice of main: `deploy/ + web-app/ + 4 root files`. No dev docs, no mpac-* source. Force-pushed by `sync-deploy-branch.sh` every time a release is cut. | Private GitHub + Lightsail (`/home/ubuntu/Agent_talking/`) |
| `deploy-archive-YYYY-MM-DD` | Snapshot of `deploy` from before the last sync, kept for rollback. | Private GitHub (no active clones) |
| `opensource` / `opensource-mcp` | Thin-slices published as `mpac` / `mpac-mcp` on PyPI — unrelated to the web app. | Private GitHub → mirrored to public `mpac-protocol` / `mpac-mcp` repos |

`BETA_ACCESS.md`, `daily_reports/`, `deploy/scripts/.invite-codes.txt`
etc. live **only on `main`** — they never leak to `deploy` (thin-slice
whitelist excludes them) or to the public PyPI branches.
