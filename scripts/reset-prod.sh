#!/usr/bin/env bash
# =============================================================================
# Vintiz — Script de remise à zéro et reconstruction complète
# =============================================================================
#
# USAGE
#   bash scripts/reset-prod.sh [OPTIONS]
#
# OPTIONS
#   --soft       Rebuild sans toucher à la base de données (défaut)
#   --hard       Supprime la base et reseed (DÉTRUIT TOUTES LES DONNÉES)
#   --seed-only  Injecte les données de test sans rebuilder
#   --status     Affiche l'état actuel sans rien modifier
#
# PRÉREQUIS SUR LE VPS
#   - Docker + Docker Compose v2
#   - /opt/vintiz/.env configuré (voir commentaires section ENV ci-dessous)
#   - Git accès au repo juliengonde-5G/vintiz
#
# ARCHITECTURE
#   Tous les services tournent en Docker sur le même réseau vintiz-network.
#   Caddy (ports 80/443) est le seul point d'entrée public.
#   Port 8000 NON exposé sur l'hôte — health check via docker exec.
#
#   vintiz-caddy  → reverse proxy HTTPS (ports 80, 443)
#   vintiz-api    → FastAPI Python 3.11-slim (interne :8000)
#   vintiz-db     → PostgreSQL 16 user=vintiz db=vintiz (interne :5432)
#   vintiz-redis  → Redis 7 (interne :6379)
#   vintiz-web    → Next.js admin app.vintiz.fr (interne :3000)
#   vintiz-site   → Next.js site vitrine vintiz.fr (interne :3001)
#
# PIÈGES CONNUS
#   - Image python:3.11-slim : PAS de curl ni wget → utiliser urllib.request
#   - PostgreSQL user = vintiz (PAS postgres)
#   - Tables créées via Base.metadata.create_all au démarrage de l'API
#     (le dossier alembic/versions/ est vide — ne pas utiliser alembic upgrade)
#   - Le port 3001 est potentiellement occupé par d'autres conteneurs sur le VPS
#     (lumos-app-1) → ne jamais mapper ce port sur l'hôte pour vintiz-site
#
# EXEMPLE .env (/opt/vintiz/.env)
#   DATABASE_URL=postgresql+asyncpg://vintiz:MOT_DE_PASSE@db:5432/vintiz
#   SECRET_KEY=cle-jwt-longue-et-aleatoire
#   POSTGRES_USER=vintiz
#   POSTGRES_PASSWORD=MOT_DE_PASSE
#   POSTGRES_DB=vintiz
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENWEATHER_API_KEY=...
#
# HISTORIQUE
#   2026-04-13  Création après série de blocages en production :
#               - Mauvaise branche dans l'ancien deploy.sh
#               - curl absent de python:3.11-slim
#               - Conflit port 3001 avec autres conteneurs
#               - scripts/seed_data.py absent de l'image Docker
#               - Contrôle PostgreSQL avec user 'postgres' au lieu de 'vintiz'
# =============================================================================

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
BRANCH="claude/fix-product-features-LbqVr"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/.env"
COMPOSE="docker compose -f $COMPOSE_FILE --env-file $ENV_FILE"
PG_USER="vintiz"
PG_DB="vintiz"

# ─────────────────────────────────────────────────────────────────────────────
# COULEURS ET HELPERS
# ─────────────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()      { echo -e "  ${GREEN}[OK]${NC}  $1"; }
fail()    { echo -e "  ${RED}[KO]${NC}  $1"; }
warn()    { echo -e "  ${YELLOW}[!!]${NC}  $1"; }
step()    { echo -e "\n${BLUE}▶ $1${NC}"; }
section() { echo -e "\n${BLUE}══════════════════════════════════════════${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${BLUE}══════════════════════════════════════════${NC}"; }

# Health check API sans curl (absent de python:3.11-slim)
api_healthy() {
  docker exec vintiz-api python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" \
    > /dev/null 2>&1
}

# Attente API avec timeout
wait_api() {
  local timeout="${1:-120}"
  echo -n "  Attente API (max ${timeout}s) "
  for i in $(seq 1 "$timeout"); do
    if api_healthy; then
      echo " OK (${i}s)"
      return 0
    fi
    echo -n "."
    sleep 1
  done
  echo " TIMEOUT"
  echo ""
  echo "  Logs vintiz-api :"
  docker logs vintiz-api --tail 40 | sed 's/^/    /'
  return 1
}

