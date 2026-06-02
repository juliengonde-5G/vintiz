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
  purge_databases.py          Purge one-shot des données opérationnelles (--dry-run / --confirm)
  backup.sh                   Backup PostgreSQL
  smoke_prod.sh               Smoke-test post-deploy (read-only, OpenAPI + endpoints)
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
  ZEBRA_INSTALLATION.md       Mise en service Zebra ZD421d (réseau local + cloud Weblink)
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
| Payment CB | SumUp API — production uniquement (sandbox retiré pour la mise en prod boutique) |
| Email | SMTP standard (simulation si non configuré) |
| SMS | Twilio (simulation si non configuré) |
| Météo | OpenWeatherMap API |
| Admin UI | Next.js 14 App Router + Tailwind CSS |
| Site public | Next.js 14 App Router + Tailwind CSS — landing + SEO + GA4 |
| Barcode | python-barcode + Pillow (Code 128) |
| Imprimante ticket | **MUNBYN 047P** ESC/POS 80 mm — réseau (port 9100) **ou** USB-OTG via WebUSB sur tablette Android |
| Imprimante étiquettes | **Zebra ZD421d** ZPL II thermique direct 25×52 mm — réseau local (TCP 9100), cloud (Weblink + SendFileToPrinter) **ou** Bluetooth LE (Web Bluetooth tablette) — preview Labelary |
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

# Photo vitrine — détourage automatique du fond (background removal).
# Photoroom est le backend prioritaire ; sans clé, fallback sur rembg local
# (hors-ligne, s'il est installé), sinon la copie vitrine est simplement
# ignorée (la photo originale reste). Voir app/services/storefront_photo.py.
PHOTOROOM_API_KEY=                # clé API Photoroom

# Embedding visuel Personal Shopper (PS 360 V4). "structured" (défaut) =
# encodeur hashing-trick sans dépendance. "clip" = vrai encodeur CLIP/SigLIP
# (ONNX) : installer l'extra (pip install -e ".[clip]") + pointer CLIP_MODEL_PATH
# sur un .onnx. Repli automatique par produit sur "structured" si modèle/dep
# absent → activation non bloquante (comme rembg). Voir app/services/visual_encoder.py.
VISUAL_EMBEDDING_BACKEND=structured   # structured | clip
CLIP_MODEL_PATH=                      # chemin du modèle image-encoder .onnx (mode clip)

# Météo Vernon (sans cette clé, widget météo indisponible)
OPENWEATHER_API_KEY=votre-cle-openweather

# CB SumUp — production uniquement
# Le mode sandbox/simulation a été retiré pour la mise en prod boutique.
# Si SUMUP_API_KEY n'est pas posée, les checkouts CB retournent FAILED
# (pas de simulation de paiement).
SUMUP_API_KEY=                    # sup_sk_... (obligatoire pour encaisser en CB)
SUMUP_MERCHANT_CODE=              # M... (obligatoire pour encaisser en CB)
SUMUP_READER_ID=                  # optionnel: push direct vers un TPE Solo
SUMUP_RETURN_URL=                 # optionnel: callback après paiement reader

