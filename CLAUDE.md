# Vintiz — Guide de développement

Boutique de seconde main premium — Vernon, Normandie.

## Architecture

Monorepo avec 3 applications :

```
apps/
  api/          FastAPI (Python 3.11) — API REST + services IA + hardware
  web/          Next.js 14 (App Router) — Interface d'administration
  site/         Next.js 14 — Site vitrine public + espace client
docker/
  docker-compose.yml          Stack dev local
  docker-compose.prod.yml     Stack prod (api + web + site + db + caddy + redis)
  Caddyfile                   Reverse-proxy HTTPS
scripts/
  seed_data.py                300 produits + 50 clients + 200 transactions
  seed_test_products.py       15 produits de test POS + codes-barres PNG
  deploy.sh                   Déploiement prod (rebuild + migrations + smoke tests)
  diag.sh                     Diagnostic auto Docker/local (PostgreSQL, API, tables)
  reset-prod.sh               Remise à zéro DB prod (idempotent, documenté)
  backup.sh                   Backup PostgreSQL
docs/
  ARCHITECTURE.md             Diagramme + flux applicatif
  AUDIT_2026_04.md            Audit sécurité / code / UX (avril 2026)
  CHANGELOG.md                Versions
  DEPLOIEMENT.md              VPS, Caddy, secrets, GitHub Action
  DESIGN_SYSTEM.md            Charte v2 (palette, fonts, logos, règles)
  POS_TEST_BARCODES.md        15 codes-barres scannables pour la douchette
  PREDICTIVE_ENGINE.md        Moteur prédictif (cahier de travail)
  MANUEL_BOUTIQUE.md          Guide utilisateur/manager
  UX_DESIGN.md                Brief design (heuristiques, parcours, états)
  test_barcodes/*.png         Barcodes Code 128 (régénérés par seed_test_products)
.github/workflows/
  deploy.yml                  Auto-deploy SSH sur push main
.claude/
  hooks/session-start.sh      Auto-démarrage PostgreSQL + API en dev
  settings.json               Config Claude Code
```

## Stack technique

| Couche | Technologie |
|---|---|
| API backend | FastAPI + SQLAlchemy async (PostgreSQL) |
| Auth | JWT (python-jose) — rate-limit 10 tentatives / 5 min / IP |
| Logs | `app/core/logging_config.py` — text ou JSON via `LOG_JSON`, `request_id` propagé |
| Sécurité | `SecurityHeadersMiddleware` (CSP, X-Frame-Options, Referrer-Policy…) + `RequestIdMiddleware` |
| IA | Anthropic Claude (claude-haiku-4-5) |
| Payment CB | SumUp API — 3 modes : production / sandbox / simulation |
| Email | SMTP standard (simulation si non configuré) |
| SMS | Twilio (simulation si non configuré) |
| Météo | OpenWeatherMap API |
| Admin UI | Next.js 14 App Router + Tailwind CSS |
| Site public | Next.js 14 App Router + Tailwind CSS — landing + SEO + GA4 |
| Barcode | python-barcode + Pillow (Code 128) |
| Imprimante ticket | **MUNBYN 047P-WiFi** ESC/POS 80 mm (réseau, port 9100) **ou** AirPrint via `window.print()` |
| Imprimante étiquettes | **SATO CT4-LX** SBPL 4″ thermique (réseau, port 9100) |
| Douchette | **Inateck BCST-35** USB HID (champ POS auto-focus) ou Inateck 160B |
| Tiroir-caisse | **Safescan SD-4141** RJ-12 kické par l'imprimante ESC/POS (`ESC p m`) |
| TPE | **SumUp Solo** Wi-Fi (push direct possible via `SUMUP_READER_ID`) |
| Reverse-proxy | Caddy 2 (HTTPS auto, ports 80/443) |
| Cache / rate-limit | Redis 7 (interne) |
| Déploiement | GitHub Actions → SSH → `scripts/deploy.sh` sur push `main` |

## Démarrage rapide

```bash
# 1. Variables d'environnement (backend)
cp apps/api/.env.example apps/api/.env
# Remplir DATABASE_URL, SECRET_KEY, ANTHROPIC_API_KEY

# 2. Backend
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. Admin UI
cd apps/web
npm install
npm run dev  # port 3000

# 4. Site vitrine
cd apps/site
npm install
npm run dev  # port 3001

# 5. Données de test
PYTHONPATH=apps/api python scripts/seed_data.py
# Crée: admin/vintiz2026, 300 produits, 50 clients, 200 transactions
```

