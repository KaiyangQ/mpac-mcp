# `deploy/fly-webapp/` — Next.js frontend on fly.io

Serves the user-facing MPAC Web App at `https://mpac-web-app.fly.dev`.

Pairs with `deploy/fly-webapi/` (FastAPI backend, `https://mpac-web-api.fly.dev`)
and `deploy/fly-coordinator/` (older hosted MPAC coordinator — not used by
the web app's own in-process coordinator).

Don't deploy this directly — use the one-shot script:

```bash
./deploy/scripts/deploy-webapp.sh
```

It creates both fly apps, the backend volume, generates secrets (JWT,
Fernet BYOK, 10 invite codes), and deploys both containers in order.
