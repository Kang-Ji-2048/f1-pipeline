#!/usr/bin/env bash
# Weekly ingestion script — called by cron or CI schedule.
# Usage: ./scripts/weekly_ingest.sh [SEASON]
set -euo pipefail

SEASON="${1:-$(date +%Y)}"

echo "=== F1 Data Pipeline — Weekly Ingest ==="
echo "Season: $SEASON"
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Run Alembic migrations
echo "Running migrations..."
alembic upgrade head

# Ingest Ergast data
echo "Ingesting Ergast data..."
f1-pipeline ingest-ergast --season "$SEASON"

# Ingest OpenF1 telemetry
echo "Ingesting OpenF1 telemetry..."
f1-pipeline ingest-openf1 --year "$SEASON"

echo "=== Ingest complete ==="