# Hardware (optionnel — sinon configurable via /settings > Materiel)
RECEIPT_PRINTER_HOST=             # IP de la MUNBYN 047P-WiFi
RECEIPT_PRINTER_PORT=9100
ZEBRA_PRINTER_IP=                 # IP de la Zebra ZD421d (legacy: LABEL_PRINTER_HOST fallback)
ZEBRA_PRINTER_PORT=9100
# Zebra — choix du transport d'impression étiquettes :
#   network (défaut) = ZPL en TCP 9100 sur le LAN (l'API doit joindre l'IP).
#   cloud            = Weblink + API SendFileToPrinter. L'imprimante se
#                      connecte en SORTIE à Zebra Data Services ; le backend
#                      pousse le ZPL par REST. À utiliser quand l'API tourne
#                      hors site (cloud) et ne peut pas ouvrir de socket vers
#                      la boutique. Le MQTT natif Zebra ne sait PAS imprimer
#                      (gestion/notifs only) — d'où Weblink. Voir
#                      app/services/zebra_cloud.py pour l'enrôlement.
#   bluetooth        = Web Bluetooth (BLE) depuis la tablette Chrome Android.
#                      Le serveur ne peut pas joindre une imprimante BLE :
#                      les endpoints d'impression renvoient 400 et la
#                      tablette récupère le ZPL (GET /api/labels/{id}/zpl)
#                      pour l'écrire sur le service BLE Parser de la Zebra.
#                      Voir apps/web/src/lib/web-bluetooth-printer.ts.
ZEBRA_CONNECTION=network          # network | cloud | bluetooth
ZEBRA_CLOUD_API_KEY=              # clé API Zebra Data Services (mode cloud)
ZEBRA_CLOUD_TENANT=               # n° de tenant Zebra (mode cloud)
ZEBRA_CLOUD_SERIAL=               # n° de série de l'imprimante enrôlée (mode cloud)
ZEBRA_CLOUD_ENDPOINT=             # optionnel: override (défaut api.zebra.com/v2/devices/printers/send)
VINTIZ_HARDWARE_CONFIG=           # chemin custom du fichier hardware.json (défaut: data/hardware.json)

# Sauvegarde base de données (gestionnaire admin /admin/database)
# Dump complet (pg_dump | gzip) chaque nuit à 3h + déclenchement manuel.
# Rétention / email d'alerte / activation du cron sont éditables dans l'UI.
BACKUP_DIR=data/backups          # dossier des dumps (persisté via volume vintiz_data en prod)
BACKUP_ALERT_EMAIL=              # destinataire mail si échec (repli: SMTP_FROM ; éditable dans l'UI)

# Email transactional (P4-003) — gateway unifié Brevo > SMTP > simulation.
# Si BREVO_API_KEY est posée → Brevo. Sinon → fallback SMTP. Sinon → simulation.
BREVO_API_KEY=                    # xkeysib-xxx
EMAIL_FROM_ADDRESS=noreply@vintiz.fr
EMAIL_FROM_NAME=Vintiz Vernon

# Email SMTP (fallback si BREVO_API_KEY non posée)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=email@domaine.fr
SMTP_PASSWORD=mot-de-passe

# Wallet pass (P4-004) — payload prêt, signing à plugger côté ops
WALLET_PASS_TYPE_IDENTIFIER=pass.fr.vintiz.loyalty
WALLET_TEAM_IDENTIFIER=           # ABCDE12345 (Apple Developer)
WALLET_GOOGLE_ISSUER_ID=          # 19 chiffres (Google Pay & Wallet)
WALLET_GOOGLE_CLASS_SUFFIX=vintiz_loyalty

