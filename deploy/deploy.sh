#!/usr/bin/env bash
# Deploy the latest main: fetch it, rebuild what changed, restart. Run on the server, by the
# GitHub Actions deploy job (through a restricted SSH key) or by hand.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Deploying $(git rev-parse --short HEAD 2>/dev/null) -> latest main"
git fetch --quiet origin main
git reset --hard origin/main # the server never has local changes; .env is not tracked
echo "Now at $(git log -1 --format='%h %s')"

docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
docker image prune -f >/dev/null # old images fill the small disk
echo "Deployed."
