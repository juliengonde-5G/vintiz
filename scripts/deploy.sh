#!/usr/bin/env bash
# ===========================================
# Vintiz V3 — Script de deploiement production
# ===========================================
# Usage:
#   ./scripts/deploy.sh                  Mise a jour normale
#   ./scripts/deploy.sh --first-run      Alias compatible (migrations comme tout deploy)
#   ./scripts/deploy.sh --rollback       Revenir a la version precedente
#
# Pre-requis sur le serveur:
#   - Docker Engine 24+ + Docker Compose v2 (docker compose, pas docker-compose)
#   - Git
#   - Fichier .env configure (copier .env.production.template -> .env et remplir les secrets)
#
# DNS requis (pointer vers l'IP du VPS):
#   vintiz.fr, www.vintiz.fr, app.vintiz.fr, api.vintiz.fr

set -eo pipefail

# Resolve paths robustly regardless of how the script is invoked
_SELF="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$_SELF")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
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
    --first-run)     FIRST_RUN=true ;;
    --rollback)      ROLLBACK=true ;;
    --test-products)
      err "Option retiree : les scripts de seed de test ne sont pas livres en production."
      exit 2
      ;;
    --help|-h)
      echo "Usage: $0 [--first-run | --rollback | --test-products]"
      echo "  --first-run      Alias compatible ; les migrations sont toujours appliquees"
      echo "  --rollback       Restaure la version du code precedant le dernier deploiement"
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
# Branch to deploy: env var DEPLOY_BRANCH, or CLI arg --branch=xxx, or default main
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
for arg in "$@"; do
  case "$arg" in --branch=*) DEPLOY_BRANCH="${arg#--branch=}" ;; esac
done

step "1/6" "Recuperation du code (branche: $DEPLOY_BRANCH)..."
git fetch origin "$DEPLOY_BRANCH"
git reset --hard "origin/$DEPLOY_BRANCH"
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
# Provenance du build → exposée par GET /api/health (build_sha/build_date).
# Permet de vérifier d'un coup d'œil quelle version tourne en prod.
export VINTIZ_BUILD_SHA="$NEW_COMMIT"
export VINTIZ_BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
log "Build SHA=$VINTIZ_BUILD_SHA date=$VINTIZ_BUILD_DATE"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build
log "Images construites"

# ============================================================
# 3. ARRET DES ANCIENS CONTENEURS
# ============================================================
step "3/6" "Arret des anciens conteneurs..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans
log "Anciens conteneurs arretes"

# ============================================================
# 4. BASE, MIGRATIONS, DEMARRAGE
# ============================================================
step "4/6" "Demarrage de la base et migrations Alembic..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d db redis

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
  exit 1
fi
log "PostgreSQL: OK"

# Run migrations in a one-shot container before the API starts. The API has a
# production boot guard and intentionally refuses a stale schema.
if $FIRST_RUN; then
  if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm api \
      python scripts/bootstrap_database.py --confirm-empty; then
    log "Schema initial vide cree sans donnees de demonstration"
  else
    err "Bootstrap refuse ou echoue — verifiez que la base est vraiment vide"
    exit 1
  fi
fi
if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm api \
    python -m alembic upgrade head; then
  log "Migrations: OK"
else
  err "Migrations echouees — API non demarree"
  exit 1
fi

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
log "Conteneurs demarres sur le schema migre"

# ============================================================
# 5. HEALTH CHECKS
# ============================================================
step "5/6" "Verification de sante des services..."

# Attente API
echo "  Attente API (max 120s)..."
API_OK=false
for i in $(seq 1 40); do
  if docker exec vintiz-api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" > /dev/null 2>&1; then
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
# 6. SMOKE TESTS SEO (landing page + robots + sitemap + JSON-LD)
# ============================================================
step "6/7" "Smoke tests SEO (landing, robots.txt, sitemap.xml, JSON-LD)..."

# Les tests hittent le container site en interne (reseau Docker) via l'API
# (qui a python + urllib). Evite les dependances DNS/TLS externes.
SITE_INTERNAL_URL="http://vintiz-site:3001"

check_seo_url() {
  local path="$1"; local label="$2"
  if docker exec vintiz-api python -c "
import sys, urllib.request
try:
    r = urllib.request.urlopen('$SITE_INTERNAL_URL$path', timeout=5)
    sys.exit(0 if r.status == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    log "$label: HTTP 200"
  else
    warn "$label: KO (non bloquant)"
  fi
}

check_seo_url "/" "Landing page /"
check_seo_url "/robots.txt" "robots.txt"
check_seo_url "/sitemap.xml" "sitemap.xml"

# Verification JSON-LD + meta description sur la landing
if docker exec vintiz-api python -c "
import urllib.request, sys
html = urllib.request.urlopen('$SITE_INTERNAL_URL/', timeout=5).read().decode('utf-8', 'ignore')
ok = 'application/ld+json' in html and 'name=\"description\"' in html.lower()
sys.exit(0 if ok else 1)
" 2>/dev/null; then
  log "Metadata SEO (JSON-LD + description) OK"
else
  warn "Metadata SEO incomplete (non bloquant)"
fi

# GA4 configure ? (lu depuis le .env sans sourcing pour eviter les side-effects)
GA_ID_VALUE=$(grep -E '^NEXT_PUBLIC_GA_ID=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs || true)
if [ -n "$GA_ID_VALUE" ]; then
  log "GA4 configure : $GA_ID_VALUE"
else
  warn "GA4 non configure (NEXT_PUBLIC_GA_ID vide) — aucun marqueur injecte."
  warn "Pour activer : renseigner NEXT_PUBLIC_GA_ID dans .env + relancer ce script."
fi

# Search Console configure ?
GSC_VALUE=$(grep -E '^NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs || true)
if [ -n "$GSC_VALUE" ]; then
  log "Search Console : verification configuree"
else
  warn "Search Console non verifiee (NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION vide)"
fi

# ============================================================
# 7. ETAT FINAL
# ============================================================
step "7/7" "Etat des services:"
docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

if $FIRST_RUN; then
  warn "--first-run ne cree aucun compte ni donnee de demonstration."
  warn "Creez le premier manager avec :"
  warn "  docker compose -f $COMPOSE_FILE run --rm api python scripts/create_manager.py --username <nom> --email <email>"
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
echo "  Panel SEO:     https://app.vintiz.fr/seo"
echo "  Sitemap:       https://vintiz.fr/sitemap.xml"
echo "  Robots:        https://vintiz.fr/robots.txt"
echo ""
echo "  Commandes utiles:"
echo "    Logs:     docker compose -f $COMPOSE_FILE logs -f"
echo "    Stop:     docker compose -f $COMPOSE_FILE down"
echo "    Rollback: ./scripts/deploy.sh --rollback"
echo "    Backup:   ./scripts/backup.sh"
echo ""
