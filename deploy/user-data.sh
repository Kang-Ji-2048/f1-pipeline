#!/usr/bin/env bash
# EC2 user-data bootstrap for the F1 data pipeline.
#
# Paste this into the "User data" field when launching an Ubuntu 22.04+ EC2
# instance (or run it manually after SSHing in). It installs Docker, clones the
# repo, and brings up the Postgres + pipeline + dashboard stack via compose.
#
# Configure the repo URL and (optionally) AWS/S3 settings below before use.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Kang-Ji-2048/f1-pipeline.git}"
APP_DIR="/opt/f1-pipeline"

# ── Install Docker Engine + compose plugin ──────────────────────────────────
apt-get update -y
apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# ── Fetch the application ───────────────────────────────────────────────────
if [ ! -d "$APP_DIR" ]; then
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

# ── Configuration ───────────────────────────────────────────────────────────
# Provide a real .env (see .env.example). The compose file already wires the
# internal DATABASE_URL for the bundled Postgres service.
if [ ! -f .env ]; then
  cp .env.example .env
fi

# ── Launch the stack (db + pipeline init + dashboard on :8501) ──────────────
docker compose up -d --build

# Initialise the schema and ingest the current season on first boot.
docker compose run --rm pipeline init-db
docker compose run --rm pipeline ingest-ergast --season "$(date +%Y)" \
  || echo "WARN: initial ingest failed; run it manually later (see deploy/README.md)."

echo "F1 pipeline stack is up. Dashboard: http://<instance-public-ip>:8501"
