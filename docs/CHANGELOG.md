# Changelog Vintiz

## [0.7.1] - 2026-04-27 — Remap boutique 11 zones (plan.jpg)

### Changed — Plan boutique aligné sur le Lot N°2 réel
- **Zones boutique : 7 → 11** alignées sur `plan.jpg` (Lot N°2 ~184 m² utiles dont ~99 m² magasin) :
  - `Petits Prix 1` / `Petits Prix 2` (200 + 200) — mur du fond, femme
  - `Extra 1` / `Extra 2` (150 + 150) — mur du fond / retour gauche, femme
  - `Chaussures F` (30) — mur gauche près des cabines
  - `Portants Standards 1` / `Portants Standards 2` (120 + 120) — portants centraux femme
  - `Chaussures H` (30) — coin façade gauche
  - `Hommes` (150) — mur façade
  - `Tendance` (200) — tête de gondole façade femme
  - `Vitrine` (8, expo uniquement) — devanture côté entrée
  Toutes féminines sauf `Hommes` + `Chaussures H`. Les anciennes zones
  (`Vitrine gauche`, `Mur gauche`, `Mur fond`, `Mur droit`, `Podium entree`,
  `Zone centrale`, `Cabine essayage`) sont supprimées par la migration ;
  les `products.zone_id` orphelins sont nullifiés.
- Photos zones exposées sous `/zones/*.jpeg` (apps/web + apps/site).
- Plan IA (`/ia` > Mapping Boutique) repositionné : entrée à droite, façade en bas.
- Prompt Claude Merchandising mis à jour avec les 11 noms réels.

### Added
- Migration `0026_remap_store_zones` idempotente : upsert des 11 zones cibles,
  détache `products.zone_id`, supprime les zones legacy (cascade `ZoneProduct`,
  `ZoneTag`, `FurnitureItem`).
- `apps/{web,site}/public/zones/*.jpeg` + `plan.jpg` (assets exposés au front).

### Fixed
- `app/core/security.py` importe désormais `bcrypt` directement → ajout du pin
  `bcrypt>=4.1.0` dans `pyproject.toml` (dropé par erreur lors du refactor C1-C5
  qui retirait `passlib[bcrypt]`). Sans ce pin, l'API ne bootait plus
  (`ModuleNotFoundError: bcrypt`).

## [0.7.0] - 2026-04-26 — Phase 4 (analytics, communication, UX) + POS redemption

### Added — Analytics & reporting (P4-001 / P4-002 / P4-007)
- **Retail KPIs** : sell-through, GMROI, days-on-hand, AIT, CA/m²/mois, top/bottom catégories, %change vs N-1.
  Endpoint `GET /api/reports/retail-kpis?period_days=30`. Settings éditables via `GET/PUT /api/admin/kpis-config`.
- **Rapport ESS Solidarité Textiles** : pièces reçues/vendues/données/retour-tri, taux de réemploi, tonnage estimé,
  CA reversé. Endpoint `GET /api/reports/ess?period_days=90`.
- **Segmentation RFM** : scoring quintile R/F/M + 9 segments (champion, loyal, new, promising, cant_lose, at_risk,
  hibernating, lost, regular). Persisté sur `Client.rfm_segment` via cron mensuel (1er du mois 04:00).
  Endpoints `POST /api/admin/rfm/run`, `GET /api/crm/segments`, `GET /api/crm/segments/{segment}`.
- 3 cards UI sur `/reports` : `RetailKpisCard`, `EssReportCard`, `RfmSegmentsCard`.
- Migration 0016 : `clients.rfm_segment`.

### Added — Communication automatique (P4-003 / P4-004 / P4-008 / P4-009)
- **Email gateway unifié** : Brevo > SMTP > simulation, sélectionné runtime via env (`BREVO_API_KEY`,
  `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`). Refactor des call-sites SMTP inline (`crm/send-email`, `pos/resend`).
- **Wallet pass payload** : Apple `.pkpass` + Google LoyaltyObject pré-remplis, exposés via
  `GET /api/crm/account/wallet?email=...`. Carte preview sur `/account/data` (site public). Signing différé (cert
  Apple p12 + service account Google requis côté ops).
- **Email anniversaire** : cron quotidien 09:00 → coupon `ANNIV-XXXXXX` -10% pendant 7j + email transactionnel.
  Idempotent par jour calendaire.
- **Email nouvelles arrivées** : cron hebdo vendredi 10:00 → digest des 5 dernières pièces *display*. Personal
  Shopper utilisé si profil de goût, fallback générique sinon.
- Migration 0017 : `clients.birth_date` + table `coupons` + enums `coupon_discount_type`, `coupon_source`.

### Added — UX manager + cliente (P4-005 / P4-006 / P4-010)
- **Réservation 48h** : modèle + index partiel unique (un seul hold actif par article) + service complet (create /
  cancel / redeem / expire) + UI manager `/reservations` + section "Vos pièces réservées" sur `/account/data`.
  Endpoints `GET /api/reservations`, `POST /api/reservations`, `POST /api/reservations/{id}/cancel`,
  `GET /api/reservations/lookup?email=`. Cron horaire d'expiration (hh:15).
- **Mobile dashboard** : strip KPI sticky compact (CA / tickets / panier) visible uniquement sur mobile.
- **Badge IA POS** : endpoint `GET /api/inventory/products/{id}/insights` + 5 types de badges (🔥 vélocité,
  ⏳ stale, ⭐ marque, 🎯 score, 🛍 hold) affichés sous chaque ligne du panier.
- Migration 0018 : table `reservations` + enum `reservation_status`.

