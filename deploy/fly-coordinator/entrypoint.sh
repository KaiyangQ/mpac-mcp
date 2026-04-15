#!/bin/sh
# Start mpac-mcp-sidecar in the background, then exec Caddy as PID 1.
# If Caddy exits the container exits (fly restarts it). If the sidecar dies,
# Caddy will start returning 502 to reverse-proxied requests — we still
# surface that via container logs so fly's healthcheck / us can notice.

set -e

: "${MPAC_SESSION_ID:=demo-room}"
: "${MPAC_SIDECAR_PORT:=8766}"
: "${MPAC_WORKSPACE:=/data}"

if [ -z "${MPAC_TOKEN:-}" ]; then
    echo "[entrypoint] FATAL: MPAC_TOKEN is not set; refusing to start." >&2
    echo "[entrypoint] Run 'fly secrets set MPAC_TOKEN=<your-random-token>' first." >&2
    exit 1
fi

echo "[entrypoint] starting mpac-mcp-sidecar"
echo "[entrypoint]   bind       : 127.0.0.1:${MPAC_SIDECAR_PORT}"
echo "[entrypoint]   session_id : ${MPAC_SESSION_ID}"
echo "[entrypoint]   workspace  : ${MPAC_WORKSPACE}"

mpac-mcp-sidecar \
    --host 127.0.0.1 \
    --port "${MPAC_SIDECAR_PORT}" \
    --session-id "${MPAC_SESSION_ID}" \
    --workspace "${MPAC_WORKSPACE}" \
    --tls &

SIDECAR_PID=$!

# Give the sidecar a moment to bind before Caddy starts proxying.
sleep 1

if ! kill -0 "${SIDECAR_PID}" 2>/dev/null; then
    echo "[entrypoint] sidecar failed to start — aborting" >&2
    exit 1
fi

echo "[entrypoint] starting Caddy on :8080 (bearer auth + reverse proxy)"
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
