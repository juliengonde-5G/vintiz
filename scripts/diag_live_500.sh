#!/usr/bin/env bash
# =============================================================================
# Vintiz — Diagnostic « Erreur réseau / 500 » sur /api/crm/account/personal-shopper/live
# =============================================================================
# À LANCER SUR LE VPS (là où tourne docker compose) :
#     cd /opt/vintiz
#     bash scripts/diag_live_500.sh "votre-email@exemple.fr"
#
# Le 500 fait disparaître l'en-tête CORS → le navigateur affiche une erreur
# CORS trompeuse. La VRAIE cause est dans les logs API + reproductible ci-dessous.
# Script READ-ONLY : il ne modifie rien (à part proposer la commande de fix).
# =============================================================================
set -uo pipefail

EMAIL="${1:-test@example.com}"
API_CONTAINER="${API_CONTAINER:-vintiz-api}"
DB_CONTAINER="${DB_CONTAINER:-vintiz-db}"
DB_USER="${DB_USER:-vintiz}"
DB_NAME="${DB_NAME:-vintiz}"
API_BASE="${API_BASE:-https://api.vintiz.fr}"
SITE_ORIGIN="${SITE_ORIGIN:-https://vintiz.fr}"

C_RED=$'\033[0;31m'; C_GRN=$'\033[0;32m'; C_YEL=$'\033[1;33m'; C_BLU=$'\033[0;34m'; C_NC=$'\033[0m'
ok()   { echo "${C_GRN}[OK]${C_NC} $*"; }
warn() { echo "${C_YEL}[!]${C_NC}  $*"; }
err()  { echo "${C_RED}[X]${C_NC}  $*"; }
step() { echo; echo "${C_BLU}=== $* ===${C_NC}"; }

# ----------------------------------------------------------------------------
step "0. Conteneurs en marche ?"
if docker ps --format '{{.Names}}' | grep -q "^${API_CONTAINER}$"; then
  ok "API container '${API_CONTAINER}' up"
else
  err "API container '${API_CONTAINER}' introuvable — 'docker ps' pour le vrai nom, puis API_CONTAINER=<nom> bash $0"
  docker ps --format '  {{.Names}}\t{{.Status}}'
  exit 1
fi
docker ps --format '  {{.Names}}\t{{.Status}}' | grep -E "vintiz|api|db|caddy" || true

# ----------------------------------------------------------------------------
step "1. Reproduire le 500 de l'EXTÉRIEUR (simuler le navigateur + Origin)"
echo "GET ${API_BASE}/api/crm/account/personal-shopper/live?email=${EMAIL}"
HTTP=$(curl -s -o /tmp/diag_body.json -w '%{http_code}' \
  -H "Origin: ${SITE_ORIGIN}" \
  "${API_BASE}/api/crm/account/personal-shopper/live?email=$(printf %s "$EMAIL" | sed 's/@/%40/')" || echo "000")
echo "  HTTP $HTTP"
echo "  Corps : $(cat /tmp/diag_body.json 2>/dev/null | head -c 400)"
echo "  --- En-têtes CORS sur la réponse ---"
curl -s -D - -o /dev/null \
  -H "Origin: ${SITE_ORIGIN}" \
  "${API_BASE}/api/crm/account/personal-shopper/live?email=$(printf %s "$EMAIL" | sed 's/@/%40/')" \
  | grep -i "access-control\|http/" || warn "Aucun en-tête Access-Control (typique d'un 500 : le CORS saute)"
case "$HTTP" in
  500) err "500 confirmé → exception serveur (voir étape 3 pour la stacktrace)";;
  403) ok  "403 = gating normal (pas membre / pas de consent) — PAS un bug serveur";;
  404) warn "404 = email inconnu côté API";;
  200) ok  "200 = l'API répond ; le souci est peut-être déjà résolu / côté cache navigateur";;
  000) err "Pas de réponse (DNS/TLS/Caddy) — l'API n'est pas joignable de l'extérieur";;
  *)   warn "HTTP $HTTP inattendu";;
esac

# ----------------------------------------------------------------------------
step "2. CORS bien configuré dans l'API ? (variable d'env du conteneur)"
CORS=$(docker exec "$API_CONTAINER" printenv CORS_ORIGINS 2>/dev/null || echo "")
echo "  CORS_ORIGINS = ${CORS:-(vide → défaut localhost only !)}"
if echo "$CORS" | grep -q "vintiz.fr"; then
  ok "https://vintiz.fr présent dans CORS_ORIGINS"
