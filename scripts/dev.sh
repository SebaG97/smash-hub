#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
case "${1:-up}" in
  install) docker compose build ;;
  up) docker compose up -d --build --wait ;;
  down) docker compose down ;;
  migrate) docker compose run --rm api alembic upgrade head ;;
  bootstrap) docker compose run --rm api python -m app.bootstrap ;;
  logs) docker compose logs -f ;;
  test) trap 'docker compose -f compose.test.yaml down -v' EXIT
    docker compose -f compose.test.yaml up --build --abort-on-container-exit --exit-code-from api ;;
  *) echo 'Usage: scripts/dev.sh install|up|down|migrate|bootstrap|test|logs'; exit 2 ;;
esac
