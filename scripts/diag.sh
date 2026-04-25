#!/bin/bash
# =============================================================================
# Vintiz — Script de diagnostic
# Usage: bash scripts/diag.sh
# =============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}[OK]${NC}  $1"; }
fail() { echo -e "  ${RED}[KO]${NC}  $1"; }
warn() { echo -e "  ${YELLOW}[!!]${NC}  $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/.env"

echo "════════════════════════════════════════════════════════"
echo "  Vintiz — Diagnostic $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Projet : $PROJECT_DIR"
echo "════════════════════════════════════════════════════════"

# ── Mode Docker ou local ──────────────────────────────────────────────────────
USE_DOCKER=false
command -v docker &>/dev/null && docker info &>/dev/null 2>&1 && USE_DOCKER=true

if $USE_DOCKER; then
  echo ""
  echo "▶ Docker Compose"
  COMPOSE_ARGS="-f $COMPOSE_FILE"
  [ -f "$ENV_FILE" ] && COMPOSE_ARGS="$COMPOSE_ARGS --env-file $ENV_FILE"

  SERVICES=(vintiz-api vintiz-db vintiz-web vintiz-caddy)
  for svc in "${SERVICES[@]}"; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$svc" 2>/dev/null || echo "absent")
    HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "$svc" 2>/dev/null || echo "")
    if [ "$STATUS" = "running" ]; then
      ok "$svc : running${HEALTH:+ ($HEALTH)}"
    else
      fail "$svc : $STATUS"
      echo "  → Démarrage..."
      docker compose $COMPOSE_ARGS up -d "$svc" 2>&1 | tail -3 | sed 's/^/    /'
    fi
  done

  echo ""
  echo "▶ API Health"
  if docker exec vintiz-api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" > /dev/null 2>&1; then
    HEALTH_RESP=$(docker exec vintiz-api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read().decode())" 2>/dev/null || echo "{}")
    ok "API répond : $HEALTH_RESP"
  else
    fail "API ne répond pas dans le conteneur"
    echo ""
    echo "  Logs vintiz-api (30 dernières lignes) :"
    docker logs vintiz-api --tail 30 2>&1 | sed 's/^/    /'
  fi

  echo ""
  echo "▶ Base de données"
  PG_USER="${POSTGRES_USER:-vintiz}"
  if docker exec vintiz-db pg_isready -U "$PG_USER" -q 2>/dev/null; then
    ok "PostgreSQL (vintiz-db) : accepte les connexions"
    DB_EXISTS=$(docker exec vintiz-db psql -U "$PG_USER" -tc "SELECT 1 FROM pg_database WHERE datname='vintiz'" 2>/dev/null | tr -d '[:space:]')
    [ "$DB_EXISTS" = "1" ] && ok "Base 'vintiz' : existe" || warn "Base 'vintiz' : introuvable"
  else
    fail "PostgreSQL ne répond pas"
    docker logs vintiz-db --tail 20 2>&1 | sed 's/^/    /'
  fi

  echo ""
  echo "▶ Tables"
  TABLE_COUNT=$(docker exec vintiz-db psql -U "${POSTGRES_USER:-vintiz}" -tc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" vintiz 2>/dev/null | tr -d '[:space:]')
  if [ -n "$TABLE_COUNT" ] && [ "$TABLE_COUNT" -gt 5 ] 2>/dev/null; then
    ok "Tables DB : $TABLE_COUNT tables présentes"
  else
    fail "Tables DB : insuffisantes ($TABLE_COUNT) — redémarrez l'API pour déclencher create_all"
  fi

  echo ""
  echo "▶ Accès externe (Caddy)"
  CADDY_STATUS=$(docker inspect --format='{{.State.Status}}' vintiz-caddy 2>/dev/null || echo "absent")
  if [ "$CADDY_STATUS" = "running" ]; then
    ok "Caddy : running (ports 80/443)"
  else
    fail "Caddy : $CADDY_STATUS"
  fi

else
  # ── Mode local (dev) ────────────────────────────────────────────────────────
  echo ""
  echo "▶ PostgreSQL (local)"
  if command -v pg_isready &>/dev/null && pg_isready -q 2>/dev/null; then
    ok "PostgreSQL : en cours d'exécution"
  elif systemctl is-active --quiet postgresql 2>/dev/null; then
    ok "PostgreSQL (systemd) : actif"
  else
    fail "PostgreSQL : ARRÊTÉ"
    command -v pg_ctlcluster &>/dev/null && pg_ctlcluster 16 main start 2>&1 | sed 's/^/    /' || \
      systemctl start postgresql 2>&1 | sed 's/^/    /' || \
      echo "  Impossible de démarrer PostgreSQL"
  fi

  echo ""
  echo "▶ API FastAPI (local)"
  if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    ok "API : répond sur :8000"
  else
    fail "API : NE RÉPOND PAS"
    API_LOG=$(find /tmp -name "vintiz-api.log" 2>/dev/null | head -1)
    if [ -n "$API_LOG" ]; then
      echo "  Log ($API_LOG) :"
      tail -20 "$API_LOG" | sed 's/^/    /'
    fi
    echo "  → Redémarrage..."
    fuser -k 8000/tcp > /dev/null 2>&1 || true
    cd "$PROJECT_DIR/apps/api"
    export PYTHONPATH="$PROJECT_DIR/apps/api"
    nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/vintiz-api.log 2>&1 &
    for i in $(seq 1 20); do
      curl -sf http://localhost:8000/api/health > /dev/null 2>&1 && ok "API redémarrée" && break
      [ "$i" -eq 20 ] && fail "Impossible de démarrer" && tail -10 /tmp/vintiz-api.log | sed 's/^/    /'
      sleep 1
    done
  fi
fi

# ── Résumé ─────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
if $USE_DOCKER; then
  API_OK=$(docker exec vintiz-api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" > /dev/null 2>&1 && echo yes || echo no)
  DB_OK=$(docker exec vintiz-db pg_isready -U "${POSTGRES_USER:-vintiz}" -q 2>/dev/null && echo yes || echo no)
else
  API_OK=$(curl -sf http://localhost:8000/api/health > /dev/null 2>&1 && echo yes || echo no)
  DB_OK=$(pg_isready -q 2>/dev/null && echo yes || echo no)
fi

if [ "$API_OK" = "yes" ] && [ "$DB_OK" = "yes" ]; then
  echo -e "  ${GREEN}✓ Services opérationnels${NC}"
else
  echo -e "  ${RED}✗ Problèmes détectés — voir détails ci-dessus${NC}"
  [ "$DB_OK" != "yes" ]  && echo "    - PostgreSQL KO"
  [ "$API_OK" != "yes" ] && echo "    - API KO"
fi
echo "════════════════════════════════════════════════════════"
