#!/bin/sh
# Start mpac-mcp-sidecar in multi_session + authenticated profile mode,
# then exec Caddy as PID 1 for the HTTP/WebSocket edge.
#
# Auth model (single layer, option 2b from the 2026-04-15 design):
#   - Caddy does NOT check the Authorization header; it only filters by
#     URL path shape (/session/*) and reverse-proxies to the sidecar.
#   - The sidecar runs with security_profile=authenticated and loads a
#     credential_verifier from MPAC_TOKEN_TABLE (a JSON env var). Each
#     token is bound to specific session ids; cross-session access is
#     rejected at the protocol layer with CREDENTIAL_REJECTED.

set -e

: "${MPAC_SIDECAR_PORT:=8766}"

if [ -z "${MPAC_TOKEN_TABLE:-}" ]; then
    echo "[entrypoint] FATAL: MPAC_TOKEN_TABLE is not set; refusing to start." >&2
    echo "[entrypoint] Run 'fly secrets set MPAC_TOKEN_TABLE=<json>' first." >&2
    echo "[entrypoint] Expected format:" >&2
    echo '  {"<token>": {"allowed_sessions": ["proj-alpha"], "roles": ["contributor"]}}' >&2
    exit 1
fi

echo "[entrypoint] starting mpac-mcp-sidecar (multi_session + authenticated)"
echo "[entrypoint]   bind             : 127.0.0.1:${MPAC_SIDECAR_PORT}"
echo "[entrypoint]   mode             : multi_session (sessions from /session/<id>)"
echo "[entrypoint]   security_profile : authenticated (verifier from MPAC_TOKEN_TABLE)"

mpac-mcp-sidecar \
    --multi-session \
    --host 127.0.0.1 \
    --port "${MPAC_SIDECAR_PORT}" \
    --tls &

SIDECAR_PID=$!

# Give the sidecar a moment to bind before Caddy starts proxying.
sleep 1

if ! kill -0 "${SIDECAR_PID}" 2>/dev/null; then
    echo "[entrypoint] sidecar failed to start — aborting" >&2
    exit 1
fi

echo "[entrypoint] starting Caddy on :8080 (reverse proxy only; auth at protocol layer)"
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
