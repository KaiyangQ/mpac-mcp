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

Originally shipped 2026-04-19 (3-step paste). Heavily streamlined
2026-04-21 deep-night sprint: **one-line `bash <(curl ...)` bootstrap**
that server-side-renders a setup script, plus a PowerShell variant
for Windows with an OS toggle in the Modal. Bootstrap hardened 2026-04-22
morning to scan for Python 3.10+ (macOS system `/usr/bin/python3` is
3.9.6 and won't satisfy `mpac-mcp`'s `mcp` dependency) and auto-upgrade
old pip (< 23 doesn't know `--break-system-packages`).

Users route the in-browser AI chat through their **local Claude Code
subscription** instead of filling in an Anthropic API key. Zero cost
beyond the Claude Pro / Max they already have.

### Prerequisites (one-time, on the tester's laptop)

- **Node.js LTS** (the bootstrap script uses `npm install -g
  @anthropic-ai/claude-code`; it needs `npm` already on PATH)
- **Python ≥ 3.10** — bootstrap scans `python3.13 → 3.12 → 3.11 → 3.10`
  and falls back to `python3` only if that one ≥ 3.10. **macOS system
  `/usr/bin/python3` (3.9.6) won't work**; use `brew install python@3.12`
  or pyenv or python.org
- **Claude Pro or Max subscription** — the bootstrap runs `claude /login`
  in a subprocess if `~/.claude/sessions/` is empty (browser OAuth, one
  time only)

No Anthropic API key anywhere in the loop. `claude -p` reads session
credentials set by `claude /login`.

### Per-project connect flow (current — one line, ~20 s after prereqs)

1. Log into <https://mpac-web.duckdns.org>, open a project.
2. Click **"🤖 Connect Claude"** in the project header.
3. Modal auto-detects your OS from the user-agent (toggle if wrong) and
   shows the one-line command keyed to it:

   **macOS / Linux / WSL / Git Bash**:
   ```bash
   bash <(curl -fsSL 'https://mpac-web.duckdns.org/api/projects/<pid>/bootstrap.sh?token=<opaque-token>')
   ```

   **Windows PowerShell**:
   ```powershell
   iex (irm 'https://mpac-web.duckdns.org/api/projects/<pid>/bootstrap.ps1?token=<opaque-token>')
   ```

4. Copy, paste into a terminal, Enter. First run takes **1-3 minutes**
   (npm install, Claude login OAuth if needed, pip install mpac-mcp);
   subsequent runs are seconds. Modal status auto-flips to green
   **`● Connected`** and a 🤖 appears next to the user's name in the
   WHO'S WORKING panel.

5. Leave the `mpac-mcp-relay` process running in the foreground. The
   terminal "hangs" after install logs — that's correct, it's a
   long-lived relay. Don't close the window.

**What the bootstrap script does** (the reason we don't paste 4 commands
anymore):
1. Scan for `npm`; fail fast if missing
2. Scan for Python 3.10+ via `python3.13 → 3.10` ladder; fail fast if none
3. Upgrade old pip (< 23) so `--break-system-packages` fallback works
4. Install Claude Code CLI if missing (`npm install -g @anthropic-ai/claude-code`)
5. Run `claude /login` in a subprocess if not already logged in
6. `pip install mpac-mcp` with fallback ladder: plain → `--user` →
   `--break-system-packages` (covers venv, Linux system, macOS PEP 668)
7. `exec mpac-mcp-relay --project-url wss://... --token <opaque>`

> We use `bash <(curl ...)` not `curl | bash` on purpose —
> process-substitution preserves stdin as a TTY so `claude /login` can
> prompt interactively. A pipe would eat stdin.

### MCP tools Claude gets

**7 MPAC-aware tools** (`mpac-mcp >= 0.2.2`, the current PyPI version):

| Tool | What Claude can do |
|---|---|
| `list_project_files` | Discover what files exist in the shared project |
| `read_project_file(path)` | Read one file's content |
| `write_project_file(path, content)` | Overwrite or create a file (full content, not diffs) |
| `check_overlap(files)` | Ask "is anyone else already working on these files?" before announcing |
| `announce_intent(files, objective, symbols=[...])` | Claim an editing intent; optional `symbols` pins symbol-level precision (0.2.1+) so MPAC can tell if another agent's `save` conflicts with my `load` |
| `withdraw_intent(intent_id)` | Release the claim when done (or yielding) |
| `list_active_intents()` | **Poll what everyone else is doing right now** — new in 0.2.2, great as the first call Claude makes each task to build a global picture |

These operate on DB-backed shared files (not the tester's local
filesystem). Intents Claude announces appear in everyone else's
WHO'S WORKING panel; conflicts light up red cards in all connected
browsers.

### Stopping / switching / troubleshooting

- **Stop your relay**: `Ctrl+C` the running process. Claude's 🤖 goes
  offline in everyone's WHO'S WORKING within ~2 s.
- **Rotate your token**: reopening the Modal while a relay is already
  connected shows the existing command (we intentionally don't rotate
  to avoid killing a running relay). To force a new token, stop the
  relay first, then reopen.
- **Quota**: each user's chat messages consume THEIR OWN Claude Code
  subscription quota. Nobody shares a pool.

| Symptom | Fix |
|---|---|
| `bash: command not found: npm` | Install Node.js LTS: <https://nodejs.org/> |
| `No Python >= 3.10 found` | `brew install python@3.12` (mac) / `apt install python3.12` (Ubuntu 22+) / `winget install Python.Python.3.12` (Windows) |
| Browser-opened Claude login but tester closed it | Rerun the one-liner — `claude /login` will prompt again |
| Token expired / 401 / 403 | Close Modal, reopen "Connect Claude" for a fresh command |
| Terminal hanging after install logs | That's correct — relay is a long-lived foreground process. Don't close the window |
| Modal stays on "Waiting for relay..." forever | Check `sudo docker logs aws-lightsail-api-1 --tail 100` for a `ws /ws/relay/<pid>` line; if absent, relay never reached the server (network / token issue) |

### Fallback

If no relay is connected AND the user has a BYOK Anthropic key on file,
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
