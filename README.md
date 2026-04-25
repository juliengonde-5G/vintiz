# Vintiz

Logiciel de gestion pour boutique de seconde main premium — Vernon, Normandie.

Application complète : caisse iPad, gestion d'inventaire, CRM, IA assistante,
matériel ESC/POS / SATO / SumUp, site vitrine SEO + GA4, espace client, cahier
de travail journalier.

## Documentation

| Fichier | Pour qui |
|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | Dev — guide complet (stack, env, endpoints, hardware) |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | Dev — diagramme + flux applicatif |
| [`docs/DEPLOIEMENT.md`](./docs/DEPLOIEMENT.md) | Ops — VPS, Caddy, GitHub Action |
| [`docs/AUDIT_2026_04.md`](./docs/AUDIT_2026_04.md) | Dev — audit sécurité / code / UX d'avril 2026 |
| [`docs/DESIGN_SYSTEM.md`](./docs/DESIGN_SYSTEM.md) | Design — palette, fonts, logos, règles |
| [`docs/UX_DESIGN.md`](./docs/UX_DESIGN.md) | Design — heuristiques, parcours, états |
| [`docs/MANUEL_BOUTIQUE.md`](./docs/MANUEL_BOUTIQUE.md) | Manager / vendeur — guide d'utilisation |
| [`docs/POS_TEST_BARCODES.md`](./docs/POS_TEST_BARCODES.md) | Mise en service hardware — codes-barres scannables |
| [`docs/PREDICTIVE_ENGINE.md`](./docs/PREDICTIVE_ENGINE.md) | Dev — moteur prédictif Cahier de Travail |
| [`docs/CHANGELOG.md`](./docs/CHANGELOG.md) | Tous — historique des versions |

## Structure du projet

```
apps/
  api/          FastAPI (Python 3.11) — API REST + IA + hardware
  web/          Next.js 14 — Interface d'administration (back-office)
  site/         Next.js 14 — Site vitrine public + espace client
docker/         Dockerfiles + docker-compose{,-prod}.yml + Caddyfile
scripts/        seed_data.py, seed_test_products.py, deploy.sh, diag.sh, reset-prod.sh
docs/           Documentation technique et utilisateur
.github/        Workflow auto-deploy (deploy.yml)
.claude/        Hooks Claude Code (session-start) + settings.json
```

## Démarrage

### Développement local

```bash
# PostgreSQL (Ubuntu)
pg_ctlcluster 16 main start

# API
cd apps/api && pip install -r requirements.txt
PYTHONPATH=apps/api uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Admin UI
cd apps/web && npm install && npm run dev        # :3000

# Site vitrine
cd apps/site && npm install && npm run dev       # :3001

# Données de test (300 produits + 50 clients + 200 transactions)
PYTHONPATH=apps/api python scripts/seed_data.py
```

Identifiants par défaut : `admin` / `vintiz2026`

> Le hook `.claude/hooks/session-start.sh` détecte Docker vs local et démarre
> automatiquement PostgreSQL + l'API quand tu ouvres une session Claude Code
> sur le repo.

### Production (VPS)

Push sur `main` → la GitHub Action `Deploy Production` exécute
`./scripts/deploy.sh` sur le VPS via SSH.

```bash
# Manuel sur le VPS si besoin
cd /opt/vintiz
git pull origin main
./scripts/deploy.sh                      # rebuild + smoke tests
./scripts/deploy.sh --first-run          # + migrations + seed initial
./scripts/deploy.sh --test-products      # + seed_test_products (15 articles avec barcodes)
bash scripts/diag.sh                     # diagnostic auto (Docker/local, PG, API)
```

## Architecture de production

Tous les services tournent en Docker Compose sur le VPS (`/opt/vintiz`).
Caddy assure le reverse-proxy HTTPS sur les ports 80/443.

| Service        | Technologie          | Accès                     |
|----------------|----------------------|---------------------------|
| `vintiz-api`   | FastAPI Python 3.11  | interne :8000 (via Caddy) |
| `vintiz-db`    | PostgreSQL 16        | interne :5432             |
| `vintiz-web`   | Next.js 14           | interne :3000 (via Caddy) |
| `vintiz-site`  | Next.js 14           | interne :3001 (via Caddy) |
| `vintiz-caddy` | Caddy 2              | public :80 :443           |
| `vintiz-redis` | Redis 7              | interne :6379             |

> **Note** : le port 8000 n'est pas exposé à l'hôte. Pour tester l'API depuis
> le VPS : `docker exec vintiz-api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"`.

## Variables d'environnement

Fichier `.env` à la racine du projet (copier depuis `.env.example`). Voir
[`CLAUDE.md` § Variables d'environnement](./CLAUDE.md#variables-denvironnement)
pour la liste complète. Les nouvelles variables introduites en avril 2026 :

```env
ENVIRONMENT=production              # refus de boot si SECRET_KEY absente
SECRET_KEY=...                      # 32+ chars (openssl rand -hex 32)
ADMIN_BOOTSTRAP_KEY=...             # /admin/create-tables
LOG_LEVEL=INFO
LOG_JSON=true                       # pour Loki / Datadog
LOGIN_RATE_LIMIT_ATTEMPTS=10
LOGIN_RATE_LIMIT_WINDOW_SECONDS=300
PUBLIC_SITE_URL=https://vintiz.fr
GA_MEASUREMENT_ID=G-XXXXXXXXXX
GOOGLE_SITE_VERIFICATION=...
RECEIPT_PRINTER_HOST=192.168.1.50   # MUNBYN 047P-WiFi
LABEL_PRINTER_HOST=192.168.1.51     # SATO CT4-LX
```

## Hardware supporté

| Périphérique | Modèle | Connexion |
|---|---|---|
| Tablette caisse | iPad (Safari) | — |
| Douchette code-barres | Inateck BCST-35 ou 160B | USB HID |
| Imprimante ticket | **MUNBYN 047P-WiFi** ESC/POS 80 mm | Wi-Fi (port 9100) |
| Imprimante étiquettes | **SATO CT4-LX** SBPL 4″ | Wi-Fi (port 9100) |
| Tiroir-caisse | **Safescan SD-4141** RJ-12 | Sur l'imprimante MUNBYN |
| TPE | **SumUp Solo** | Wi-Fi / compte SumUp |

Configuration via `/settings > Materiel` (back-office). Tests live disponibles
(impression test, kick tiroir).

## Diagnostic

```bash
bash scripts/diag.sh
```

Détecte automatiquement Docker vs local, vérifie PostgreSQL, l'API, les tables
et Caddy. Redémarre automatiquement ce qui ne répond pas.

## Tests

```bash
# Backend
cd apps/api && pytest                   # 11 tests dont 6 régression sécurité
ruff check apps/api/app                 # 0 erreur

# Frontend
cd apps/web  && npm run lint && npm run build
cd apps/site && npm run lint && npm run build
```

## Sécurité

Voir [`docs/AUDIT_2026_04.md`](./docs/AUDIT_2026_04.md) pour le rapport
complet (S1–S12). Implémenté : refus boot prod sans `SECRET_KEY`, rate-limit
login, sanitization erreurs SMTP/Twilio, security headers, logs JSON +
`request_id`.

## Licence

Propriétaire — Vintiz, Vernon, France.
