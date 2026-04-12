#!/usr/bin/env bash
# ===========================================
# Vintiz V3 — Script de deploiement production
# ===========================================
# Usage:
#   ./scripts/deploy.sh              Mise a jour normale
#   ./scripts/deploy.sh --first-run  Premier deploiement (migrations + seed)
#   ./scripts/deploy.sh --rollback   Revenir a la version precedente
#
# Pre-requis sur le serveur:
#   - Docker Engine 24+ + Docker Compose v2 (docker compose, pas docker-compose)
#   - Git
#   - Fichier .env configure (copier .env.production.template -> .env et remplir les secrets)
#
# DNS requis (pointer vers l'IP du VPS):
#   vintiz.fr, www.vintiz.fr, app.vintiz.fr, api.vintiz.fr

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/.env"
ROLLBACK_FILE="$PROJECT_DIR/.deploy_rollback"

# Couleurs
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; }
step() { echo -e "\n${BLUE}[$1]${NC} $2"; }

# Parse arguments
FIRST_RUN=false
ROLLBACK=false
for arg in "$@"; do
  case "$arg" in
    --first-run) FIRST_RUN=true ;;
    --rollback)  ROLLBACK=true ;;
    --help|-h)
      echo "Usage: $0 [--first-run | --rollback]"
      echo "  --first-run  Lance migrations Alembic + seed data (300 produits, 50 clients)"
      echo "  --rollback   Restaure la version du code precedant le dernier deploiement"
      exit 0
      ;;
  esac
done

echo ""
echo "============================================"
echo "  Vintiz V3 — Deploiement Production"
echo "============================================"

# ============================================================
# ROLLBACK
# ============================================================
if $ROLLBACK; then
  if [ ! -f "$ROLLBACK_FILE" ]; then
    err "Aucune version precedente enregistree ($ROLLBACK_FILE introuvable)."
    err "Rollback impossible sans deploiement precedent."
    exit 1
  fi
  PREV_COMMIT=$(cat "$ROLLBACK_FILE")
  warn "Rollback vers commit: $PREV_COMMIT"
  cd "$PROJECT_DIR"
  git checkout "$PREV_COMMIT"
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
  log "Rollback termine vers $PREV_COMMIT"
  echo ""
  echo "  Rollback actif. Pour revenir a la derniere version:"
  echo "    git checkout main && ./scripts/deploy.sh"
  exit 0
fi

# ============================================================
# VERIFICATIONS PRE-DEPLOIEMENT
# ============================================================
step "0/6" "Verification de l'environnement..."

if [ ! -f "$ENV_FILE" ]; then
  err "Fichier .env manquant."
  echo ""
  echo "  Copier le template et remplir les secrets:"
  echo "    cp .env.production.template .env"
  echo "    nano .env"
  exit 1
fi

if grep -q "CHANGER_MOI" "$ENV_FILE"; then
  err "Le fichier .env contient encore des valeurs CHANGER_MOI."
  echo ""
  grep -n "CHANGER_MOI" "$ENV_FILE" | while IFS= read -r line; do
    echo "  Ligne: $line"
  done
  exit 1
fi

if ! command -v docker &>/dev/null; then
  err "Docker non installe. Installer Docker Engine 24+."
  exit 1
fi

if ! docker compose version &>/dev/null; then
  err "Docker Compose v2 non disponible (docker compose, pas docker-compose)."
  exit 1
fi

log "Environnement OK"

# ============================================================
# SAUVEGARDE DU COMMIT ACTUEL (pour rollback)
# ============================================================
cd "$PROJECT_DIR"
CURRENT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "$CURRENT_COMMIT" > "$ROLLBACK_FILE"
log "Commit actuel sauvegarde pour rollback eventuel: $CURRENT_COMMIT"

# ============================================================
# 1. GIT PULL
# ============================================================
step "1/6" "Recuperation du code depuis main..."
git fetch origin main
git reset --hard origin/main
NEW_COMMIT=$(git rev-parse --short HEAD)
if [ "$CURRENT_COMMIT" = "$NEW_COMMIT" ]; then
  warn "Code deja a jour ($NEW_COMMIT). Deploiement force."
else
  log "Code mis a jour: $CURRENT_COMMIT -> $NEW_COMMIT"
fi

# ============================================================
# 2. BUILD DES IMAGES
# ============================================================
step "2/6" "Build des images Docker..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build
log "Images construites"

# ============================================================
# 3. ARRET DES ANCIENS CONTENEURS
# ============================================================
step "3/6" "Arret des anciens conteneurs..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans
log "Anciens conteneurs arretes"

# ============================================================
# 4. DEMARRAGE
# ============================================================
step "4/6" "Demarrage des services..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
log "Conteneurs demarres"

# ============================================================
# 5. HEALTH CHECKS
# ============================================================
step "5/6" "Verification de sante des services..."

# Attente PostgreSQL
echo "  Attente PostgreSQL (max 60s)..."
DB_OK=false
for i in $(seq 1 20); do
  if docker exec vintiz-db pg_isready -U vintiz -q 2>/dev/null; then
    DB_OK=true
    break
  fi
  sleep 3
done
if ! $DB_OK; then
  err "PostgreSQL: TIMEOUT — verifier les logs"
  docker logs vintiz-db --tail 20
  warn "Pour rollback: ./scripts/deploy.sh --rollback"
  exit 1
fi
log "PostgreSQL: OK"

# Migrations Alembic (a chaque deploy pour appliquer les nouvelles)
echo "  Application des migrations Alembic..."
if docker exec vintiz-api python -m alembic upgrade head; then
  log "Migrations: OK"
else
  err "Migrations echouees"
  docker logs vintiz-api --tail 20
  warn "Pour rollback: ./scripts/deploy.sh --rollback"
  exit 1
fi

# Attente API
echo "  Attente API (max 120s)..."
API_OK=false
for i in $(seq 1 40); do
  if docker exec vintiz-api curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    API_OK=true
    break
  fi
  sleep 3
done
if ! $API_OK; then
  err "API: TIMEOUT — verifier les logs"
  docker logs vintiz-api --tail 30
  warn "Pour rollback: ./scripts/deploy.sh --rollback"
  exit 1
fi
log "API: OK"

# ============================================================
# 6. ETAT FINAL
# ============================================================
step "6/6" "Etat des services:"
docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# ============================================================
# PREMIER DEPLOIEMENT : SEED DATA
# ============================================================
if $FIRST_RUN; then
  echo ""
  echo "  ---- Initialisation des donnees ----"
  echo "  Injection seed data (300 produits, 50 clients, 200 transactions)..."
  if docker exec vintiz-api python scripts/seed_data.py; then
    log "Seed data: OK — admin/vintiz2026"
  else
    warn "Seed partiel. Relancer manuellement:"
    warn "  docker exec vintiz-api python scripts/seed_data.py"
  fi
fi

# ============================================================
# RESUME
# ============================================================
echo ""
echo "============================================"
echo "  Deploiement termine ! (commit: $NEW_COMMIT)"
echo "============================================"
echo ""
echo "  Site vitrine:  https://vintiz.fr"
echo "  Back-office:   https://app.vintiz.fr"
echo "  API:           https://api.vintiz.fr"
echo "  Health check:  https://api.vintiz.fr/api/health"
echo ""
echo "  Commandes utiles:"
echo "    Logs:     docker compose -f $COMPOSE_FILE logs -f"
echo "    Stop:     docker compose -f $COMPOSE_FILE down"
echo "    Rollback: ./scripts/deploy.sh --rollback"
echo "    Backup:   ./scripts/backup.sh"
echo ""