# SMS — gateway unifié Brevo (primary) → Twilio (legacy fallback) → simulation.
# Vintiz a migré sur Brevo pour email ET SMS : la même BREVO_API_KEY ci-dessus
# active les deux. Aucun nouveau secret à configurer côté ops.
# Sender ID alphanumérique affiché sur le téléphone (Brevo, max 11 chars).
BREVO_SMS_SENDER=Vintiz
# Twilio reste supporté en fallback pour compat anciens déploiements
# (sera retiré une fois la migration prod confirmée).
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM=

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
POST   /api/labels/print/{product_id}        Impression unitaire Zebra (ZPL TCP 9100)
POST   /api/labels/print/batch                Impression multiple (body: product_ids[], copies)
GET    /api/labels/preview/{product_id}       Aperçu PNG Labelary (image/png)
GET    /api/labels/printer/status             Ping TCP imprimante (online/offline + latency_ms)
GET    /api/labels/sheet?ids=…&cols=2&rows=4  Mode dégradé : planche A4 HTML (window.print auto)
GET    /api/pos/transactions/{id}/escpos      Bytes ESC/POS bruts pour WebUSB (mode tablette)
GET    /api/hardware/receipt/test-escpos     Bytes ESC/POS pour ticket test WebUSB
GET    /api/inventory/products/{id}/score    Score détaillé
POST   /api/inventory/products/{id}/reprice  Change le prix → recalcule+persiste la note (trend_score) → propose un déplacement (suggest_zone). Audit logge le prix. Body: new_price
GET    /api/inventory/products/{id}/photos   Liste multi-photos
POST   /api/inventory/products/{id}/photos   Ajouter une photo (url + AI fields)
POST   /api/inventory/products/{id}/photos/{pid}/primary  Définir la photo primaire
POST   /api/inventory/products/{id}/photos/{pid}/storefront Régénérer la photo vitrine (fond détouré + logo)
POST   /api/inventory/products/{id}/photos/reorder        Réordonner (drag/drop)
DELETE /api/inventory/products/{id}/photos/{pid}          Supprimer une photo
POST   /api/inventory/products/import-csv    Import en masse CSV (multipart, ?dry_run=true)
GET    /api/inventory/products/{id}/history  Historique mouvements (audit_logs)
POST   /api/inventory/products/{id}/transition  Transition cycle de vie produit (FSM)
DELETE /api/inventory/products/{id}          Soft-delete (statut → returned)
DELETE /api/inventory/products/{id}/permanent  Suppression définitive d'un produit créé à tort (manager only, 409 si déjà vendu, nettoie photos/zone/embedding/order/events, audité)
POST   /api/inventory/batches                Créer un lot d'arrivage (carton)
GET    /api/inventory/batches                Liste des lots
GET    /api/inventory/batches/{id}           Détail lot + produits assignés
POST   /api/inventory/batches/{id}/assign-product  Rattacher produit au lot
GET    /api/inventory/products/{id}/suggest-zone   Reco placement zone (P2-006)
GET    /api/inventory/locate?q=              Localiser un produit en boutique (P2-008)
# Mouvements de stock — flux vertical (réserve↔rayon) & horizontal (zone↔zone)
GET    /api/inventory/products/{id}/location-history  Timeline emplacements (historisée dans la fiche)
GET    /api/inventory/movements/weekly-plan   Aménagement hebdo IA (horizontal, travail zone par zone)
GET    /api/inventory/movements/restock-plan  Achalandage réserve→rayon selon le besoin des zones (vertical)
POST   /api/inventory/movements/execute       Mouvement à la lecture du code-barres (body: barcode, to_status?, to_zone_id?)

# POS — vente + caisse + ticket
POST   /api/pos/transactions                 Créer une vente (idempotent via client_uuid optionnel — replay offline safe)
POST   /api/pos/transactions/{id}/refund     Refund partiel/total (cash/card/cheque/avoir)
GET    /api/pos/transactions/{id}/receipt    Texte du ticket (80 mm)
POST   /api/pos/transactions/{id}/resend     Renvoyer ticket (email/SMS, body: channel + to optionnel pour walk-in)
POST   /api/pos/drawer/open                  Ouvrir la caisse (fond initial)
POST   /api/pos/drawer/close                 Fermer + rapport Z
GET    /api/pos/drawer/current               État tiroir

# POS — CB SumUp
POST   /api/pos/payments/cb/initiate         Initier paiement SumUp (production)
GET    /api/pos/payments/cb/{id}/status      Poller statut SumUp
DELETE /api/pos/payments/cb/{id}             Annuler checkout
GET    /api/pos/payments/cb/config           Config SumUp (clés masquées)