## Variables d'environnement

```env
# Environnement (development | staging | production)
# En production, refus de boot si SECRET_KEY est absent ou égal au sentinel.
ENVIRONMENT=development

# Obligatoire
DATABASE_URL=postgresql+asyncpg://user:password@localhost/vintiz
# REQUIS en prod ; en dev, génération d'une clé éphémère + warning si vide.
SECRET_KEY=

# Bootstrap admin (n'utilise plus SECRET_KEY → endpoint /admin/create-tables)
ADMIN_BOOTSTRAP_KEY=

# Rate limit /auth/login (par IP)
LOGIN_RATE_LIMIT_ATTEMPTS=10
LOGIN_RATE_LIMIT_WINDOW_SECONDS=300

# Logging
LOG_LEVEL=INFO
LOG_JSON=false                    # true en prod pour Loki / Datadog

# IA (sans cette clé, fallback sur données statiques)
ANTHROPIC_API_KEY=sk-ant-...

# Météo Vernon (sans cette clé, widget météo indisponible)
OPENWEATHER_API_KEY=votre-cle-openweather

# CB SumUp — 3 modes
#   - production : SUMUP_ENVIRONMENT=production + clé + merchant code
#   - sandbox    : SUMUP_ENVIRONMENT=sandbox avec clé de dev
#   - simulation : pas de clé → sandbox en mémoire, event log + approve manuel
SUMUP_ENVIRONMENT=sandbox
SUMUP_API_KEY=
SUMUP_MERCHANT_CODE=
SUMUP_READER_ID=                  # optionnel: push direct vers un TPE Solo
SUMUP_RETURN_URL=                 # optionnel: callback après paiement reader
SUMUP_SANDBOX_AUTO_DELAY_SEC=5    # 0 = approbation manuelle requise

# Hardware (optionnel — sinon configurable via /settings > Materiel)
RECEIPT_PRINTER_HOST=             # IP de la MUNBYN 047P-WiFi
RECEIPT_PRINTER_PORT=9100
LABEL_PRINTER_HOST=               # IP de la SATO CT4-LX
LABEL_PRINTER_PORT=9100
VINTIZ_HARDWARE_CONFIG=           # chemin custom du fichier hardware.json (défaut: data/hardware.json)

# Email SMTP (sans ces clés, simulation)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=email@domaine.fr
SMTP_PASSWORD=mot-de-passe

# SMS Twilio (sans ces clés, simulation)
TWILIO_ACCOUNT_SID=ACxxxx
TWILIO_AUTH_TOKEN=token
TWILIO_FROM=+33xxxxxxxxx

# SEO / Analytics (site public)
PUBLIC_SITE_URL=https://vintiz.fr
GA_MEASUREMENT_ID=                # G-XXXXXXXXXX
GOOGLE_SITE_VERIFICATION=         # méta verification Search Console
GSC_PROPERTY=                     # propriété GSC pour smoke tests SEO

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3001
```

## Identifiants par défaut

| Utilisateur | Mot de passe | Rôle |
|---|---|---|
| admin | vintiz2026 | Manager |

## Structure API

Base URL: `http://localhost:8000`

| Module | Préfixe | Description |
|---|---|---|
| Auth | `/api/auth` | Login (rate-limit 10/5min), refresh token |
| Inventaire | `/api/inventory` | CRUD produits, étiquettes, score |
| POS | `/api/pos` | Transactions, caisse, CB SumUp |
| CRM | `/api/crm` | Clients, fidélité, personal shopper |
| IA Booster | `/api/ai` | Vision, checklist, tendances, personas |
| Admin | `/api/admin` | Météo, zones, scoring mensuel, bootstrap |
| Rapports | `/api/reports` | Dashboard, statistiques |
| **Hardware** | `/api/hardware` | Config péri (printer, drawer, scanner, label), tests |
| **Cahier** | `/api/cahier` | Cahier de travail journalier (objectifs, signatures) |
| **Newsletter** | `/api/newsletter` | Subscribe RGPD, unsubscribe 1-clic, export CSV |
| **SEO** | `/api/seo` | Smoke tests sitemap / robots / metas / OG / JSON-LD |

### Endpoints clés

