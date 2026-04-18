# `deploy/dockerfiles/api/` — FastAPI backend Dockerfile

Builds `mpac-web-api:local` — a Python 3.12-slim image that serves the
FastAPI app from `web-app/api/` on port 8001 via uvicorn.

Consumed by `deploy/aws-lightsail/docker-compose.yml` — you usually
don't invoke docker build directly; let compose orchestrate.

Build context must be the repo root (so the Dockerfile can see both
`web-app/api/` and its `requirements.txt`).

If we move away from AWS Lightsail to another host, this Dockerfile
stays the same — only the compose file / runtime config changes.
