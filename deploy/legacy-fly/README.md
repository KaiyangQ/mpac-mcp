# `deploy/legacy-fly/` — archived fly.io deployment artifacts

**Status: deprecated**. The MPAC web app used to run on fly.io as two
separate apps (`mpac-web-api` + `mpac-web-app`), plus an older hosted
MPAC coordinator (`mpac-demo`). On **2026-04-18** the fly.io trial
expired and everything was migrated to a single AWS Lightsail instance
— see `deploy/aws-lightsail/` for the current deployment.

These files are kept for:
* historical reference (how the fly deployment was set up)
* potential future use if we decide to offer multi-cloud deploy options
* paired Dockerfile history — the current `deploy/dockerfiles/api/Dockerfile`
  and `deploy/dockerfiles/app/Dockerfile` were forked from the fly
  versions; diffing against these archives shows exactly what changed

## Contents

| Path | What it is |
|---|---|
| `fly-coordinator/` | Hosted MPAC coordinator app on `mpac-demo.fly.dev`. Caddy + mpac-mcp-sidecar, multi-session + authenticated profile. Suspended (never destroyed) on fly. |
| `fly-webapi-toml/fly.toml` | fly app config for the FastAPI backend — `mpac-web-api.fly.dev`. |
| `fly-webapp-toml/fly.toml` | fly app config for the Next.js frontend — `mpac-web-app.fly.dev`. |
| `fly-webapi-toml/README.md` | original README from the fly-webapi directory. |
| `fly-webapp-toml/README.md` | original README from the fly-webapp directory. |
| `deploy-webapp.sh` | One-shot fly deploy script — created both apps, set secrets, generated 10 invite codes. Replaced by the AWS Lightsail runbook in `deploy/aws-lightsail/README.md`. |

## Do not run anything in this directory

The fly apps `mpac-web-api` and `mpac-web-app` were destroyed after
migration; `mpac-demo` coordinator is suspended. Running
`deploy-webapp.sh` would try to recreate all three, which either fails
on the expired trial or costs money on a billable account — and even
if it succeeded, you'd still need to also tear down AWS to avoid double
billing.

If you ever want to deploy on fly again: create a fresh `deploy/fly-*`
directory from scratch using these as a template; don't try to
resurrect this directory in-place.
