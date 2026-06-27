#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/SakuraAgentTeam"
cd "$APP_DIR"

echo "[sakura] stopping containers"
docker compose -f infra/docker-compose.yml down || true

echo "[sakura] stopped"