```
# Auth
POST   /api/auth/login                       Connexion manager (username/password, 429 si rate-limit dépassé)
POST   /api/pos/cashier/login                Identifier le cashier au POS via PIN 4 chiffres
POST   /api/pos/cashier/set-pin              Définir/changer un PIN (manager only)
POST   /api/pos/cashier/clear-pin            Retirer un PIN (manager only)
GET    /api/pos/cashier/list                 Lister utilisateurs + statut PIN (manager only)

# Inventaire
GET    /api/inventory/products               Liste produits (paginée)
GET    /api/inventory/products/search?q=…    Recherche (filtre stock+display par défaut, &include_sold=true sinon)
GET    /api/inventory/products/{id}          Fiche produit
GET    /api/inventory/products/{id}/label    Étiquette PNG (ou impression SATO si configurée)
GET    /api/inventory/products/{id}/score    Score détaillé
GET    /api/inventory/products/{id}/photos   Liste multi-photos
POST   /api/inventory/products/{id}/photos   Ajouter une photo (url + AI fields)
POST   /api/inventory/products/{id}/photos/{pid}/primary  Définir la photo primaire
POST   /api/inventory/products/{id}/photos/reorder        Réordonner (drag/drop)
DELETE /api/inventory/products/{id}/photos/{pid}          Supprimer une photo
POST   /api/inventory/products/import-csv    Import en masse CSV (multipart, ?dry_run=true)
GET    /api/inventory/products/{id}/history  Historique mouvements (audit_logs)
POST   /api/inventory/products/{id}/transition  Transition cycle de vie produit (FSM)
POST   /api/inventory/batches                Créer un lot d'arrivage (carton)
GET    /api/inventory/batches                Liste des lots
GET    /api/inventory/batches/{id}           Détail lot + produits assignés
POST   /api/inventory/batches/{id}/assign-product  Rattacher produit au lot
GET    /api/inventory/products/{id}/suggest-zone   Reco placement zone (P2-006)
GET    /api/inventory/locate?q=              Localiser un produit en boutique (P2-008)

# POS — vente + caisse + ticket
POST   /api/pos/transactions                 Créer une vente (idempotent via client_uuid optionnel — replay offline safe)
POST   /api/pos/transactions/{id}/refund     Refund partiel/total (cash/card/cheque/avoir)
GET    /api/pos/transactions/{id}/receipt    Texte du ticket (80 mm)
POST   /api/pos/transactions/{id}/resend     Renvoyer ticket (email/SMS)
POST   /api/pos/drawer/open                  Ouvrir la caisse (fond initial)
POST   /api/pos/drawer/close                 Fermer + rapport Z
GET    /api/pos/drawer/current               État tiroir

# POS — CB SumUp
POST   /api/pos/payments/cb/initiate         Initier paiement SumUp
GET    /api/pos/payments/cb/{id}/status      Poller statut SumUp
DELETE /api/pos/payments/cb/{id}             Annuler checkout
GET    /api/pos/payments/cb/sandbox/config   Config SumUp (env, clés)
GET    /api/pos/payments/cb/sandbox/state    Event log sandbox (live)
POST   /api/pos/payments/cb/sandbox/{id}/approve  Valider manuellement
POST   /api/pos/payments/cb/sandbox/{id}/decline  Refuser manuellement

# Hardware (back-office /settings > Materiel)
GET    /api/hardware/compatibility           Liste matériel supporté
GET    /api/hardware/config                  Lire config persistée (data/hardware.json)
PUT    /api/hardware/config                  Modifier config (IP imprimante, kick pin…)
POST   /api/hardware/receipt/test            Imprimer un ticket de test (MUNBYN ESC/POS)
POST   /api/hardware/drawer/kick             Ouvrir tiroir (impulsion ESC p m via printer)
POST   /api/hardware/label/test              Imprimer étiquette de test (SATO SBPL)

# Cahier de travail (back-office /dashboard/cahier-du-jour)
GET    /api/cahier/{report_date}                Données cahier journalier (KPI + objectifs + IA)
GET    /api/cahier/monthly-target/{year}/{month} Objectif mensuel CA
PUT    /api/cahier/monthly-target               Saisir l'objectif mensuel
PUT    /api/cahier/daily-text                   Mettre à jour message/operation du jour
PUT    /api/cahier/signature                    Apposer signature (manager / equipe)
GET    /api/cahier/weekday-weights              Poids historiques des jours de la semaine

# Newsletter (RGPD)
POST   /api/newsletter/subscribe             Inscription (consentement explicite requis)
GET    /api/newsletter/unsubscribe?token=… 1-clic via token signé
GET    /api/newsletter/subscribers           Liste (admin)
GET    /api/newsletter/subscribers/export    Export CSV (admin)
DELETE /api/newsletter/subscribers/{id}      Suppression (admin, RGPD)

# SEO + Marketing
GET    /api/seo/status                       Smoke test sitemap / robots / metas (ext)
POST   /api/seo/snapshots/run                Lancer un snapshot SEO + persister
GET    /api/seo/snapshots?days=30            Historique snapshots SEO (manager only)
GET    /api/seo/social-posts/current         4 posts proposés cette semaine (manager only)
POST   /api/seo/social-posts/regenerate      Régénérer la sélection (Claude + fallback)
POST   /api/seo/social-posts/{id}/accept     Valider un post
GET    /api/seo/mentions                     Liste mentions Insta/TikTok (manager only)
POST   /api/seo/mentions                     Saisie manuelle d'une mention
GET    /api/seo/reviews                      Liste avis Google (manager only)
POST   /api/seo/reviews                      Saisie manuelle d'un avis
POST   /api/seo/reviews/{id}/suggest-reply   Brouillon de réponse Claude (avec fallback)
PUT    /api/seo/reviews/{id}/reply           Enregistrer la réponse

# Admin / IA / merchandising
GET    /api/admin/weather                    Météo Vernon
GET    /api/admin/audit-logs                 Journal AuditLog (manager only, filtres entity/action/user_id)
GET    /api/admin/fiscal-export?from=&to=&format=xml|json  Export fiscal NF525/DGFiP (manager only)
GET    /api/admin/data-quality?days=7        Volumes events_log + courbe (manager only)
POST   /api/admin/embeddings/recompute       Recalcul embeddings catalogue (manager only)
POST   /api/admin/embeddings/customer/{id}   Refresh taste profile cliente (manager only)
GET    /api/admin/return-to-sorting/preview  Dry-run retour automatique tri (manager only)
POST   /api/admin/return-to-sorting/run      Trigger manuel retour automatique (manager only)
GET    /api/admin/markdown-rules             Liste règles markdown (manager only)
POST   /api/admin/markdown-rules             Créer règle markdown (manager only, validation conditions+action)
PUT    /api/admin/markdown-rules/{id}        Modifier règle (manager only)
DELETE /api/admin/markdown-rules/{id}        Supprimer règle (manager only)
GET    /api/admin/markdown-rules/preview     Dry-run engine (manager only)
POST   /api/admin/markdown-rules/run         Trigger manuel engine (manager only)
GET    /api/admin/brand-tiers                Liste marques + tiers (manager only)
POST   /api/admin/brand-tiers                Créer marque (luxury/premium/mid/basic)
PUT    /api/admin/brand-tiers/{id}           Modifier marque (manager only)
DELETE /api/admin/brand-tiers/{id}           Supprimer marque (manager only)
GET    /api/admin/store-plan                 Plan zones + occupation + score moyen (manager only)
GET    /api/admin/window-display/current     Proposition vitrine semaine courante (manager only)
POST   /api/admin/window-display/regenerate  Régénérer la proposition (manager only)
POST   /api/admin/window-display/{id}/accept Valider la vitrine (manager only)

# IA Booster (Compagnon IA)
GET    /api/ai/weekly-checklist              Checklist semaine IA
GET    /api/ai/trends                        Tendances mode
POST   /api/ai/persona/marketing             Rapport marketing IA
POST   /api/ai/persona/juridique             Audit RGPD IA

# CRM clients + RGPD
GET    /api/crm/clients/lookup?email=…       Lookup client public
GET    /api/crm/clients/personal-shopper?email=…  Personal shopper v1 (legacy règles)
GET    /api/crm/clients/{id}/personal-shopper-v2  Personal shopper v2 (embeddings + Claude Haiku)
GET    /api/crm/personal-shopper-v2?email=        Personal shopper v2 public (lookup email)
POST   /api/crm/personal-shopper-v2/click         Log click sur recommandation
GET    /api/crm/onboarding/options                Catalogue styles/occasions/budgets (public)
POST   /api/crm/clients/{id}/onboarding           Cold-start taste profile (manager)
POST   /api/crm/account/onboarding                Cold-start taste profile (public, body: email + choix)
GET    /api/crm/clients/{id}/avoir                Solde + historique avoir (store credit)
GET    /api/crm/clients/{id}/consents              Consentements RGPD (état courant + historique)
POST   /api/crm/clients/{id}/consents              Enregistrer consentement (purpose+granted+source)
GET    /api/crm/clients/{id}/data-export           Export RGPD JSON portable (Article 20)
POST   /api/crm/clients/{id}/deletion-request      Demande suppression (soft, fenêtre 30j)
POST   /api/crm/clients/{id}/deletion-cancel       Annuler demande de suppression
GET    /api/crm/account/data-export?email=         Public — export RGPD JSON par email
POST   /api/crm/account/deletion-request           Public — demande suppression (body: email)
POST   /api/crm/account/deletion-cancel            Public — annuler suppression (body: email)
```

