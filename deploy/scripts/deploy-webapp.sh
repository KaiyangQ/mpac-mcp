#!/usr/bin/env bash
# deploy-webapp.sh — one-shot deploy of the MPAC Web App (semi-public beta).
#
# Idempotent: safe to re-run. Creates fly apps + volume + secrets + deploys
# both the FastAPI backend (mpac-web-api) and the Next.js frontend
# (mpac-web-app). Prints the 10 invite codes on first-run; on subsequent
# runs reads them from `deploy/scripts/.invite-codes.txt` so you can share
# the same codes again.
#
# Prereqs:
#   - `fly auth login` (already done; account: happylifeqqq@gmail.com)
#   - python3 on PATH (for generating secrets)
#
# Usage:
#     ./deploy/scripts/deploy-webapp.sh
#
# Flags:
#     --skip-deploy    Only create apps / secrets, don't deploy (useful for
#                      rotating a secret without a redeploy).

set -euo pipefail

# ── Config ──
API_APP="mpac-web-api"
APP_APP="mpac-web-app"
REGION="dfw"
VOLUME_NAME="webapi_data"
VOLUME_SIZE_GB=1
INVITE_COUNT=10

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SECRETS_DIR="$REPO_ROOT/deploy/scripts"
INVITES_FILE="$SECRETS_DIR/.invite-codes.txt"

# ── Helpers ──
log()  { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[deploy]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[deploy]\033[0m %s\n' "$*" >&2; exit 1; }

command -v fly      >/dev/null || die "fly CLI not found; install from https://fly.io/docs/hands-on/install-flyctl/"
command -v python3  >/dev/null || die "python3 required for secret generation"

SKIP_DEPLOY=0
for arg in "$@"; do
  case "$arg" in
    --skip-deploy) SKIP_DEPLOY=1 ;;
    *) die "unknown flag: $arg" ;;
  esac
done

# ── 1. Ensure both apps exist ──
ensure_app() {
  local app="$1"
  if fly apps list --json 2>/dev/null | python3 -c "
import json, sys
want = sys.argv[1]
apps = json.load(sys.stdin)
sys.exit(0 if any(a.get('Name') == want or a.get('name') == want for a in apps) else 1)
" "$app"; then
    log "app '$app' already exists"
  else
    log "creating app '$app'"
    fly apps create "$app" --org personal
  fi
}
ensure_app "$API_APP"
ensure_app "$APP_APP"

# ── 2. Ensure the API's persistent volume exists ──
if fly volumes list --app "$API_APP" 2>/dev/null | grep -q "$VOLUME_NAME"; then
  log "volume '$VOLUME_NAME' already exists on '$API_APP'"
else
  log "creating ${VOLUME_SIZE_GB}GB volume '$VOLUME_NAME' on '$API_APP' in $REGION"
  fly volumes create "$VOLUME_NAME" \
    --region "$REGION" --size "$VOLUME_SIZE_GB" --app "$API_APP" --yes
fi

# ── 3. Invite codes ──
INVITE_CODES=()
if [[ -f "$INVITES_FILE" ]]; then
  log "reusing existing invite codes from $INVITES_FILE"
  # bash 3.2 compatible: avoid `mapfile` (bash 4+).
  while IFS= read -r line; do
    [[ -n "$line" ]] && INVITE_CODES+=("$line")
  done < "$INVITES_FILE"
else
  log "generating $INVITE_COUNT fresh invite codes"
  for i in $(seq 1 "$INVITE_COUNT"); do
    code="mpac-beta-$(python3 -c 'import secrets; print(secrets.token_urlsafe(6).lower().replace("_","").replace("-",""))' | cut -c1-8)"
    INVITE_CODES+=("$code")
  done
  mkdir -p "$SECRETS_DIR"
  printf '%s\n' "${INVITE_CODES[@]}" > "$INVITES_FILE"
  chmod 600 "$INVITES_FILE"
fi
INVITES_CSV=$(IFS=','; echo "${INVITE_CODES[*]}")

# ── 4. Gen platform secrets (JWT + Fernet) ──
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' 2>/dev/null \
  || python3 -c 'import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())')

# ── 5. Wire backend secrets ──
log "setting secrets on '$API_APP'"
fly secrets set \
  MPAC_WEB_JWT_SECRET="$JWT_SECRET" \
  MPAC_WEB_ENCRYPTION_KEY="$ENCRYPTION_KEY" \
  MPAC_WEB_INVITE_CODES="$INVITES_CSV" \
  MPAC_WEB_ALLOWED_ORIGINS="https://$APP_APP.fly.dev" \
  --app "$API_APP" --stage

# ── 6. Deploy ──
if [[ "$SKIP_DEPLOY" -eq 1 ]]; then
  log "--skip-deploy set; stopping before fly deploy. Run \`fly deploy --app $API_APP\` manually to apply staged secrets."
  exit 0
fi

log "deploying FastAPI backend → https://$API_APP.fly.dev"
cd "$REPO_ROOT"
fly deploy \
  --config  "deploy/fly-webapi/fly.toml" \
  --dockerfile "deploy/fly-webapi/Dockerfile" \
  --app "$API_APP" \
  --yes

log "deploying Next.js frontend → https://$APP_APP.fly.dev"
fly deploy \
  --config  "deploy/fly-webapp/fly.toml" \
  --dockerfile "deploy/fly-webapp/Dockerfile" \
  --app "$APP_APP" \
  --build-arg "NEXT_PUBLIC_API_URL=https://$API_APP.fly.dev" \
  --yes

# ── 7. Print the codes for sharing ──
echo
log "✅ deploy complete"
echo "    Frontend:  https://$APP_APP.fly.dev"
echo "    Backend:   https://$API_APP.fly.dev"
echo
echo "Invite codes (each single-use) — saved to $INVITES_FILE:"
for code in "${INVITE_CODES[@]}"; do
  echo "    https://$APP_APP.fly.dev/register?invite=$code"
done
echo
echo "Share these URLs with your beta testers. Each code is single-use; after"
echo "someone registers with it, the code is burned."
