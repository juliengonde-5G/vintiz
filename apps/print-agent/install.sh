#!/usr/bin/env bash
#
# Vintiz label print agent — one-shot installer for Raspberry Pi (Raspberry Pi
# OS / Debian). Installs CUPS, the agent, and a systemd service.
#
# Usage (on the Pi):
#   git clone https://github.com/juliengonde-5g/vintiz.git
#   cd vintiz/apps/print-agent
#   sudo ./install.sh
#
# Re-running is safe (idempotent). It will NOT overwrite an existing
# /etc/vintiz-print-agent.env so your token/printer config is preserved.

set -euo pipefail

INSTALL_DIR="/opt/vintiz-print-agent"
ENV_FILE="/etc/vintiz-print-agent.env"
SERVICE="vintiz-print-agent.service"
AGENT_USER="vintiz-agent"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Ce script doit être lancé avec sudo (root)." >&2
  exit 1
fi

echo "==> Installation des paquets (CUPS + Python3)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends cups cups-client python3 >/dev/null

echo "==> Création de l'utilisateur de service '${AGENT_USER}' (groupe lp)…"
if ! id "${AGENT_USER}" >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin --groups lp "${AGENT_USER}"
else
  usermod -aG lp "${AGENT_USER}"
fi

echo "==> Copie de l'agent dans ${INSTALL_DIR}…"
install -d -m 0755 "${INSTALL_DIR}"
install -m 0755 "${SRC_DIR}/print_agent.py" "${INSTALL_DIR}/print_agent.py"

echo "==> Installation du service systemd…"
install -m 0644 "${SRC_DIR}/${SERVICE}" "/etc/systemd/system/${SERVICE}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "==> Création de ${ENV_FILE} (à compléter !)…"
  install -m 0640 "${SRC_DIR}/.env.example" "${ENV_FILE}"
  chgrp "${AGENT_USER}" "${ENV_FILE}" || true
else
  echo "==> ${ENV_FILE} existe déjà — conservé tel quel."
fi

systemctl daemon-reload
systemctl enable "${SERVICE}" >/dev/null

cat <<EOF

============================================================
Agent Vintiz installé.

PROCHAINES ÉTAPES :

1. Branchez l'imprimante d'étiquettes et déclarez-la dans CUPS, p. ex. :
     sudo lpinfo -v                       # repérer l'URI (usb://… ou socket://IP)
     sudo lpadmin -p vintiz_labels -E -v "<URI>" -m everywhere
     sudo lpoptions -d vintiz_labels      # (optionnel) imprimante par défaut
   Vérifiez : echo test | lp -d vintiz_labels

2. Renseignez la configuration :
     sudo nano ${ENV_FILE}
   -> VINTIZ_API_URL, RPI_AGENT_TOKEN (= celui du serveur), CUPS_PRINTER

3. Démarrez l'agent :
     sudo systemctl restart ${SERVICE}
     sudo systemctl status  ${SERVICE}
     journalctl -u ${SERVICE} -f      # suivre les logs en direct

L'imprimante apparaîtra "en ligne" dans Vintiz (/settings > Materiel) dès le
premier passage de l'agent.
============================================================
EOF