## Fonctionnalités principales

### 1. Inventaire
- Création produit avec génération automatique code-barres
- Fiche produit cliquable avec score détaillé (6 composantes)
- Date de mise en rayon, emplacement zone
- Édition inline prix / zone / statut
- Bouton "Générer étiquette" → PNG téléchargeable/imprimable

### 2. POS (Caisse) — prêt pour matériel
- Interface tactile compacte iPad 1024×768 (tout sur 1 écran sans scroll,
  jusqu'à 5-6 articles au panier avant scroll du panier)
- Champ recherche auto-focus, résultats filtrés (produits vendus/retournés exclus)
- **Douchette USB HID** (Inateck 160B) : scan → Entrée → ajout auto au panier
  (résolution via exact match sur `barcode`, fallback recherche 1 résultat)
- **Numpad tactile** pour saisies de montants (espèces, fond de caisse)
- Remises par article (0, 5, 10, 15, 20, 30 %) — masquées par défaut, chip `-%` pour les ouvrir
- 3 modes de paiement :
  - *Espèces* — rendu monnaie calculé, **ouverture auto du tiroir** à la validation
  - *CB SumUp* — TPE Solo + polling + approve/decline manuel ; si `SUMUP_READER_ID`
    configuré, push direct sur le TPE (sonne tout seul, pas de saisie TPE)
  - *Chèque* — saisie libre
- Fidélité : affichage points, toggle rachat (1 pt = 0,10 €, max 50 % panier)
- **Ouverture / fermeture caisse** : fond initial, clôture avec rapport Z
  (écart attendu vs compté, totaux par méthode)
- **Ticket à la demande** : après la vente, modal *Imprimer le ticket* /
  *Fermer sans ticket*. L'impression utilise `window.print()` AirPrint 80 mm ;
  l'imprimante thermique ouvre le tiroir via impulsion RJ11 (option driver
  "open drawer on print")
