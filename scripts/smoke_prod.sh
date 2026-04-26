#!/bin/bash
# =============================================================================
# Vintiz — Smoke test post-deploy
#
# Validation rapide qu'un déploiement Phase 4 est sain. Read-only :
# le script ne crée AUCUNE donnée en prod, n'envoie aucun email réel,
# ne déclenche pas de cron. Il vérifie juste que les endpoints répondent
# et qu'OpenAPI expose bien les routes attendues.
#
# Usage:
#   bash scripts/smoke_prod.sh                     # défaut: http://localhost:8000
#   bash scripts/smoke_prod.sh https://api.vintiz.fr
#
# Pour les checks authentifiés (réservations + coupons + reports), poser
# un token manager :
#   export VINTIZ_API_TOKEN="eyJhbGciOi..."
#   bash scripts/smoke_prod.sh https://api.vintiz.fr
#
# Génération du token (depuis la machine de Camille) :
#   curl -s -X POST https://api.vintiz.fr/api/auth/login \
#     -H 'content-type: application/json' \
#     -d '{"username":"admin","password":"vintiz2026"}' | jq -r .access_token
# =============================================================================

set -u  # unset var = erreur explicite ; on ne met pas -e car on veut continuer après une fail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}[OK]${NC}  $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}[KO]${NC}  $1"; FAIL=$((FAIL + 1)); }
warn() { echo -e "  ${YELLOW}[!!]${NC}  $1"; SKIP=$((SKIP + 1)); }
info() { echo -e "  ${BLUE}[..]${NC}  $1"; }

PASS=0; FAIL=0; SKIP=0

API_URL="${1:-http://localhost:8000}"
API_URL="${API_URL%/}"   # trim trailing slash

echo "════════════════════════════════════════════════════════"
echo "  Vintiz — Smoke test  $(date '+%Y-%m-%d %H:%M:%S')"
echo "  API : $API_URL"
echo "  Token : $([ -n "${VINTIZ_API_TOKEN:-}" ] && echo 'fourni' || echo 'absent — checks auth seront skip')"
echo "════════════════════════════════════════════════════════"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# curl wrapper qui imprime le code HTTP. Stocke le body dans /tmp/smoke_body.
http_get() {
  local path="$1"
  local headers=("-H" "accept: application/json")
  if [ -n "${VINTIZ_API_TOKEN:-}" ]; then
    headers+=("-H" "authorization: Bearer ${VINTIZ_API_TOKEN}")
  fi
  curl -s -o /tmp/smoke_body -w '%{http_code}' --max-time 10 "${headers[@]}" "$API_URL$path"
}

http_get_anon() {
  local path="$1"
  curl -s -o /tmp/smoke_body -w '%{http_code}' --max-time 10 \
    -H 'accept: application/json' \
    "$API_URL$path"
}

