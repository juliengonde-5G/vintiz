# Impression d'étiquettes — Agent Raspberry Pi

Remplace l'ancien pilotage direct de l'imprimante Zebra ZD421d (transports
réseau / cloud Weblink / Bluetooth, tous retirés). L'impression des étiquettes
passe désormais par une **Raspberry Pi** en boutique qui imprime via **CUPS**.

## Pourquoi

L'API Vintiz tourne **hors site** (VPS) et ne peut pas joindre une imprimante
sur le LAN de la boutique (NAT du routeur). Plutôt que de pousser vers
l'imprimante, on **inverse le flux** : la Pi interroge l'API (HTTPS sortant,
sans redirection de port), récupère les étiquettes en attente et les imprime.

```
   API Vintiz (cloud)                 Raspberry Pi (boutique)        Imprimante
  ┌───────────────────┐  HTTPS sortant  ┌──────────────────┐  USB/LAN  ┌────────┐
  │ file label_print  │◀───── poll ──────│  print_agent.py   │─── lp ───▶│ labels │
  │  jobs (PDF rendu)  │── jobs + PDF ───▶│  (client CUPS)    │           └────────┘
  └───────────────────┘◀──── ack ────────└──────────────────┘
```

## Architecture logicielle

| Couche | Fichier | Rôle |
|---|---|---|
| Rendu étiquette | `apps/api/app/services/label_render.py` | Rend le tag 25×52 mm en **PNG** (aperçu) et **PDF** (impression, page exactement 25×52 mm @ 203 dpi). Source unique de mise en page. |
| File d'attente | `apps/api/app/models/label_job.py` + `app/services/label_queue.py` | Table `label_print_jobs` : enqueue / claim / ack / heartbeat / status. |
| API étiquettes | `apps/api/app/api/labels/router.py` | Endpoints manager (preview, enqueue, statut, planche A4) + endpoints **agent** (token). |
| Agent Pi | `apps/print-agent/` | Script Python (stdlib seule) + service systemd + installeur. |

## Endpoints

**Manager (JWT) :**

| Méthode | Endpoint | Rôle |
|---|---|---|
| POST | `/api/labels/print/{product_id}` | Met une étiquette produit en file (202). |
| POST | `/api/labels/print/batch` | Met N étiquettes en file. |
| POST | `/api/labels/test-print` | Met une étiquette de test en file. |
| GET | `/api/labels/preview/{product_id}` | Aperçu PNG (rendu serveur). |
| GET | `/api/labels/printer/status` | Statut agent : en ligne, file, dernier contact. |
| GET | `/api/labels/sheet?ids=…` | Mode dégradé : planche A4 HTML (impression navigateur). |

**Agent (en-tête `X-Agent-Token`) :**

| Méthode | Endpoint | Rôle |
|---|---|---|
| GET | `/api/labels/agent/jobs/next?max=N` | Réclame jusqu'à N jobs ; renvoie le PDF base64 + `copies`. |
| POST | `/api/labels/agent/jobs/{id}/ack` | Acquitte (`{success, error?}`). |

## Configuration serveur

```env
RPI_AGENT_TOKEN=            # secret partagé avec la Pi (vide ⇒ endpoints agent en 503)
RPI_AGENT_STALE_SECONDS=120 # délai sans poll avant "hors ligne"
RPI_CUPS_PRINTER_NAME=      # indicatif (affiché en /settings > Materiel)
```

Générer le token : `python3 -c "import secrets; print(secrets.token_hex(32))"`.

## Mise en service de la Pi

Voir **`apps/print-agent/README.md`** pour la procédure complète. En bref :

```bash
git clone https://github.com/juliengonde-5g/vintiz.git
cd vintiz/apps/print-agent && sudo ./install.sh
# 1) déclarer l'imprimante dans CUPS (lpadmin)
# 2) remplir /etc/vintiz-print-agent.env (URL + RPI_AGENT_TOKEN + CUPS_PRINTER)
# 3) sudo systemctl restart vintiz-print-agent
```

## Robustesse

* **Derrière NAT** : la Pi n'ouvre que des connexions sortantes — aucun port à
  ouvrir sur la box.
* **Reprise sur panne** : un job réclamé mais non acquitté (coupure courant) est
  automatiquement remis en file après `RPI_AGENT_STALE_SECONDS`.
* **Contenu figé** : le texte de l'étiquette (réf, nom, semaine) est snapshotté
  à la mise en file — l'étiquette imprimée correspond à ce que le manager a vu,
  même si le produit change ensuite.
* **Mode dégradé** : si la Pi est en panne, `GET /api/labels/sheet` génère une
  planche A4 imprimable depuis le navigateur sur n'importe quelle imprimante.
* **Imprimante agnostique** : tout périphérique reconnu par CUPS convient
  (thermique étiquettes USB, imprimante réseau…).
