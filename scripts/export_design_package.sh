#!/usr/bin/env bash
# scripts/export_design_package.sh
#
# Re-synchronise design-package/logos depuis apps/site/public, vérifie que
# le preset Tailwind reflète bien le tailwind.config.ts du site, et zippe
# l'arborescence en design-package.zip pour distribution externe.
#
# Idempotent — peut être relancé après chaque mise à jour de charte.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG="$ROOT/design-package"
SITE_PUBLIC="$ROOT/apps/site/public"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "→ Synchronisation logos depuis apps/site/public"
mkdir -p "$PKG/logos"
for asset in logo-teal logo-rose lettrage-noir lettrage-rose; do
  src="$SITE_PUBLIC/$asset.png"
  if [ -f "$src" ]; then
    cp "$src" "$PKG/logos/$asset.png"
    echo -e "  ${GREEN}✓${NC} $asset.png"
  else
    echo -e "  ${YELLOW}!${NC} $asset.png absent dans apps/site/public — skip"
  fi
done

echo "→ Vérification du preset Tailwind"
SITE_TEAL=$(grep -A1 "teal:" "$ROOT/apps/site/tailwind.config.ts" | grep "DEFAULT" | head -1 | grep -o '#[A-F0-9a-f]\{6\}' || true)
PKG_TEAL=$(grep '"DEFAULT": "#' "$PKG/tokens/colors.json" | head -1 | grep -o '#[A-F0-9a-f]\{6\}' || true)
if [ -n "$SITE_TEAL" ] && [ "$SITE_TEAL" != "$PKG_TEAL" ]; then
  echo -e "  ${YELLOW}!${NC} teal site=$SITE_TEAL ≠ pkg=$PKG_TEAL — mettre à jour tokens/colors.json"
else
  echo -e "  ${GREEN}✓${NC} teal aligné ($PKG_TEAL)"
fi

echo "→ Génération design-package.zip"
( cd "$ROOT" && zip -r -q design-package.zip design-package -x "*.DS_Store" )
SIZE=$(du -h "$ROOT/design-package.zip" | cut -f1)
echo -e "  ${GREEN}✓${NC} design-package.zip ($SIZE)"

echo ""
echo -e "${GREEN}Design package prêt :${NC} $ROOT/design-package/"
echo -e "${GREEN}Archive distribuable :${NC} $ROOT/design-package.zip"