- Reçu renvoyable par email/SMS

### 3. IA Booster
- **Analyse photo** : Claude Vision détecte type, couleur, marque, état
- **Checklist hebdo** : recommandations actionnables (mise en avant, prix, vitrine)
- **Tendances mode** : social/Vinted/retail printemps-été 2026
- **Rapport marketing** : analyse boutique par persona manager
- **Audit RGPD** : conformité CNIL par persona juridique
- **Scoring automatique** : 6 composantes, automation 1er mercredi

### 4. Dashboard
- KPIs journaliers (CA, panier moyen, nb transactions)
- Widget météo Vernon (OpenWeatherMap)
- Tickets cliquables → modal détail + reprint/email/SMS

### 5. Cahier de travail (Cahier du Jour)
- Page `/dashboard/cahier-du-jour` — vue journalière manager
- Objectif CA mensuel, réparti par jour selon le **poids historique** des jours de la semaine
  (`GET /api/cahier/weekday-weights`, recalcul auto sur les N dernières semaines)
- KPI : progression cumul mois, reste à faire, comparatif N-1
- Champs libres : "message du jour", "opération en cours"
- Signatures manager / équipe (boutons `PUT /api/cahier/signature`)
- Voir `docs/PREDICTIVE_ENGINE.md` pour la logique de répartition

### 6. Paramétrage zones
- 7 zones prédéfinies (plan boutique L 98m²)
- Édition : nom, description, capacité, types de produits, couleur, photo, **objectif CA mensuel par zone**
- Plan 2D : positions (`pos_x`, `pos_y`, `width`, `height`, `shape`, `display_order`)
  pilotables visuellement (utilisé par `IA Booster > Mapping Boutique`)

