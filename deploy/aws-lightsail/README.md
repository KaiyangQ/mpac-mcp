# `deploy/aws-lightsail/` — single-host MPAC web-app on AWS Lightsail

Replaces the two fly.io apps (`mpac-web-api` + `mpac-web-app`) with one
Lightsail instance running both containers behind host nginx. Total cost
for the `$5/month` Lightsail plan (2GB RAM / 40GB SSD / 2TB traffic) is
constant — no surprise bills.

## One-time runbook

Steps are numbered so you can resume if interrupted. Everything except
steps 1-2 happens over SSH on the Lightsail box.

### 1. Launch the Lightsail instance

AWS Console → Lightsail → **Create instance** →

| Field | Value |
|---|---|
| Platform | Linux/Unix |
| Blueprint | **OS Only → Ubuntu 24.04 LTS** |
| Plan | **$5/month** (1 vCPU, 2 GB RAM, 40 GB SSD, 2 TB transfer) |
| SSH key | Default or create new — download the `.pem` |
| Region | whichever you picked (e.g. `us-west-2`) |
| Name | `mpac-web` |

After it's running → **Networking** tab → **Create static IP** → attach
to `mpac-web`. Note the IP.

### 2. (Optional) Point your domain

If you have a domain, add a DNS `A` record:
```
mpac.yourname.com  A  <static-ip>
```

