# `deploy/fly-webapi/` — FastAPI backend on fly.io

Serves the MPAC Web App API + in-process MPAC coordinator at
`https://mpac-web-api.fly.dev`.

Pairs with `deploy/fly-webapp/` (Next.js frontend) and
`deploy/fly-coordinator/` (older standalone MPAC coordinator — not used
by this app; we run the coordinator in-process inside the FastAPI worker).

Don't deploy this directly — use the one-shot script:

```bash
./deploy/scripts/deploy-webapp.sh
```

## Runtime layout

- `internal_port = 8001` — Uvicorn listens here, fly's edge proxy forwards `:443` → `:8001`.
- `[[mounts]] webapi_data → /data` — persistent SQLite DB (`/data/mpac_web.db`).
- `auto_stop_machines = "off"` — the in-process coordinator keeps live
  WebSocket sessions; cold starts would drop them.
- `--workers 1` — coordinator state lives in module globals (`mpac_bridge.registry`),
  so more workers would desynchronize sessions. Scale vertically for now.

## Secrets (set by `deploy-webapp.sh`)

- `MPAC_WEB_JWT_SECRET`  — 48-byte urlsafe token signing secret.
- `MPAC_WEB_ENCRYPTION_KEY` — Fernet key for per-user BYOK Anthropic keys.
- `MPAC_WEB_INVITE_CODES` — CSV of 10 signup codes, seeded into DB on startup.
- `MPAC_WEB_ALLOWED_ORIGINS` — CORS allowlist (just the frontend URL for now).

See `api/config.py` for how each is read.
