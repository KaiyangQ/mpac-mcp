#!/usr/bin/env bash
# MPAC Lightsail bootstrap — run ONCE on a fresh Ubuntu 24.04 instance.
#
# Installs: Docker Engine + Compose plugin, nginx, certbot, ufw.
# Creates:  /var/mpac/data (SQLite volume), /etc/mpac (secrets).
# Opens:    22 (SSH), 80 (HTTP), 443 (HTTPS).
#
# Usage (run from the repo root after cloning, AS ROOT):
#     sudo bash deploy/aws-lightsail/bootstrap.sh
#
# After this finishes, see README.md for the next steps (populate
# /etc/mpac/api.env + compose.env, `docker compose up -d`, nginx + certbot).

set -euo pipefail

log()  { printf '\033[1;36m[bootstrap]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[bootstrap]\033[0m %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "must run as root (sudo)"

log "apt update + base deps"
apt-get update
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release \
    nginx certbot python3-certbot-nginx \
    ufw sqlite3

log "Docker (official repo)"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

log "ufw — allow 22 / 80 / 443"
ufw --force default deny incoming
ufw --force default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

log "/var/mpac/data + /etc/mpac"
mkdir -p /var/mpac/data /etc/mpac /var/www/certbot
chmod 750 /etc/mpac
chown root:root /etc/mpac

# systemd: make sure nginx + docker start on boot (both are enabled by
# default, but double-check so the instance is resilient to reboots).
systemctl enable --now docker nginx

log "adding 'ubuntu' user to 'docker' group (takes effect on next login)"
if id ubuntu >/dev/null 2>&1; then
    usermod -aG docker ubuntu
fi

log "done."
echo
echo "Next steps (see deploy/aws-lightsail/README.md for details):"
echo "  1. Fill in /etc/mpac/api.env    (copy from api.env.example)"
echo "  2. Fill in /etc/mpac/compose.env — set NEXT_PUBLIC_API_URL"
echo "  3. Restore SQLite backup to /var/mpac/data/mpac_web.db"
echo "  4. Build + start:"
echo "       sudo docker compose -f deploy/aws-lightsail/docker-compose.yml \\"
echo "            --env-file /etc/mpac/compose.env up -d --build"
echo "  5. Install nginx conf + certbot:"
echo "       sudo sed 's|__DOMAIN__|YOUR.HOST|g' \\"
echo "            deploy/aws-lightsail/nginx.conf.template \\"
echo "            > /etc/nginx/sites-available/mpac"
echo "       sudo ln -sf /etc/nginx/sites-available/mpac /etc/nginx/sites-enabled/mpac"
echo "       sudo rm -f /etc/nginx/sites-enabled/default"
echo "       sudo nginx -t && sudo systemctl reload nginx"
echo "       sudo certbot --nginx -d YOUR.HOST --agree-tos -m you@example.com"
