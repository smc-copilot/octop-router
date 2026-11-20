#!/usr/bin/env bash
set -euo pipefail
command -v docker >/dev/null || { echo 'docker not found'; exit 1; }
docker compose version >/dev/null || { echo 'docker compose plugin not found'; exit 1; }
test -f .env || { echo '.env not found; copy .env.example to .env and configure it'; exit 1; }
echo 'Docker and .env prerequisites are present.'