### Added — Coupon + reservation redemption au POS
- `POST /api/pos/coupons/validate` : preview cashier (read-only, vérifie statut/expiration/client).
- `POST /api/pos/transactions` : accepte un `coupon_code` optionnel, redime atomiquement après signature fiscale.
- `GET /api/pos/products/{id}/reservation-holder` : warning bandeau pour la caisse (rouge si tenu pour quelqu'un
  d'autre, vert si correspondance cliente).
- Auto-redemption : à la création de vente, toute réservation active dont le produit est dans le panier passe à
  `redeemed` + lien `redeemed_transaction_id`.

### Hotfix
- **Migration 0014** : `INSERT … VALUES (…, :tier, …)` plantait sur PG (asyncpg) car le bind param VARCHAR n'était
  pas auto-coerced vers l'enum `brand_tier_level`. Wrappé dans `CAST(:tier AS brand_tier_level)`.

### Tests
- 5 PR Phase 4 + 1 hotfix mergés (#25, #27, #28, #29, #30).
- Suite : 362 tests passent (vs 280 avant Phase 4).
- 9 nouveaux fichiers de test : `test_retail_kpis.py`, `test_rfm.py`, `test_email_gateway.py`,
  `test_wallet_service.py`, `test_anniversary_coupons.py`, `test_new_arrivals.py`,
  `test_reservation_service.py`, `test_product_insights.py`, `test_coupon_redemption.py`.

### Variables d'environnement nouvelles
```env
BREVO_API_KEY=
EMAIL_FROM_ADDRESS=noreply@vintiz.fr
EMAIL_FROM_NAME=Vintiz Vernon
WALLET_PASS_TYPE_IDENTIFIER=pass.fr.vintiz.loyalty
WALLET_TEAM_IDENTIFIER=
WALLET_GOOGLE_ISSUER_ID=
WALLET_GOOGLE_CLASS_SUFFIX=vintiz_loyalty
```

### Suivi (laissé en TODO)
- **Apple `.pkpass` signing** (cert p12 + WWDR) — payload prêt, signing à plugger côté ops.
- **Google Wallet JWT signing** (Service Account) — payload prêt, signing à plugger côté ops.
- Pagination de l'autocomplete cliente côté `/reservations` quand >1k clientes.

## [0.3.0] - 2026-04-16 — Hardware-ready POS
### Added
- **SumUp sandbox** — service refactoré avec 3 modes (`production`, `sandbox`,
  `simulation`) pilotés par `SUMUP_ENVIRONMENT`. Simulation en mémoire avec
  event log live et approve/decline manuel depuis *Paramètres > Paiement*.
  Variables d'env : `SUMUP_ENVIRONMENT`, `SUMUP_API_KEY`, `SUMUP_MERCHANT_CODE`,
  `SUMUP_SANDBOX_AUTO_DELAY_SEC`.
- **Gestion tiroir-caisse** côté UI POS : ouverture (fond initial), fermeture
  avec rapport Z (totaux par méthode, écart attendu/compté).
- **Numpad tactile** pour saisies de montants (espèces, fond de caisse).
- **Douchette code-barres** (Inateck 160B / USB HID) : handler `Enter` sur le
  champ recherche POS auto-focus — scan → ajout automatique au panier.
- **Impression ticket 80 mm** via `window.print()` (AirPrint iPad). Le tiroir
  s'ouvre automatiquement via l'option driver imprimante "open drawer on print".
- **15 produits de test** (`TEST0001` → `TEST0015`) couvrant 0,25 € → 79 €.
  Seed idempotent : `scripts/seed_test_products.py`.
- **Codes-barres scannables** : `docs/POS_TEST_BARCODES.md` + 15 PNG Code 128
  générés dans `docs/test_barcodes/`.
- **Deploy flag** `--test-products` dans `scripts/deploy.sh` pour seeder les
  produits de test sur le VPS.
- **Pickers size/color** sur la page de création produit (UX touch).
- Endpoint `GET /api/inventory/products/search?q=…` utilisé par la douchette.
- Endpoints sandbox : `/pos/payments/cb/sandbox/{config,state,approve,decline}`.

### Changed
- POS UI refondue touch-first (min-height 44px sur tous les boutons).
- `scripts/deploy.sh` — help message et flags mis à jour.

## [0.2.0] - 2026-03-29
### Added
- Frontend PWA back-office (Next.js 14 + Tailwind)
  - Design system Vintiz (Button, Card, Input, Badge, Modal, DataTable)
  - Sidebar navigation avec icones
  - Page login avec auth JWT
  - Dashboard KPIs (CA, stock, transactions, panier moyen)
  - Inventaire : liste produits, creation avec photo, filtres
  - Caisse : scan/saisie, panier, paiement multi-mode, cloture Z
- Module POS backend complet
  - Service encaissement avec TVA 20%
  - Multi-paiement (especes, CB, cheque) avec rendu monnaie
  - Gestion tiroir-caisse (ouverture, cloture, cadrage)
- Conformite fiscale NF525
  - Hash chain SHA-256 sur transactions
  - Generation Z reports immutables
  - Verification integrite chaine
  - Service tickets de caisse
- CRM backend
  - CRUD clients (nom, prenom, tel, email, commune)
  - Systeme de fidelite (activation, solde)
  - Historique achats par client
- Reporting backend
  - Rapports quotidiens, hebdomadaires, mensuels
  - Valorisation du stock
- Script seed data (admin, categories, grille tarifaire, zones boutique)

## [0.1.0] - 2026-03-29
### Added
- Structure monorepo (apps/api, apps/web, apps/site)
- Assets de marque organises (logos, lettrages, etiquettes)
- Page "Ouverture Prochaine" (landing page vintiz.fr)
- Scaffold API FastAPI (modeles, schemas, auth, inventaire)
- Infrastructure Docker (PostgreSQL, Redis, API, Web, Site)
- Documentation architecture