No domain? Use [DuckDNS](https://www.duckdns.org) — sign in with GitHub,
claim a free subdomain, point it at your static IP. The rest of this
runbook works the same either way.

### 3. SSH in + bootstrap

```bash
ssh -i ~/Downloads/LightsailDefault.pem ubuntu@<static-ip>
```

Then on the instance:

```bash
# Generate a deploy key for the private repo
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 -C "mpac-lightsail"
cat ~/.ssh/id_ed25519.pub
# → copy the single line that prints
```

Paste that public key at
<https://github.com/KaiyangQ/Agent_talking/settings/keys> → **Add deploy key**
(title: `mpac-lightsail`, leave "allow write" unchecked).

Back on the instance:

```bash
# Trust GitHub's SSH host key
ssh-keyscan github.com >> ~/.ssh/known_hosts

git clone git@github.com:KaiyangQ/Agent_talking.git
cd Agent_talking

sudo bash deploy/aws-lightsail/bootstrap.sh
```

`bootstrap.sh` installs Docker + nginx + certbot + ufw (~3 min), opens
firewall, and creates `/var/mpac/data` for SQLite persistence.

### 4. Put secrets in `/etc/mpac/`

```bash
sudo cp deploy/aws-lightsail/api.env.example /etc/mpac/api.env
sudo chmod 640 /etc/mpac/api.env

# Generate fresh secrets. Do NOT reuse the fly.io values — if anything
# leaked during the fly deploy, a fresh set limits blast radius.
JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' 2>/dev/null \
    || python3 -c 'import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())')

sudo sed -i "s|paste_48_urlsafe_chars_here|$JWT_SECRET|" /etc/mpac/api.env
sudo sed -i "s|paste_fernet_key_here|$ENCRYPTION_KEY|" /etc/mpac/api.env
sudo sed -i "s|https://your.domain.here|https://mpac.yourname.com|" /etc/mpac/api.env
```

> 🚨 If you regenerate `MPAC_WEB_ENCRYPTION_KEY`, any previously-stored
> BYOK Anthropic keys can't be decrypted anymore — each user needs to
> re-paste their key in Settings. For the 4 test accounts this doesn't
> matter (they have no keys on file yet).

And the compose-level `NEXT_PUBLIC_API_URL` (Next.js bakes this in at
build time):

```bash
sudo tee /etc/mpac/compose.env > /dev/null <<EOF
NEXT_PUBLIC_API_URL=https://mpac.yourname.com
EOF
sudo chmod 640 /etc/mpac/compose.env
```

### 5. Restore the SQLite backup

The backup taken from fly is at `deploy/aws-lightsail/backups/mpac_web.db`
in the repo (gitignored). Upload from your laptop:

```bash
# FROM LAPTOP (not the instance):
scp -i ~/Downloads/LightsailDefault.pem \
    deploy/aws-lightsail/backups/mpac_web.db \
    ubuntu@<static-ip>:/tmp/mpac_web.db
```

Back on the instance:

```bash
sudo mv /tmp/mpac_web.db /var/mpac/data/mpac_web.db
sudo chmod 640 /var/mpac/data/mpac_web.db

# Confirm the 4 test accounts + 10 codes survived the round-trip
sqlite3 /var/mpac/data/mpac_web.db "SELECT COUNT(*) || ' users' FROM users;"
sqlite3 /var/mpac/data/mpac_web.db "SELECT COUNT(*) || ' codes' FROM signup_codes;"
```

### 6. Build + start the containers

```bash
cd ~/Agent_talking
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml \
    --env-file /etc/mpac/compose.env up -d --build
```

Watch logs:

```bash
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml logs -f
```

Should see `INFO: Uvicorn running on http://0.0.0.0:8001` from the api
container and Next.js startup from the app container.

### 7. Install nginx config + TLS

```bash
sudo sed "s|__DOMAIN__|mpac.yourname.com|g" \
    deploy/aws-lightsail/nginx.conf.template \
    > /tmp/mpac.conf
sudo mv /tmp/mpac.conf /etc/nginx/sites-available/mpac
sudo ln -sf /etc/nginx/sites-available/mpac /etc/nginx/sites-enabled/mpac
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Then request a TLS cert. Certbot will add the HTTPS server block + auto-redirect:

```bash
sudo certbot --nginx -d mpac.yourname.com \
    --agree-tos -m happylifeqqq@gmail.com --redirect --no-eff-email
```

Cert auto-renews via the certbot systemd timer (already enabled by the
Ubuntu package).

### 8. Verify

```bash
curl -sS https://mpac.yourname.com/health
# → {"status":"ok"}

curl -sS -X POST https://mpac.yourname.com/api/login \
    -H "Content-Type: application/json" \
    -d '{"email":"alice@mpac.test","password":"mpac-test-2026"}' \
    | python3 -m json.tool
# → { token, user_id: 1, email: "alice@mpac.test", display_name: "Alice" }
```

### 9. Update the public URL everywhere

Edit `BETA_ACCESS.md` — replace `https://mpac-web-app.fly.dev` with your
new `https://mpac.yourname.com`. Commit to main.

### 10. Destroy the fly.io apps

```bash
fly apps destroy mpac-web-api --yes
fly apps destroy mpac-web-app --yes
```

(Can also do this from <https://fly.io/dashboard> if CLI is blocked by
the trial-expired state.)

## Day-2 ops

### Updating the site after a code push

```bash
ssh ubuntu@<static-ip>
cd ~/Agent_talking
git pull
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml \
    --env-file /etc/mpac/compose.env up -d --build
```

The `--build` flag rebuilds the image; Next.js takes 2-3 minutes on
2GB RAM. The api container rebuild is ~30s.

If you changed `NEXT_PUBLIC_API_URL` (e.g. new domain), add `--no-cache
app` to force Next to re-bake it into the bundle:

```bash
sudo docker compose ... build --no-cache app
sudo docker compose ... up -d
```

### Reading logs

```bash
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml logs --tail=100 api
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml logs --tail=100 app
sudo tail -f /var/log/nginx/access.log
```

### Backing up SQLite

```bash
sudo sqlite3 /var/mpac/data/mpac_web.db ".backup /tmp/mpac_backup.db"
scp ubuntu@<ip>:/tmp/mpac_backup.db ./backups/$(date +%Y-%m-%d).db
```

Run weekly as a cron job on the instance if this matters.

### Rotating invite codes

Edit the CSV in `/etc/mpac/api.env`, then:

```bash
sudo docker compose -f deploy/aws-lightsail/docker-compose.yml \
    --env-file /etc/mpac/compose.env restart api
```

On startup the api re-reads `MPAC_WEB_INVITE_CODES` and seeds new rows
into `signup_codes`. Existing rows (including used ones) are untouched.

## Cost tracking

| Line item | Monthly |
|---|---|
| Lightsail `$5` plan | $5.00 |
| Static IP (attached) | $0 |
| DNS (if via Route 53) | $0.50/hosted zone |
| Outbound transfer | 0 — included 2 TB covers it |
| **Total** | **~$5/month** |

`$100` AWS credit = ~20 months of runway, but the Free Plan window is
6 months — after that you must upgrade to a paid plan for the account
to keep serving (the `$5/month` cost stays the same post-upgrade).