### 7. Hardware (`/settings > Materiel`)
- Configuration persistée dans `apps/api/data/hardware.json`
- Onglets matériel : imprimante ticket / tiroir / imprimante étiquette / douchette / TPE
- Boutons de test live :
  - "Imprimer ticket test" (MUNBYN ESC/POS port 9100)
  - "Kicker tiroir" (impulsion `ESC p m`)
  - "Imprimer étiquette test" (SATO SBPL port 9100)
- Tableau de compatibilité avec annotations (`/api/hardware/compatibility`)
- Utilisable même en production : pas de redéploiement requis pour changer une IP

### 8. Newsletter (RGPD)
- Inscription côté site public avec **double consentement** (case à cocher + lien email)
- Token de désinscription signé → page `/desinscription` 1-clic
- Page admin `/newsletter` : recherche, filtres consentement, export CSV, suppression RGPD
- Stockage des consentements horodatés (`subscribed_at`, `consent_text_version`)

### 9. SEO + Analytics (site public)
- Landing `/` optimisée (Vintiz Vernon, seconde main premium)
- `sitemap.ts` + `robots.ts` Next.js dynamiques
- `<head>` : title, description, canonical, OG, Twitter, JSON-LD `Store`
- GA4 via `GA_MEASUREMENT_ID` injecté côté client
- Search Console : meta `google-site-verification`
- Smoke tests post-deploy : `GET /api/seo/status` vérifie l'externe (sitemap, metas)

### 10. Espace client (site public)
- Login par email (sans mot de passe — magic-link prévu cf. AUDIT S8)
- Carte fidélité (Bronze/Silver/Gold)
- Historique achats
- Personal Shopper IA : sélection personnalisée basée sur l'historique

## Design tokens (Tailwind)

Charte v2 (2026-04) — voir `docs/DESIGN_SYSTEM.md` pour le détail complet.

```css
teal:  #008678  (couleur signature — CTA, liens, actions primaires)
pink:  #FFC5DF  (accent — fidélité, badges, tags)
black: #000000  (texte structurel)
cream: #FFF3ED  (fond chaud — sert de background)
white: #FFFFFF  (cartes, surfaces)
```

Typographie : **Lexend Mega** (titres, `font-display`) + **Poppins** (texte,
`font-sans`), chargées via `next/font/google` dans les layouts.

Logos (copiés dans `apps/{web,site}/public/`) :

| Fichier | Usage |
|---|---|
| `/logo-teal.png` | Monogramme VL teal — logo par défaut (navbar, sidebar, login) |
| `/logo-rose.png` | Monogramme rose — fonds sombres (footer noir) |
| `/lettrage-noir.png` | Mot « VINTIZ » noir — factures, emails |
| `/receipt-logo.png` | Version ticket de caisse (forcée noir via CSS filter) |

## Moteur prédictif

Voir `docs/PREDICTIVE_ENGINE.md` pour la documentation détaillée.

## Tests et seed data

```bash
# Seeder 300 produits + 50 clients + 200 transactions
PYTHONPATH=apps/api python scripts/seed_data.py

# Le script est idempotent (peut être relancé sans dupliquer)
```

## Git workflow

Branches `main` (prod) + branches feature `claude/<sujet>-<suffix>`. Le push sur
`main` déclenche la GitHub Action `Deploy Production` → SSH → `scripts/deploy.sh`
sur le VPS (`/opt/vintiz`).

```bash
# Cycle type
git checkout -b claude/feature-xyz
# ... commits ...
git push -u origin claude/feature-xyz
gh pr create        # ou via mcp__github__create_pull_request
# revue + merge UI → auto-deploy
```

Voir `.github/workflows/deploy.yml` pour la config (secrets `VPS_HOST`,
`VPS_USER`, `VPS_SSH_KEY`, `VPS_PORT`). Concurrency group `production` :
deux pushs successifs s'enchaînent sans s'annuler.

## Sécurité

- **`SECRET_KEY`** obligatoire en prod (refus de boot, voir `app/core/config.py`).
  En dev, génération éphémère + warning si vide.
