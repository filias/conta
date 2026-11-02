#!/usr/bin/env bash
# One-time setup of conta on the server. Run as root:
#   scp deploy/setup-server.sh memi: && ssh -t memi bash setup-server.sh
# Safe to re-run: existing checkout, .env and Caddy block are left alone.
set -euo pipefail

APP=/opt/conta
REPO=${REPO:-https://github.com/filias/conta.git}
CADDYFILE=/etc/caddy/Caddyfile

if [ ! -d "$APP" ]; then
  for port in 8007 9007; do
    if ss -ltn "sport = :$port" | grep -q LISTEN; then
      echo "Port $port is already in use — pick another in deploy/ and retry." >&2
      exit 1
    fi
  done
  git clone "$REPO" "$APP"
fi

cd "$APP"
uv sync --no-dev
mkdir -p private/guides private/videos

if [ ! -f .env ]; then
  echo "Choose the conta login password."
  HASH=$(uv run python -c "
import getpass, sys
from werkzeug.security import generate_password_hash
p = getpass.getpass('Password: ')
if not p or p != getpass.getpass('Again: '):
    sys.exit('Passwords empty or different.')
print(generate_password_hash(p))")
  umask 077
  {
    echo "SECRET_KEY='$(openssl rand -hex 32)'"
    echo "ADMIN_PASSWORD_HASH='$HASH'"
    echo "CALENDAR_TOKEN='$(openssl rand -hex 16)'"
    echo "SITE_URL=https://conta.filias.dev"
    echo "SESSION_COOKIE_SECURE=1"
    echo "# Reminders: fill in SMTP_* and/or NTFY_URL (see .env.example)"
  } > .env
  umask 022
fi

if [ ! -f /etc/conta-webhook.env ]; then
  (umask 077; echo "WEBHOOK_SECRET=$(openssl rand -hex 20)" > /etc/conta-webhook.env)
fi

cp deploy/conta.service deploy/conta-webhook.service deploy/conta-remind.service \
  deploy/conta-remind.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now conta conta-webhook conta-remind.timer
systemctl restart conta conta-webhook

if ! grep -q "^conta.filias.dev" "$CADDYFILE"; then
  BACKUP="$CADDYFILE.bak.$(date +%s)"
  cp "$CADDYFILE" "$BACKUP"
  { echo; grep -v '^#' deploy/Caddyfile; } >> "$CADDYFILE"
  if ! caddy validate --config "$CADDYFILE" --adapter caddyfile; then
    cp "$BACKUP" "$CADDYFILE"
    echo "Caddyfile invalid — restored the original." >&2
    exit 1
  fi
  systemctl reload caddy || caddy reload --config "$CADDYFILE"
fi

sleep 2
curl -fsS -o /dev/null -w "app on :8007 → HTTP %{http_code}\n" http://127.0.0.1:8007/
echo
echo "Done. Webhook secret is in /etc/conta-webhook.env."
