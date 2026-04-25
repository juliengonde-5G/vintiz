#!/bin/bash
set -euo pipefail

# Only run in remote Claude Code sessions
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo '{"async": true, "asyncTimeout": 300000}'

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/home/user/vintiz}"
COMPOSE_FILE="$PROJECT_DIR/docker/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/.env"

# ── Détecter le mode : Docker (VPS /opt/vintiz) ou local (dev /home/user/vintiz)
# On est en mode Docker si les conteneurs vintiz tournent déjà OU si on est sur /opt
USE_DOCKER=false
if command -v docker &>/dev/null; then
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "vintiz-"; then
    USE_DOCKER=true
  elif [ "$PROJECT_DIR" = "/opt/vintiz" ]; then
    USE_DOCKER=true
  fi
fi

if $USE_DOCKER; then
  # ── Mode Docker (VPS) ──────────────────────────────────────────────────────
  echo "[1/3] Vérification des conteneurs Docker..."
  ARGS="-f $COMPOSE_FILE"
  [ -f "$ENV_FILE" ] && ARGS="$ARGS --env-file $ENV_FILE"

  docker compose $ARGS up -d 2>&1 | tail -5

  echo "[2/3] Attente API (max 60s)..."
  for i in $(seq 1 60); do
    if docker exec vintiz-api python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" \
      > /dev/null 2>&1; then
      echo "  API: OK"
      break
    fi
    if [ "$i" -eq 60 ]; then
      echo "  API: TIMEOUT — logs:"
      docker logs vintiz-api --tail 20
      exit 1
    fi
    sleep 1
  done

  echo "[3/3] Migrations..."
  docker exec vintiz-api python -m alembic upgrade head 2>&1 | tail -3
  echo "  OK"

else
  # ── Mode local (dev Claude Code) ──────────────────────────────────────────
  echo "[1/3] Démarrage PostgreSQL..."
  if ! pg_isready -q 2>/dev/null; then
    pg_ctlcluster 16 main start 2>&1 || true
    for i in $(seq 1 20); do
      pg_isready -q 2>/dev/null && break
      [ "$i" -eq 20 ] && echo "  PostgreSQL: TIMEOUT" && exit 1
      sleep 1
    done
  fi
  echo "  PostgreSQL: OK"

  echo "[2/3] Dépendances Python..."
  cd "$PROJECT_DIR/apps/api"
  pip install -e ".[dev]" -q 2>/dev/null || pip install -r requirements.txt -q 2>/dev/null || true
  echo "  Python: OK"

  echo "[3/3] Démarrage API..."
  cd "$PROJECT_DIR/apps/api"
  export PYTHONPATH="$PROJECT_DIR/apps/api"

  if ! curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    fuser -k 8000/tcp > /dev/null 2>&1 || true
    sleep 1
    nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 \
      > /tmp/vintiz-api.log 2>&1 &

    for i in $(seq 1 30); do
      curl -sf http://localhost:8000/api/health > /dev/null 2>&1 && echo "  API: OK" && exit 0
      [ "$i" -eq 30 ] && echo "  API: TIMEOUT" && tail -10 /tmp/vintiz-api.log && exit 1
      sleep 1
    done
  else
    echo "  API: déjà en cours"
  fi
fi
