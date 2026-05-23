# Vintiz — Agent d'impression Raspberry Pi

Agent à installer sur une **Raspberry Pi** en boutique pour imprimer les
étiquettes produits Vintiz. Il remplace l'ancien pilotage direct de
l'imprimante Zebra (réseau / cloud / Bluetooth).

## Pourquoi un agent ?

L'API Vintiz tourne **hors site** (VPS) et ne peut pas ouvrir de connexion vers
une imprimante derrière le routeur de la boutique (NAT). On inverse donc le
sens : la Pi, posée en boutique, **interroge** l'API (connexion sortante
uniquement, sans redirection de port), récupère les étiquettes en attente et
les imprime sur l'imprimante qui lui est branchée, via **CUPS**.

```
   Vintiz API (cloud)                Raspberry Pi (boutique)        Imprimante
  ┌──────────────────┐   HTTPS sortant  ┌─────────────────┐   USB/LAN  ┌────────┐
  │ file d'étiquettes │◀───── poll ──────│  print_agent.py  │──── lp ───▶│ labels │
  │  (PDF rendu)      │── jobs + PDF ───▶│   (CUPS client)  │            └────────┘
  └──────────────────┘◀──── ack ────────└─────────────────┘
```

* Le **serveur** rend l'étiquette en PDF (page exactement 25 × 52 mm @ 203 dpi).
* La **Pi** ne fait qu'imprimer ce PDF — n'importe quelle imprimante reconnue
  par CUPS convient (thermique étiquettes USB, imprimante réseau, …).

## Pré-requis

* Raspberry Pi (Pi 3 ou +) sous Raspberry Pi OS / Debian, avec accès Internet.
* Une imprimante d'étiquettes branchée (USB) ou joignable sur le LAN.
* Côté **serveur Vintiz** : la variable `RPI_AGENT_TOKEN` doit être posée
  (jeton partagé). Sans elle, les endpoints de l'agent renvoient `503`.
  Génération : `python3 -c "import secrets; print(secrets.token_hex(32))"`.

## Installation rapide

```bash
git clone https://github.com/juliengonde-5g/vintiz.git
cd vintiz/apps/print-agent
sudo ./install.sh
```

Le script installe CUPS + Python 3, copie l'agent dans `/opt/vintiz-print-agent/`,
installe le service systemd `vintiz-print-agent` et crée
`/etc/vintiz-print-agent.env` (à compléter).

### 1. Déclarer l'imprimante dans CUPS

```bash
sudo lpinfo -v                                   # repérer l'URI de l'imprimante
sudo lpadmin -p vintiz_labels -E -v "<URI>" -m everywhere
echo "test" | lp -d vintiz_labels                # vérifier l'impression
```

> `<URI>` ressemble à `usb://Zebra/…` ou `socket://192.168.1.51:9100`.
> Pour une imprimante thermique d'étiquettes, configurez le format média
> (`Custom.25x52mm`) dans l'admin CUPS (`http://<pi>:631`) ou via
> `lpadmin -o media=Custom.25x52mm`.

### 2. Configurer l'agent

```bash
sudo nano /etc/vintiz-print-agent.env
```

| Variable          | Rôle                                                        |
|-------------------|-------------------------------------------------------------|
| `VINTIZ_API_URL`  | URL de l'API (ex. `https://app.vintiz.fr`)                  |
| `RPI_AGENT_TOKEN` | **doit être identique** au `RPI_AGENT_TOKEN` du serveur     |
| `CUPS_PRINTER`    | nom de la file CUPS (ex. `vintiz_labels`)                   |
| `POLL_INTERVAL`   | secondes entre deux interrogations (défaut 5)               |
| `LABEL_WIDTH_MM` / `LABEL_HEIGHT_MM` | taille média (`lp -o media=Custom.WxHmm`) |

### 3. Démarrer

```bash
sudo systemctl restart vintiz-print-agent
sudo systemctl status  vintiz-print-agent
journalctl -u vintiz-print-agent -f          # logs en direct
```

Dès le premier passage, l'imprimante apparaît **« en ligne »** dans Vintiz
(`/settings > Materiel`) et le bouton « Imprimer une étiquette de test » envoie
une étiquette dans la file.

## Fonctionnement

* L'agent appelle `GET /api/labels/agent/jobs/next` (en-tête `X-Agent-Token`),
  imprime chaque PDF reçu via `lp`, puis acquitte avec
  `POST /api/labels/agent/jobs/{id}/ack`.
* `copies` est intégré au PDF (une page par étiquette) — pas d'option `-n`.
* **Reprise sur panne** : un job pris en charge mais non acquitté (coupure de
  courant) est automatiquement remis en file côté serveur après
  `RPI_AGENT_STALE_SECONDS` (défaut 120 s).
* Aucune dépendance pip : uniquement la bibliothèque standard Python + CUPS.

## Dépannage

| Symptôme | Piste |
|---|---|
| `Agent désactivé côté serveur (503)` | Poser `RPI_AGENT_TOKEN` côté serveur et redéployer. |
| `Jeton agent refusé (401)` | Le token de la Pi ≠ celui du serveur. |
| `commande 'lp' introuvable` | `sudo apt-get install cups-client`. |
| Rien ne sort de l'imprimante | `lpstat -p` (imprimante prête ?), `echo test \| lp -d <nom>`, vérifier le format média. |
| « hors ligne » dans Vintiz | l'agent ne poll plus : `systemctl status`, `journalctl -u vintiz-print-agent`. |
| Mise à jour de l'agent | `git pull` puis `sudo ./install.sh` (config préservée) et `sudo systemctl restart vintiz-print-agent`. |

## Test manuel (sans systemd)

```bash
VINTIZ_API_URL=https://app.vintiz.fr \
RPI_AGENT_TOKEN=<token> \
CUPS_PRINTER=vintiz_labels \
python3 print_agent.py
```