needs_token() {
  if [ -z "${VINTIZ_API_TOKEN:-}" ]; then
    warn "$1 (skip — VINTIZ_API_TOKEN absent)"
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# 1. Liveness
# ---------------------------------------------------------------------------

echo ""
echo "── 1. Liveness ──────────────────────────────────────────"
code=$(http_get_anon "/health")
if [ "$code" = "200" ]; then
  ok "/health → 200"
else
  fail "/health → $code (attendu 200) — l'API est down ou l'URL est fausse, on stoppe."
  echo ""
  echo "════════════════════════════════════════════════════════"
  echo "  Résultat : $PASS OK, $FAIL KO, $SKIP skip"
  echo "════════════════════════════════════════════════════════"
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. OpenAPI : vérifie que les routes Phase 4 sont bien câblées
# ---------------------------------------------------------------------------

echo ""
echo "── 2. OpenAPI — routes Phase 4 ──────────────────────────"
code=$(http_get_anon "/openapi.json")
if [ "$code" = "200" ]; then
  ok "/openapi.json → 200"
  EXPECTED_PATHS=(
    "/api/reports/retail-kpis"
    "/api/reports/ess"
    "/api/admin/kpis-config"
    "/api/admin/rfm/run"
    "/api/admin/anniversary/run"
    "/api/admin/new-arrivals/run"
    "/api/admin/coupons"
    "/api/crm/segments"
    "/api/crm/account/wallet"
    "/api/reservations"
    "/api/reservations/lookup"
    "/api/pos/coupons/validate"
  )
  for p in "${EXPECTED_PATHS[@]}"; do
    if grep -q "\"$p\"" /tmp/smoke_body; then
      ok "  route exposée : $p"
    else
      fail "  route MANQUANTE : $p"
    fi
  done
  # Sanity sur les routes paramétriques (présence du préfixe seulement)
  for p in "/api/inventory/products/" "/api/pos/products/" "/api/reservations/"; do
    if grep -q "\"$p" /tmp/smoke_body; then
      ok "  préfixe paramétrique présent : ${p}…"
    else
      fail "  préfixe MANQUANT : ${p}…"
    fi
  done
else
  fail "/openapi.json → $code"
fi

# ---------------------------------------------------------------------------
# 3. Endpoints publics (pas de token requis)
# ---------------------------------------------------------------------------

echo ""
echo "── 3. Endpoints publics ─────────────────────────────────"

# 404 attendu sur lookup d'un email qui n'existe pas — confirme que la
# route est branchée à la DB (vs 500 = DB cassée).
code=$(http_get_anon "/api/crm/clients/lookup?email=smoke-no-such@vintiz.fr")
if [ "$code" = "404" ]; then
  ok "/api/crm/clients/lookup (email inconnu) → 404"
elif [ "$code" = "400" ]; then
  ok "/api/crm/clients/lookup (email inconnu) → 400 (validation)"
else
  fail "/api/crm/clients/lookup → $code (attendu 404)"
fi

code=$(http_get_anon "/api/reservations/lookup?email=smoke-no-such@vintiz.fr")
if [ "$code" = "404" ]; then
  ok "/api/reservations/lookup (email inconnu) → 404"
else
  fail "/api/reservations/lookup → $code (attendu 404)"
fi

code=$(http_get_anon "/api/crm/account/wallet?email=smoke-no-such@vintiz.fr")
if [ "$code" = "404" ]; then
  ok "/api/crm/account/wallet (email inconnu) → 404"
else
  fail "/api/crm/account/wallet → $code (attendu 404)"
fi

# ---------------------------------------------------------------------------
# 4. Endpoints manager (auth requise)
# ---------------------------------------------------------------------------

echo ""
echo "── 4. Endpoints authentifiés (manager) ──────────────────"

if needs_token "checks manager"; then
  code=$(http_get "/api/reports/retail-kpis?period_days=30")
  if [ "$code" = "200" ]; then
    ok "/api/reports/retail-kpis → 200"
    if command -v jq >/dev/null 2>&1; then
      revenue=$(jq -r '.revenue // "?"' < /tmp/smoke_body)
      info "    revenue (30j) = $revenue €"
    fi
  else
    fail "/api/reports/retail-kpis → $code"
  fi

  code=$(http_get "/api/reports/ess?period_days=90")
  if [ "$code" = "200" ]; then
    ok "/api/reports/ess → 200"
  else
    fail "/api/reports/ess → $code"
  fi

  code=$(http_get "/api/admin/kpis-config")
  if [ "$code" = "200" ]; then
    ok "/api/admin/kpis-config → 200"
  else
    fail "/api/admin/kpis-config → $code"
  fi

  code=$(http_get "/api/crm/segments")
  if [ "$code" = "200" ]; then
    ok "/api/crm/segments → 200"
    if command -v jq >/dev/null 2>&1; then
      total=$(jq -r '.total_segmented // "?"' < /tmp/smoke_body)
      info "    total clientes segmentées = $total (0 = la cron RFM n'a pas encore tourné)"
    fi
  else
    fail "/api/crm/segments → $code"
  fi

  code=$(http_get "/api/admin/coupons?only_active=true")
  if [ "$code" = "200" ]; then
    ok "/api/admin/coupons → 200"
  else
    fail "/api/admin/coupons → $code"
  fi

  code=$(http_get "/api/reservations?only_active=true")
  if [ "$code" = "200" ]; then
    ok "/api/reservations → 200"
  else
    fail "/api/reservations → $code"
  fi
fi

# ---------------------------------------------------------------------------
# 5. Étapes manuelles — instructions
# ---------------------------------------------------------------------------

echo ""
echo "── 5. À tester manuellement (création de données) ───────"
cat <<EOF
  Les checks ci-dessous créent des données et ne sont PAS automatisés
  pour éviter de polluer la prod. À faire depuis l'interface :

  ${YELLOW}a. Réservation → encaissement${NC}
     1. /reservations → créer un hold sur un produit pour une cliente test
     2. POS → sélectionner la même cliente, scanner le produit
     3. Vérifier le bandeau vert "Réservation pour cette cliente"
     4. Encaisser ; le hold doit passer en 'redeemed'
        SELECT status, redeemed_transaction_id FROM reservations
        ORDER BY created_at DESC LIMIT 1;

  ${YELLOW}b. Coupon anniversaire${NC}
     1. POST /api/admin/anniversary/run (déclenche la cron à la demande)
     2. Vérifier qu'un coupon ANNIV-XXXXXX existe pour les clientes nées aujourd'hui
        SELECT code, valid_until FROM coupons WHERE source='anniversary'
        ORDER BY created_at DESC LIMIT 5;
     3. POS → appliquer le code → vérifier le pill et le total

  ${YELLOW}c. Crons APScheduler${NC}
     Au boot de l'API, les logs doivent lister :
       monthly_scoring, daily_rgpd_purge, daily_embedding_refresh,
       nightly_markdown_engine, daily_return_to_sorting,
       weekly_window_display, weekly_social_posts, daily_seo_snapshot,
       monthly_rfm_segmentation, daily_anniversary_emails,
       weekly_new_arrivals_emails, hourly_reservation_expiry
     soit 12 jobs.

EOF

# ---------------------------------------------------------------------------
# Résultat
# ---------------------------------------------------------------------------

echo "════════════════════════════════════════════════════════"
echo "  Résultat : ${GREEN}$PASS OK${NC}, ${RED}$FAIL KO${NC}, ${YELLOW}$SKIP skip${NC}"
echo "════════════════════════════════════════════════════════"

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
