# Hosted MPAC coordinator image for fly.io
#
# Layout:
#   PID 1       : Caddy (listens on :8080, terminates bearer-token auth,
#                 reverse-proxies WebSocket traffic to the sidecar)
#   background  : mpac-mcp-sidecar (listens on 127.0.0.1:8766, inside the
#                 container only — never exposed directly)
#
# fly.io's built-in proxy terminates TLS for *.fly.dev and forwards plain
# HTTP to internal_port 8080, so Caddy here does NOT do TLS itself.

FROM python:3.12-slim

# --- Install Caddy from its official apt repo ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl gnupg ca-certificates \
        debian-keyring debian-archive-keyring apt-transport-https && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        | tee /etc/apt/sources.list.d/caddy-stable.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends caddy && \
    apt-get purge -y --auto-remove curl gnupg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Install mpac (protocol core) + mpac-mcp (bridge) from local source ---
# Build context is the repo root (see fly.toml / `fly deploy --dockerfile` docs).
# We install mpac-package first so that mpac-mcp's `mpac>=0.1.0` dep is
# satisfied from the local tree and pip does not reach for PyPI.
COPY mpac-package/ ./mpac-package/
COPY mpac-mcp/     ./mpac-mcp/
RUN pip install --no-cache-dir ./mpac-package ./mpac-mcp

# --- Caddy config + entrypoint shim ---
COPY deploy/fly-coordinator/Caddyfile   /etc/caddy/Caddyfile
COPY deploy/fly-coordinator/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Workspace volume mountpoint (fly.io volume is mounted here via [mounts])
RUN mkdir -p /data

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