- **`ADMIN_BOOTSTRAP_KEY`** distinct pour `/admin/create-tables` (plus de réutilisation de `SECRET_KEY`).
- **Rate-limit login** : 10 tentatives / 5 min / IP. Reset au login réussi. (`app/core/rate_limit.py`)
- **Sanitization erreurs** : SMTP / Twilio / exceptions globales — détail générique côté client, full-trace côté serveur.
- **Headers** : `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`.
- **Logs JSON** + `request_id` corrélation client/serveur.
- Voir `docs/AUDIT_2026_04.md` pour le rapport complet (S1–S12).

## Tests

```bash
# Backend (11 tests, dont 6 régression sécurité)
cd apps/api && pytest

# Lint
ruff check apps/api/app

# Frontend
cd apps/web && npm run lint && npm run build
cd apps/site && npm run lint && npm run build
```

Les tests tournent contre SQLite (`sqlite+aiosqlite`) grâce au type portable
`JSONType` (`app/models/types.py = JSON().with_variant(JSONB, "postgresql")`).

## Hardware POS — mise en service

Matériel supporté :

| Composant | Référence testée | Connexion | Code |
|---|---|---|---|
| Tablette caisse | iPad (Safari) | — | — |
| Douchette code-barres | **Inateck BCST-35** ou **160B** | USB HID (clavier) | Auto-focus champ POS |
| Imprimante ticket | **MUNBYN 047P-WiFi** ESC/POS 80 mm | Réseau (port 9100) | `app/services/escpos_service.py` |
| Imprimante étiquettes | **SATO CT4-LX** SBPL 4″ | Réseau (port 9100) | `app/services/sato_service.py` |
| Tiroir-caisse | **Safescan SD-4141** RJ-12 | Branché sur imprimante (kick `ESC p m`) | inclus dans `escpos_service` |
| TPE | **SumUp Solo** | Wi-Fi / compte SumUp | `app/services/sumup_service.py` |

Deux modes d'impression ticket coexistent dans `apps/web/src/app/pos/page.tsx` :

1. **MUNBYN ESC/POS** (recommandé) — bouton *Imprimer (MUNBYN)* dans la modal de
   ticket. Appelle `POST /api/hardware/receipt/test` ou la version production
   liée à la transaction. Tiroir kické via la même connexion réseau.
2. **AirPrint via `window.print()`** (fallback) — bouton *Imprimer (AirPrint)*.
   Utilise le format 80 mm CSS-rendered. Tiroir kické si "open drawer on print"
   est activé sur le pilote AirPrint.

Procédure complète + 15 codes-barres scannables : `docs/POS_TEST_BARCODES.md`.

```bash
# 1. Configurer SumUp (dev local ou .env prod)
SUMUP_ENVIRONMENT=sandbox       # sandbox | production
SUMUP_API_KEY=                  # vide → simulation en mémoire
SUMUP_MERCHANT_CODE=
SUMUP_READER_ID=                # optionnel: push direct vers TPE Solo
SUMUP_SANDBOX_AUTO_DELAY_SEC=5  # 0 = approbation manuelle via Settings

# 2. Seeder les 15 produits de test + régénérer les PNG codes-barres
PYTHONPATH=apps/api python scripts/seed_test_products.py
# Régénérer juste la doc + les PNG sans toucher la DB :
python scripts/seed_test_products.py --docs-only

# 3. En prod (sur le VPS)
./scripts/deploy.sh --test-products
```

**Autoriser les pop-ups pour le domaine** sur l'iPad (Safari → Réglages →
Sites web → Fenêtres pop-up → Autoriser pour app.vintiz.fr) — sinon le
kick-tiroir automatique sur les paiements espèces sera bloqué (le bouton
*Imprimer le ticket* continuera de fonctionner car il provient d'un clic
direct).

**Récupérer un `SUMUP_READER_ID`** : une fois la clé API configurée,

```
GET https://api.sumup.com/v0.1/merchants/{MERCHANT_CODE}/readers
Authorization: Bearer <SUMUP_API_KEY>
```

Renvoie la liste des TPE enrôlés sur le compte. Le champ `id` du Solo
souhaité va dans `SUMUP_READER_ID`.

### Modes SumUp

- **production** — appels réels api.sumup.com, frais SumUp qui s'appliquent.
- **sandbox** — clé de dev SumUp, appels API réels en mode test.
- **simulation** (défaut sans clé) — sandbox en mémoire dans l'API. Event log
  visible dans `/settings > Paiement`, approve/decline manuel disponible, les
  checkouts PENDING passent auto en PAID après `SUMUP_SANDBOX_AUTO_DELAY_SEC`.