else
  err "https://vintiz.fr ABSENT de CORS_ORIGINS → même un 200 serait bloqué par le navigateur"
  echo "     → Ajouter dans /opt/vintiz/.env :  CORS_ORIGINS=https://vintiz.fr,https://www.vintiz.fr,https://app.vintiz.fr"
fi
ENVI=$(docker exec "$API_CONTAINER" printenv ENVIRONMENT 2>/dev/null || echo "")
echo "  ENVIRONMENT = ${ENVI:-(non posé)}"

# ----------------------------------------------------------------------------
step "3. ⭐ LA VRAIE CAUSE — stacktrace du 500 dans les logs API"
echo "  (les 40 dernières lignes contenant une trace Python / 500)"
docker logs "$API_CONTAINER" --tail 400 2>&1 \
  | grep -iE "Traceback|Unhandled exception|Error|Exception|UndefinedColumn|psycopg|asyncpg|column .* does not exist|relation .* does not exist|personal-shopper/live" \
  | tail -40 || warn "Rien trouvé dans les 400 dernières lignes — relance la requête puis re-exécute ce script"

# ----------------------------------------------------------------------------
step "4. Migrations Alembic appliquées ? (cause #1 du 500 : colonne manquante)"
HEAD_DB=$(docker exec "$API_CONTAINER" python -m alembic current 2>/dev/null | grep -oE "[0-9]{4}" | head -1 || echo "?")
echo "  Migration courante en base : ${HEAD_DB:-inconnue}"
echo "  Migration attendue (code)  : 0053"
if [ "$HEAD_DB" = "0053" ]; then
  ok "Schéma à jour (0053)"
else
  err "Schéma EN RETARD (≠ 0053) → colonnes manquantes (gender_profile, exclude_from_taste, …) = 500"
  echo "     → FIX :  docker exec ${API_CONTAINER} python -m alembic upgrade head"
fi

# ----------------------------------------------------------------------------
step "5. Colonnes critiques réellement présentes en base ?"
check_col() {
  local table="$1" col="$2"
  local present
  present=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT 1 FROM information_schema.columns WHERE table_name='${table}' AND column_name='${col}';" 2>/dev/null)
  if [ "$present" = "1" ]; then ok "${table}.${col}"; else err "${table}.${col} MANQUANTE (→ 500 sur le live feed)"; fi
}
check_col clients gender_profile
check_col clients age_band
check_col clients season_bias
check_col transactions is_gift
check_col transactions exclude_from_taste

# ----------------------------------------------------------------------------
step "6. Reproduire l'appel À L'INTÉRIEUR (stacktrace complète, hors masquage prod)"
docker exec "$API_CONTAINER" python - "$EMAIL" <<'PYEOF' 2>&1 | tail -30
import asyncio, sys, traceback
email = sys.argv[1].strip().lower()
async def main():
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.client import Client
    from app.services.personal_shopper import PersonalShopperService, PersonalShopperGatedError
    async with AsyncSessionLocal() as db:
        c = (await db.execute(select(Client).where(Client.email == email))).scalar_one_or_none()
        if c is None:
            print("[i] Aucun client pour", email, "(404 normal)"); return
        try:
            r = await PersonalShopperService(db).recommend(c.id, top_n=8)
            print("[OK] recommend a réussi — produits:", len(r.get("products", [])),
                  "| gated:", r.get("gated"), "| empty_state:", r.get("empty_state"))
        except PersonalShopperGatedError as e:
            print("[i] Gated (403 normal, PAS un 500):", e.reason)
        except Exception:
            print("[X] ⬇⬇⬇  C'EST LA CAUSE DU 500  ⬇⬇⬇")
            traceback.print_exc()
asyncio.run(main())
PYEOF

echo
echo "${C_BLU}=== RÉSUMÉ ===${C_NC}"
echo "  • 403 partout            → comportement normal (gating), le front doit afficher l'adhésion, pas 'Erreur réseau'."
echo "  • Colonne manquante / migration < 0053 → FIX: docker exec ${API_CONTAINER} python -m alembic upgrade head"
echo "  • CORS_ORIGINS sans vintiz.fr          → FIX: éditer /opt/vintiz/.env puis ./scripts/deploy.sh"
echo "  • Stacktrace à l'étape 3/6             → colle-la moi, je corrige le code."
