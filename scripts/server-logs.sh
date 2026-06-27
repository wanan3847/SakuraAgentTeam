#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/SakuraAgentTeam"
cd "$APP_DIR"

docker compose -f infra/docker-compose.yml logs -f --tail=200