# Hardware (back-office /settings > Materiel)
GET    /api/hardware/compatibility           Liste matériel supporté
GET    /api/hardware/config                  Lire config persistée (data/hardware.json)
PUT    /api/hardware/config                  Modifier config (IP imprimante, kick pin…)
POST   /api/hardware/receipt/test            Imprimer un ticket de test (MUNBYN ESC/POS)
POST   /api/hardware/drawer/kick             Ouvrir tiroir (impulsion ESC p m via printer)
POST   /api/hardware/label/test              Imprimer étiquette de test (Zebra ZPL)

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
GET    /api/admin/database/state            État base : volumes/table, taille, dernière sauvegarde (manager only)
GET    /api/admin/database/config           Lire réglages sauvegarde (rétention/email/cron) (manager only)
PUT    /api/admin/database/config           Modifier réglages sauvegarde (manager only)
GET    /api/admin/database/backups          Liste des sauvegardes (manager only)
POST   /api/admin/database/backups/run      Lancer une sauvegarde manuelle (manager only)
GET    /api/admin/database/backups/{id}/download  Télécharger un dump .sql.gz (manager only)
DELETE /api/admin/database/backups/{id}      Supprimer une sauvegarde (fichier + ligne) (manager only)
GET    /api/admin/database/export?table=…    Export CSV d'une table whitelistée (manager only)
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
GET    /api/admin/message-templates          Liste templates emails/SMS auto éditables (manager only ; seed défauts au 1er appel)
PUT    /api/admin/message-templates/{id}     Éditer objet/corps/actif d'un template (manager only)
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
# Personal Shopper : le pipeline embeddings est l'UNIQUE voie de reco
# (cosinus visual+text → diversification catégorie → narrative Haiku, gated
# membre+consent profilage). Pas d'endpoint « v1 à règles ». Note : l'ALGO_VERSION
# interne reste "personal-shopper-v1-2026-04" pour la continuité des events loggés.
GET    /api/crm/clients/{id}/personal-shopper-v2  Personal shopper (embeddings + Claude Haiku, manager)
GET    /api/crm/personal-shopper-v2?email=        Personal shopper v2 public (lookup email)
POST   /api/crm/personal-shopper-v2/click         Log click sur recommandation
GET    /api/crm/onboarding/options                Catalogue genres/âges/styles/occasions/budgets/marques (public)
GET    /api/crm/onboarding/visual-candidates      Pièces du cold-start visuel L2 (public, ?gender=&n=)
POST   /api/crm/clients/{id}/onboarding           Onboarding en couches (manager — L1 genre/âge, L2 likes, L3 détaillé)
POST   /api/crm/account/onboarding                Onboarding en couches (public, body: email + L1/L2/L3)
GET    /api/crm/clients/{id}/avoir                Solde + historique avoir (store credit)
GET    /api/crm/clients/{id}/consents              Consentements RGPD (état courant + historique)
POST   /api/crm/clients/{id}/consents              Enregistrer consentement (purpose+granted+source)
GET    /api/crm/clients/{id}/data-export           Export RGPD JSON portable (Article 20)
POST   /api/crm/clients/{id}/deletion-request      Demande suppression (soft, fenêtre 30j)
POST   /api/crm/clients/{id}/deletion-cancel       Annuler demande de suppression
GET    /api/crm/account/data-export?email=         Public — export RGPD JSON par email
POST   /api/crm/account/deletion-request           Public — demande suppression (body: email)
POST   /api/crm/account/deletion-cancel            Public — annuler suppression (body: email)

# Phase 4 — Analytics & reporting (P4-001 / P4-002 / P4-007)
GET    /api/reports/retail-kpis?period_days=30     KPIs retail (sell-through, GMROI, AIT, CA/m²/mois…)
GET    /api/reports/ess?period_days=90             Rapport ESS (réemploi, tonnage, CA reversé)
GET    /api/reports/stock-movement?period_days=30  Gestion stock (réserve/rayon) + vitesse + rythmes rotation V/H
GET    /api/admin/kpis-config                      Config surface boutique + poids pièce + %CA reversé
PUT    /api/admin/kpis-config                      Modifier la config retail/ESS
POST   /api/admin/rfm/run                          Trigger manuel segmentation RFM
GET    /api/crm/segments                           Counts par segment RFM
GET    /api/crm/segments/{segment}                 Sample clientes d'un segment