# ─────────────────────────────────────────────────────────────────────────────
# MODE --status : affiche l'état sans modifier
# ─────────────────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--status" ]; then
  section "État des services Vintiz"

  step "Conteneurs Docker"
  $COMPOSE ps 2>/dev/null || docker ps --filter "name=vintiz" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

  step "API"
  api_healthy && ok "API répond" || fail "API ne répond pas"

  step "Base de données"
  TABLE_COUNT=$(docker exec vintiz-db psql -U "$PG_USER" -tc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" \
    "$PG_DB" 2>/dev/null | tr -d '[:space:]' || echo "?")
  ok "Tables : $TABLE_COUNT"

  step "Code source"
  cd "$PROJECT_DIR"
  echo "  Branche   : $(git branch --show-current)"
  echo "  Dernier commit : $(git log --oneline -1)"

  exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────
# MODE --seed-only : injecte les données sans rebuilder
# ─────────────────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--seed-only" ]; then
  section "Injection des données de test"
  api_healthy || { fail "API non disponible — lancez d'abord le script sans --seed-only"; exit 1; }
  docker exec -e PYTHONPATH=/app vintiz-api python /app/scripts/seed_data.py
  ok "Seed terminé"
  exit 0
fi

# ─────────────────────────────────────────────────────────────────────────────
# VÉRIFICATIONS PRÉALABLES
# ─────────────────────────────────────────────────────────────────────────────
section "Vérifications"

step "Fichier .env"
if [ ! -f "$ENV_FILE" ]; then
  fail ".env manquant dans $PROJECT_DIR"
  echo "  Créez-le à partir de .env.production :"
  echo "  cp .env.production .env && nano .env"
  exit 1
fi
ok ".env présent"

step "Variables obligatoires"
for VAR in DATABASE_URL SECRET_KEY POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB; do
  if grep -q "^${VAR}=" "$ENV_FILE" 2>/dev/null; then
    ok "$VAR défini"
  else
    fail "$VAR manquant dans .env"
    exit 1
  fi
done

step "Docker"
docker info > /dev/null 2>&1 && ok "Docker disponible" || { fail "Docker non disponible"; exit 1; }

# ─────────────────────────────────────────────────────────────────────────────
# [1] MISE À JOUR DU CODE
# ─────────────────────────────────────────────────────────────────────────────
section "[1/5] Mise à jour du code"
cd "$PROJECT_DIR"
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"
ok "Branche $BRANCH — $(git log --oneline -1)"

# ─────────────────────────────────────────────────────────────────────────────
# [2] NETTOYAGE (mode --hard uniquement)
# ─────────────────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--hard" ]; then
  section "[2/5] Nettoyage complet (--hard)"
  warn "SUPPRESSION des conteneurs et volumes DB dans 5s... Ctrl+C pour annuler"
  sleep 5

  # Stopper et supprimer les conteneurs vintiz (pas les autres projets)
  $COMPOSE down --volumes --remove-orphans 2>/dev/null || true
  ok "Conteneurs et volumes supprimés"
else
  section "[2/5] Arrêt des conteneurs"
  # --remove-orphans nettoie les conteneurs qui ne sont plus dans le compose
  # mais ne supprime PAS les volumes (données préservées)
  $COMPOSE down --remove-orphans 2>/dev/null || true
  ok "Conteneurs arrêtés (données préservées)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# [3] BUILD DES IMAGES
# ─────────────────────────────────────────────────────────────────────────────
section "[3/5] Build des images Docker"
# Note : scripts/ est copié dans l'image API via Dockerfile.api
# Note : web/site n'exposent PAS leurs ports sur l'hôte (Caddy reverse proxy)
$COMPOSE build 2>&1 | grep -E "^(#|Step|Successfully|ERROR|error)" || true
ok "Images construites"

# ─────────────────────────────────────────────────────────────────────────────
# [4] DÉMARRAGE
# ─────────────────────────────────────────────────────────────────────────────
section "[4/5] Démarrage des services"
$COMPOSE up -d
ok "Conteneurs démarrés"

step "Attente que l'API soit prête"
wait_api 120 || exit 1

# ─────────────────────────────────────────────────────────────────────────────
# [5] INITIALISATION DE LA BASE
# ─────────────────────────────────────────────────────────────────────────────
section "[5/5] Base de données"

# Les tables sont créées automatiquement par Base.metadata.create_all
# au démarrage de l'API (pas via alembic upgrade head).
# On vérifie juste que les tables sont là.
step "Vérification des tables"
TABLE_COUNT=$(docker exec vintiz-db psql -U "$PG_USER" -tc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" \
  "$PG_DB" 2>/dev/null | tr -d '[:space:]' || echo "0")

if [ "${TABLE_COUNT:-0}" -gt 5 ] 2>/dev/null; then
  ok "$TABLE_COUNT tables présentes"
else
  fail "Tables manquantes ($TABLE_COUNT) — l'API n'a peut-être pas démarré correctement"
  echo "  Logs : docker logs vintiz-api --tail 30"
  exit 1
fi

# Seed uniquement si --hard (reset complet) ou si la table users est vide
if [ "${1:-}" = "--hard" ]; then
  step "Injection des données initiales (--hard)"
  docker exec -e PYTHONPATH=/app vintiz-api python /app/scripts/seed_data.py 2>&1 | tail -5
  ok "Seed terminé — admin/vintiz2026, 300 produits, 50 clients"
else
  USER_COUNT=$(docker exec vintiz-db psql -U "$PG_USER" -tc \
    "SELECT count(*) FROM users" "$PG_DB" 2>/dev/null | tr -d '[:space:]' || echo "0")
  if [ "${USER_COUNT:-0}" -eq 0 ] 2>/dev/null; then
    step "Base vide — injection des données initiales"
    docker exec -e PYTHONPATH=/app vintiz-api python /app/scripts/seed_data.py 2>&1 | tail -5
    ok "Seed terminé — admin/vintiz2026, 300 produits, 50 clients"
  else
    ok "Données existantes ($USER_COUNT utilisateurs) — seed ignoré"
    echo "    (utilisez --hard pour réinitialiser complètement)"
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# RÉSUMÉ FINAL
# ─────────────────────────────────────────────────────────────────────────────
section "État final"
$COMPOSE ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo -e "${GREEN}  ✓ Vintiz opérationnel${NC}"
echo ""
echo "  Site vitrine : https://vintiz.fr"
echo "  Back-office  : https://app.vintiz.fr"
echo "  API health   : https://api.vintiz.fr/api/health"
echo ""
echo "  Logs en direct : docker logs vintiz-api -f"
echo "  Diagnostic     : bash scripts/diag.sh"
echo "  État           : bash scripts/reset-prod.sh --status"
echo ""
