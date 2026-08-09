#!/usr/bin/env bash
# One-command update for a deployed F1 pipeline (EC2 + Docker Compose).
#
# Run it on the instance, from the repo root, as root (the repo is root-owned
# and Docker needs privileges):
#
#     sudo bash deploy/update.sh
#
# It pulls the latest code and rebuilds/recreates the containers. The
# --force-recreate is deliberate: a plain `--build` rebuilds the image but keeps
# the old container running, so the dashboard would otherwise still serve the
# stale version.
#
# Options / environment:
#   BRANCH=<name>   branch to deploy (default: main)
#   --migrate       also apply Alembic migrations after the rebuild. Only use
#                   this on an Alembic-managed database; instances bootstrapped
#                   with `init-db` are not stamped, so a blind upgrade can fail
#                   on already-existing tables (see deploy/README.md).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/f1-pipeline}"
BRANCH="${BRANCH:-main}"
RUN_MIGRATE=0
for arg in "$@"; do
  case "$arg" in
    --migrate) RUN_MIGRATE=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

cd "$APP_DIR"

echo "==> Updating $APP_DIR to latest origin/$BRANCH"
git fetch origin
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "==> Rebuilding and recreating containers"
docker compose up -d --build --force-recreate

if [ "$RUN_MIGRATE" -eq 1 ]; then
  echo "==> Applying database migrations"
  docker compose run --rm --entrypoint alembic pipeline upgrade head \
    || echo "WARN: migration failed; is the DB Alembic-managed? See deploy/README.md."
fi

echo "==> Current state"
docker compose ps

echo
echo "Done. Now on:"
git log --oneline -1
echo "Dashboard: http://<instance-public-ip>:8501  (hard-refresh, or ⋮ → Clear cache)."