# Phase 4 — Communication automatique (P4-003 / P4-004 / P4-008 / P4-009)
GET    /api/crm/account/wallet?email=              Wallet pass payload (Apple + Google) — public
GET    /api/crm/clients/{id}/wallet                Wallet pass payload (manager-side preview)
POST   /api/admin/anniversary/run                  Trigger manuel cron anniversaires
POST   /api/admin/new-arrivals/run                 Trigger manuel digest hebdo nouvelles arrivées
GET    /api/admin/coupons?only_active=true         Liste coupons (manager only)

# Phase 4 — POS AI badges (P4-010) + redemption coupon
GET    /api/inventory/products/{id}/insights       Badges contextuels pour la caisse
POST   /api/pos/coupons/validate                   Preview coupon (body: code, cart_total, client_id?)
POST   /api/pos/transactions                       Crée vente (accepte coupon_code? optionnel)

# Événementiel ouverture — bons cadeau (crédit fiche client + débit en caisse)
GET    /api/pos/event-vouchers/catalog             Catalogue des bons (boutons zone Événementiel)
POST   /api/pos/event-vouchers/issue               Créditer un bon sur la fiche client (body: client_id, type_key)
GET    /api/pos/clients/{id}/vouchers              Bons actifs d'une cliente (affichés à l'identification)
POST   /api/pos/transactions                       Débit d'un bon : ligne paiement method=voucher + voucher_code
GET    /api/admin/event-vouchers/catalog           Lit le catalogue des bons cadeau (manager)
PUT    /api/admin/event-vouchers/catalog           Édite montants / % / validité / activation (manager)

# Refonte Relation Client — PR1: Magic-link + souscription + ticket fidélité
POST   /api/auth/magic-link/request                Issue OTP 6 chiffres + lien cliquable email (public, 204 toujours, anti-énumération)
POST   /api/auth/magic-link/verify                 Échange OTP → JWT client 1h (public)
POST   /api/auth/magic-link/verify-token           Connexion sans code via le lien email (?token=) → JWT client 1h (public)
POST   /api/pos/loyalty/subscribe                  Crée carte V###### au POS avec opt-ins RGPD (manager, 409 si email existant)
GET    /api/pos/clients/identify?q=                Identifie client par V######, email, phone (manager)
GET    /api/admin/loyalty/config                   Lit config souscription (mode + prix + seuil) (manager)
PUT    /api/admin/loyalty/config                   Modifie config 3 modes free/paid/first_purchase (manager)
GET    /api/admin/loyalty/earning-config           Lit règles cumul fidélité (pts/€, bon valeur+seuil, validités) (manager)
PUT    /api/admin/loyalty/earning-config           Modifie règles cumul (1 pt/X€, bon X€/X pts, validité bon+points) — admin/operations (manager)

# Refonte Relation Client — PR2: Personal Shopper + alertes tendance
POST   /api/crm/account/personal-shopper/toggle    Pose/retire consent profilage (public, body: email, enabled)
POST   /api/crm/account/trend-alerts/toggle        Pose/retire consent trend_alerts (public)
POST   /api/crm/account/personal-shopper/search    Recherche sémantique texte libre (gated, body: email, q)
GET    /api/crm/account/personal-shopper/live      Sélection PS live gated (membre + profilage)
POST   /api/admin/trend-alerts/run                 Trigger manuel cron alertes tendance (manager)

# Refonte Relation Client — PR3: espace client RGPD (6 zones)
POST   /api/crm/account/register                   Créer son espace client depuis le site (public, 202 toujours, anti-énumération ; crée le Client + opt-ins + envoie le magic-link)
GET    /api/crm/account/coupons?email=             Liste coupons actifs cliente (public)
GET    /api/crm/account/transactions?email=        Historique paginé avec items (public, limit ≤100)
GET    /api/crm/account/consents?email=            Liste consents lisible (5 purposes, granted/source/recorded_at)
POST   /api/crm/account/consents/{purpose}         Toggle consent générique (body: email, granted)
GET    /api/crm/account/loyalty/status?email=      État adhésion fidélité (active, n° carte, mode) — espace client
POST   /api/crm/account/loyalty/subscribe          Adhésion self-service depuis l'espace client (public, body: email, opt-ins ; idempotent ; pas de paiement en ligne)

