#!/usr/bin/env bash
# ===========================================
# Vintiz V2 - Script de deploiement production
# ===========================================
# Usage: ./scripts/deploy.sh [--first-run]
#
# Pre-requis sur le serveur:
#   - Docker + Docker Compose v2
#   - Git
#   - Fichier .env configure (copier .env.production et remplir les secrets)
#
# DNS requis (pointer vers l'IP du VPS):
#   - vintiz.fr → IP_VPS
#   - www.vintiz.fr → IP_VPS
#   - app.vintiz.fr → IP_VPS
#   - api.vintiz.fr → IP_VPS

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/.env"

echo "============================================"
echo "  Vintiz V2 - Deploiement Production"
echo "============================================"
echo ""

# Verifications
if [ ! -f "$ENV_FILE" ]; then
    echo "ERREUR: Fichier .env manquant."
    echo "  1. Copier .env.production en .env"
    echo "  2. Remplir les valeurs reelles (mots de passe, cles API)"
    echo ""
    echo "  cp .env.production .env && nano .env"
    exit 1
fi

if grep -q "CHANGER_MOI" "$ENV_FILE"; then
    echo "ERREUR: Le fichier .env contient encore des valeurs par defaut (CHANGER_MOI)."
    echo "  Editez .env et remplacez toutes les valeurs CHANGER_MOI."
    exit 1
fi

echo "[1/5] Pull derniere version du code..."
cd "$PROJECT_DIR"
git pull origin claude/vintiz-shop-management-v2-Fso64

echo ""
echo "[2/5] Build des images Docker..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache

echo ""
echo "[3/5] Arret des anciens conteneurs..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down --remove-orphans

echo ""
echo "[4/5] Demarrage des services..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

echo ""
echo "[5/5] Verification des services..."
sleep 5

# Attente que l'API soit prete
echo "  Attente API..."
for i in $(seq 1 30); do
    if docker exec vintiz-api curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "  API: OK"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  API: TIMEOUT - verifier les logs avec: docker logs vintiz-api"
    fi
    sleep 2
done

# Verification des conteneurs
echo ""
echo "  Etat des services:"
docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# Premier deploiement: migration + seed
if [ "${1:-}" = "--first-run" ]; then
    echo ""
    echo "[INIT] Premier deploiement detecte..."

    echo "  Migration de la base de donnees..."
    docker exec vintiz-api python -m alembic upgrade head 2>/dev/null || echo "  (Alembic migrations a configurer)"

    echo "  Injection des donnees initiales..."
    docker exec vintiz-api python -m scripts.seed_data 2>/dev/null || echo "  (Seed a executer manuellement)"

    echo ""
    echo "  Initialisation terminee."
fi

echo ""
echo "============================================"
echo "  Deploiement termine !"
echo "============================================"
echo ""
echo "  Site vitrine:  https://vintiz.fr"
echo "  Back-office:   https://app.vintiz.fr"
echo "  API:           https://api.vintiz.fr"
echo ""
echo "  Logs: docker compose -f $COMPOSE_FILE logs -f"
echo "  Stop: docker compose -f $COMPOSE_FILE down"
echo ""
