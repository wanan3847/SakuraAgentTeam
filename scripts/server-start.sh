#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/SakuraAgentTeam"
cd "$APP_DIR"

if [ ! -f backend/.env ]; then
  echo "[sakura] backend/.env not found"
  exit 1
fi

echo "[sakura] starting containers"
docker compose -f infra/docker-compose.yml up -d --build

echo "[sakura] started"
