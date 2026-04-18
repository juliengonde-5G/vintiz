#!/usr/bin/env bash
# Configure les identifiants Google Analytics dans apps/site/.env
#
# Usage :
#   ./scripts/setup_ga.sh                       # mode interactif
#   ./scripts/setup_ga.sh G-XXXXXXXXXX          # GA_ID uniquement
#   ./scripts/setup_ga.sh G-XXXXXXXXXX <token>  # GA_ID + Search Console
#
# Idempotent : relance sans doublon, remplace la valeur existante.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/apps/site/.env"
ENV_EXAMPLE="$ROOT/apps/site/.env.example"

GA_ID="${1:-}"
GSC_TOKEN="${2:-}"

if [[ -z "$GA_ID" ]]; then
  read -rp "Google Analytics ID (format G-XXXXXXXXXX) : " GA_ID
fi

if [[ -z "$GSC_TOKEN" && -t 0 ]]; then
  read -rp "Google Search Console token (optionnel, Entrée pour passer) : " GSC_TOKEN
fi

if [[ ! "$GA_ID" =~ ^G-[A-Z0-9]+$ ]]; then
  echo "Erreur : GA_ID doit être au format G-XXXXXXXXXX (reçu: '$GA_ID')" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Créé $ENV_FILE depuis .env.example"
fi

upsert() {
  local key="$1" value="$2" file="$3"
  if grep -q "^${key}=" "$file"; then
    # BSD/GNU sed compatible : passe par un fichier temporaire
    local tmp
    tmp="$(mktemp)"
    awk -v k="$key" -v v="$value" -F= '
      $1 == k { print k "=" v; next }
      { print }
    ' "$file" > "$tmp"
    mv "$tmp" "$file"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$file"
  fi
}

upsert "NEXT_PUBLIC_GA_ID" "$GA_ID" "$ENV_FILE"
if [[ -n "$GSC_TOKEN" ]]; then
  upsert "NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION" "$GSC_TOKEN" "$ENV_FILE"
fi

echo "OK — $ENV_FILE mis à jour :"
grep -E '^NEXT_PUBLIC_(GA_ID|GOOGLE_SITE_VERIFICATION)=' "$ENV_FILE"