# Refonte Relation Client — PR4: companion POS + fiche client + predictive
GET    /api/pos/clients/{id}/companion?cart_total_cents=&items=  Cart-aware up-sells (manager)
GET    /api/crm/clients/{id}/full                  Agrégat fiche client admin (+ section qualification V2, manager)
GET    /api/admin/predictive/audience?period_days=90  Snapshot debug dominant tastes loyal_active (manager)

# Personal Shopper 360 — V2: profilage métier + détection cadeau
POST   /api/pos/transactions                       Crée vente (accepte is_gift? → exclut du profil de goûts)
POST   /api/crm/account/transactions/{id}/gift     Cliente marque un achat « c'était un cadeau » (public, body: email, is_gift)
POST   /api/admin/qualification/run                Trigger manuel recalcul qualification (saison/prix/affinité, manager)

# Personal Shopper 360 — V3: aide à la vente
GET    /api/pos/clients/{id}/picks                 « Pépites du jour » : top 5 pièces présentes, filtrées dur genre+taille, classées cosinus puis trend_score, zone physique affichée, frequency cap 24h, log customer_picks_shown (manager ; non-membre/sans-consent → gated+CTA)

# Personal Shopper 360 — V5: appro prescriptif
GET    /api/admin/appro-brief                       Brief d'appro hebdo dans l'IA Booster : demande (goûts membres + skew genre) vs stock → recommandations niveau carton (catégorie×genre×qualité, action demander/réduire/maintenir). Cold-start = gaps déclaratifs (manager)
```

## Fonctionnalités principales

### 1. Inventaire
- Création produit avec génération automatique code-barres
- Fiche produit cliquable avec score détaillé (6 composantes)
- Date de mise en rayon, emplacement zone
- Édition inline prix / zone / statut
- **Genre produit** (`Product.gender` : homme/femme/enfant/mixte) saisi à
  l'étape 2 de l'assistant d'ajout (proposé par la détection image). C'est la
  **base de l'affectation automatique des zones** (`suggest_zone` privilégie le
  genre produit, repli sur le genre de la catégorie) et la **3ᵉ variable de la
  1ʳᵉ ligne de l'étiquette** (H/F/E/U). Additif : colonne nullable, les fiches
  antérieures restent à NULL (repli catégorie). Voir migration 0048.
- Bouton "Générer étiquette" → PNG téléchargeable/imprimable
- **Photo vitrine auto** : à chaque upload, une copie détourée (fond
  supprimé + canvas off-white charte + logo Vintiz) est générée en back et
  stockée dans la fiche (`ProductPhoto.processed_url`,
  `Product.storefront_photo_url`). Backend : Photoroom (`PHOTOROOM_API_KEY`,
  défaut, sans dépendance) ; repli rembg local **optionnel** (extra
  `pip install -e ".[rembg]"`, embarque onnxruntime). Sans backend, la copie
  vitrine est ignorée (statut `skipped`). Proposée en fin d'assistant d'ajout ;
  régénérable depuis la galerie photos. C'est l'image destinée au site vitrine.

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
- **Analyse photo** : Claude Vision détecte type, couleur, marque, état, **genre** (H/F/E/U)
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
- 11 zones prédéfinies (plan boutique L, Lot N°2 ~184 m² utiles dont ~99 m² magasin) — voir `plan.jpg` + photos `apps/web/public/zones/*.jpeg`
- Édition : nom, description, capacité, types de produits, couleur, photo, **objectif CA mensuel par zone**
- Plan 2D : positions (`pos_x`, `pos_y`, `width`, `height`, `shape`, `display_order`)
  pilotables visuellement (utilisé par `IA Booster > Mapping Boutique`)

### 7. Hardware (`/settings > Materiel`)
- Configuration persistée dans `apps/api/data/hardware.json`
- Onglets matériel : imprimante ticket / tiroir / imprimante étiquette / douchette / TPE
- Boutons de test live :
  - "Imprimer ticket test" (MUNBYN ESC/POS port 9100)
  - "Kicker tiroir" (impulsion `ESC p m`)
  - "Imprimer étiquette test" (Zebra ZPL port 9100)
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

### 10. Espace client (site public, 6 zones)
- **Auth magic-link** : OTP 6 chiffres email (10 min TTL, 5 tentatives, rate-limit
  3/h/email + 30/h/IP), JWT cookie 1 h. Plus de `?email=` dans les URLs.
- **Carte fidélité unique** : 1 € = 1 pt, n° `V######`, péremption 24 mois
  sans activité (cron quotidien `daily_loyalty_expiry` 03:30). Carte
  virtuelle Apple Wallet + Google Wallet. Adhésion 100 % digitale au POS,
  3 modes admin configurables (gratuite / payante / offerte 1er achat).
- **Personal Shopper gated** : réservé aux membres avec consent profilage.
  Recherche sémantique texte libre (« t-shirt blanc taille M ») — Claude Haiku
  extrait les filtres, cache Redis 24 h.
- **Alertes tendance** : email auto quand un produit `trend_score>70` matche
  le taste profile d'une cliente opt-in (frequency cap 7 j, cron 11:00).
- **Espace client** : 6 zones isolées (`/account` index, `/fidelite`,
  `/shopper`, `/selection`, `/offres`, `/historique`, `/rgpd`) avec side nav
  responsive (drawer mobile + sidebar desktop), composants partagés
  `AccountShell` + `AccountNav`.
- **RGPD** : page `/account/rgpd` avec consents lisibles, export Article 20,
  demande suppression 30 j (annulable), DPO `dpo@solidarite-textiles.fr`.

### 11. POS Companion (panneau caisse)
- À l'identification cliente, panneau latéral auto-rafraîchi (debounce 300 ms)
  affiche : solde fidélité + gain panier + rachat max 50 %, 3 suggestions
  complémentaires (mapping `CATEGORY_COMPLEMENTS` robe→accessoires/chaussures…),
  coupons applicables (bouton "Appliquer"), alertes RFM (`at_risk`, `champion`,
  `hibernating`) + birthday <7 j + milestone fidélité <14 pts.
- Fiche client admin `/clients/[id]` : 6 onglets (Synthèse / Achats / Fidélité /
  Goûts / RGPD / Audit) chargés en 1 requête `GET /crm/clients/{id}/full`.

### 12. Gestionnaire de base de données (admin `/admin/database`, manager only)
- **État de la base** : moteur, taille, volumes par table, dernière sauvegarde.
- **Sauvegarde nocturne** : cron APScheduler 03:00 Europe/Paris
  (`run_nightly_database_backup`, jobs.py) → dump complet `pg_dump | gzip` dans
  `BACKUP_DIR` (le conteneur API embarque `postgresql-client`). Chaque dump =
  une ligne `DatabaseBackup` (succès/échec, taille, durée). **Mail d'alerte en
  cas d'échec** via la passerelle email (destinataire configurable).
- **Déclenchement manuel** + **téléchargement** de chaque sauvegarde (.sql.gz).
- **Réglages éditables** (`DatabaseBackupConfig` singleton) : rétention en jours
  (purge auto fichiers + lignes), email d'alerte, activation du cron nocturne.
- **Exports CSV** par table whitelistée (produits, catégories, clients,
  transactions, newsletter). Service : `app/services/database_backup.py`.

## Design tokens (Tailwind)

Charte v3 « Sauge Néo » (2026-04) — voir `docs/DESIGN_SYSTEM.md` pour le détail complet.
Preset Tailwind : `design-package/tailwind.preset.ts`.

```css
vz-bg:          #F6F5F1  (fond principal off-white)
vz-bg-alt:      #ECEAE3  (sidebar backend, sections alternées)
vz-surface:     #FFFFFF  (cards, modales, inputs)
vz-ink:         #0E0E0C  (texte principal — quasi-noir)
vz-ink-soft:    #4A4A47  (texte secondaire)
vz-ink-mute:    #8B8B86  (méta, labels, hints)
vz-line:        #D5D3CC  (bordures, séparateurs)
vz-teal:        #0B7A6A  (couleur primaire — CTA, liens, fidélité)
vz-teal-deep:   #054238  (hover/pressed teal)
vz-teal-soft:   #CDE5DF  (background chips/badges teal)
vz-accent:      #E84E8B  (magenta éditorial — célébration uniquement)
vz-accent-soft: #FFD5E5  (background offre encartée)
vz-gold:        #8E7B57  (tier fidélité haut de gamme)
```

Typographie : **Fraunces** (display, `font-display`) + **Manrope** (body,
`font-body`/`font-sans`) + **JetBrains Mono** (codes/numéros, `font-mono`).
Chargées via `@import url('https://fonts.googleapis.com/css2?...')` en tête
de `apps/{web,site}/src/app/globals.css`.

Mode sombre backend uniquement, activé via `[data-theme="dark"]` ou `.dark`.

Logos (copiés dans `apps/{web,site}/public/`) :

| Fichier | Usage |
|---|---|
| `/logo-teal.png` | Monogramme VZ teal `#0B7A6A` — logo par défaut (navbar, sidebar, login) |
| `/logo-rose.png` | Monogramme magenta `#E84E8B` — fonds sombres (footer noir) — **à régénérer en v3 (était `#FFC5DF` en v2)** |
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
| Imprimante étiquettes | **Zebra ZD421d** ZPL II 25×52 mm | Réseau LAN (9100), cloud Weblink **ou** Bluetooth LE | `zebra_printer.py` (TCP) + `zebra_cloud.py` (Weblink) + `web-bluetooth-printer.ts` (BLE front) + `zebra_zpl.py` |
| Tiroir-caisse | **Safescan SD-4141** RJ-12 | Branché sur imprimante (kick `ESC p m`) | inclus dans `escpos_service` |
| TPE | **SumUp Solo** | Wi-Fi / compte SumUp | `app/services/sumup_service.py` |

Une seule impression ticket : **MUNBYN ESC/POS** — bouton *Imprimer (MUNBYN)*
dans la modal ticket. Appelle `POST /api/pos/transactions/{id}/print` qui
envoie le ticket en ESC/POS direct vers la MUNBYN port 9100. Tiroir kické
via la même connexion réseau. L'ancien fallback AirPrint a été retiré
(Vintiz tourne sur Android, où `window.print()` retombe en PDF — inutile).

Procédure complète + 15 codes-barres scannables : `docs/POS_TEST_BARCODES.md`.

```bash
# 1. Configurer SumUp (production uniquement)
SUMUP_API_KEY=sup_sk_...        # OBLIGATOIRE — sinon les checkouts CB échouent
SUMUP_MERCHANT_CODE=M...        # OBLIGATOIRE
SUMUP_READER_ID=                # optionnel: push direct vers TPE Solo

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

### SumUp — production uniquement

Le mode sandbox / simulation a été retiré pour la mise en prod boutique.
Tous les checkouts CB passent par api.sumup.com en production avec une
vraie clé. Si `SUMUP_API_KEY` n'est pas configurée, les appels retournent
`FAILED` avec un message explicite plutôt que de simuler un paiement —
impossible donc d'encaisser une fausse vente CB par accident.

Pour tester avec une carte sans débiter réellement : SumUp propose des
clés API de test côté developer.sumup.com (préfixe `sup_sk_test_…`).
Configurer dans `SUMUP_API_KEY` ou via `/settings > Paiement`.
