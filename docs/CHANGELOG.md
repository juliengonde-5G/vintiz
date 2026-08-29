# Changelog Vintiz

## [1.2.0] - 2026-08-29 — Prix manuel POS, débit fidélité à l'émission, session d'audit multi-agents

### Caisse
- **Prix manuel par article** : chip € à côté du chip remise `-%` — saisie d'un
  prix rond (entier), exclusif avec la remise %, prix ferme (pas de Solde
  par-dessus), ligne exclue des points fidélité, écart étiquette↔manuel compté
  dans les remises du jour, historisé dans la fiche produit
  (`pos.price_override`). API : `items[].manual_unit_price`.

### Fidélité
- **Correctif** : le compteur de points est désormais **débité du palier à
  l'émission du chèque cadeau** (ligne `redeem` au ledger) — il repart du
  reliquat. Migration `0076` : régularisation des comptes existants
  (déduction des paliers déjà convertis en chèques).
- Remboursements adaptés : un solde rendu négatif par l'annulation des points
  révoque le chèque non utilisé et re-crédite son palier.

### Conformité NF525
- Toute émission de ticket est tracée (`receipt.reprint` / `receipt.escpos`,
  `copy_number`) ; les émissions après la première impriment
  « * DUPLICATA n.X * » sur le ticket — y compris le chemin WebUSB tablette
  qui n'était pas tracé.
- `scripts/go_live_reset.py` : refus en `ENVIRONMENT=production`
  (inaltérabilité, art. 286-I-3° bis CGI) + carve-out `events_log`
  réellement préservé sous PostgreSQL.
- Nouveau `docs/PLAN_CONFORMITE_NF525.md` + `docs/DOSSIER_CERTIFICATION_NF525.md`.

### Site public / back-office
- Newsletter de la landing : le formulaire n'appelait aucune API — branché sur
  l'inscription réelle avec consentement RGPD explicite.
- Page `/admin/monitoring` raccrochée au template back-office (sidebar).

### Nettoyage
- Audit multi-agents (dette technique, promesse, NF525) archivé dans
  `docs/audits/2026-08-multi-agents/`.
- Code mort supprimé : `services/barcode.py` (+ dépendance `python-barcode`),
  `services/cash_drawer.py` ; `CLAUDE.md` réaligné (scripts de seed, fidélité,
  prix manuel).

## [1.1.2] - 2026-07-16 — Transparence IA et révocation du profilage

- Révocation du Personal Shopper rendue effective depuis ses deux interfaces :
  suppression immédiate du profil de goûts et des qualifications déclaratives,
  anonymisation des événements de recommandation et conservation séparée de
  l'historique d'achats soumis aux obligations légales.
- Mentions Anthropic corrigées sur le site et dans les documents d'audit : pas
  d'allégation d'hébergement UE, transparence sur le stockage américain par
  défaut, la rétention API standard et l'absence d'entraînement par défaut.
- Politique de confidentialité versionnée, promesse NF525 reformulée comme
  démarche de certification et description de la sécurité alignée sur les
  contrôles réellement déployés.
- Sélecteur de langue corrigé sur les routes sans équivalent anglais, dont
  l'espace client ; suppression de l'allégation d'hébergement UE de GA4.
- Tests de non-régression sur les deux parcours de retrait du consentement.

## [1.1.1] - 2026-07-16 — Correctif déploiement fiscal

- Migration 0072 compatible `asyncpg` : chaque fonction et trigger PostgreSQL
  est envoyé dans une commande préparée distincte.
- Le déploiement refuse désormais une clé fiscale absente ou trop courte et
  le compose de production impose explicitement `ENVIRONMENT=production`.
- Test de non-régression interdisant plusieurs commandes SQL de premier niveau
  dans un même appel Alembic.
- Smoke-test de production aligné sur la protection JWT des routes clientes ;
  procès-verbal 1.1.1 initial : 30 contrôles OK, aucun échec.

## [1.1.0] - 2026-07-15 — Durcissement révision, fidélité et NF525

### Sécurité et paiements

- Espace client protégé par JWT sur toutes les données personnelles ; les
  emails fournis par le navigateur ne servent plus d'autorité d'identité.
- Vente CB créée uniquement après relecture SumUp `PAID`, rapprochement du
  checkout, du montant, de la tentative serveur et du `client_uuid`.
- Remboursement CB local transactionnel : rollback si SumUp échoue.
- Validation stricte des lignes et paiements POS, coupons et bons verrouillés,
  rendu monnaie séparé du montant fiscal encaissé.

### Fidélité

- Promesse unifiée : 1 € éligible = 1 point ; promos, soldes, coupons et
  remises exclus ; chèque cadeau de 5 € à chaque palier de 100 points.
- Suppression de la conversion directe historique des points et des crédits
  manuels ; remboursement proportionnel des points avec gestion des bons déjà
  émis ou consommés.

### NF525 — version candidate, non certifiée

- Signature HMAC-SHA256 v2 sur transaction complète, lignes et paiements.
- Triggers PostgreSQL d'inaltérabilité, compteurs rollback-safe, Z enrichis.
- Clôtures mensuelles/annuelles, grand total et total perpétuel, archives JSON
  gzip scellées et endpoint de contrôle d'intégrité.
- Clé fiscale dédiée, version applicative unique, boot production refusé si la
  révision Alembic n'est pas `0072`.
- Documentation corrigée : une certification externe reste requise avant toute
  revendication « conforme NF525 » pour ce logiciel développé en interne.

### IA et qualité

- Personal Shopper aligné sur les statuts stock modernes, filtres genre/taille
  réellement durs, exclusion complète des cadeaux, appels via le routeur IA.
- CI rendue bloquante (ruff, tests, TypeScript, migrations) ; suppression des
  tolérances de build Next.js et des identifiants administrateur par défaut.

## [1.0.0] - 2026-06-03 — Mise en production officielle 🎉

**Ouverture de la boutique Vintiz Vernon — 03/06/2026, 10h00.** Version
verrouillée comme socle de production. Aucune nouvelle fonctionnalité majeure
par rapport à la 0.8.x : cette release consolide la base, corrige les bugs de
mise en route et fige la conformité fiscale (voir `docs/COMPLIANCE_NF525.md`).

### Fixed (mise en route boutique)
- **Clôture de caisse** : type enum PostgreSQL `cash_movement_direction`
  désaligné (`inflow`/`outflow` au lieu de `in`/`out`) → 500 qui cassait la
  connexion → « Failed to fetch » côté caisse. Migration `0057` réaligne les
  labels de manière idempotente.
- **Erreurs 500** : nouvelle frontière d'erreur dans `RequestIdMiddleware` —
  toute exception non gérée renvoie désormais un `JSONResponse(500)` lisible
  avec `request_id` (corrélation logs serveur ↔ message client) au lieu de
  réinitialiser la socket. Headers CORS toujours présents sur les 500.
- **Ticket par email** : le reçu reprend le contenu intégral du ticket de
  caisse (header, lignes, totaux, hash NF525, footer fidélité).
- **Remboursement admin** : impression via le pipeline unifié réseau/USB.
- **Cahier du jour** : objectif quotidien = objectif mensuel ÷ nb jours
  d'ouverture du mois.

### Changed
- **Bons cadeau d'ouverture** : 1 bon « prochain achat » par personne,
  non utilisable le jour de l'émission ; nouveaux bons « immédiats »
  (1€/2€/-10%/foulard) applicables sur l'achat en cours ; bouton *Valider*.
- **Emails transactionnels** : mail de bienvenue (adhésion + création de
  compte), mail récapitulatif au crédit d'un bon cadeau — templates éditables.
- **POS** : carte cliente compactée, compagnon caisse en modale (bouton
  *Encaisser* toujours visible), focus auto sur la recherche, tabulation +
  Entrée sur la création de fiche client.
- **Site vitrine** : pages `/produits`, fiches et home branchées sur
  l'inventaire réel (`/api/storefront/*`, ISR 5 min) ; suppression du Journal
  et de `/produits/made-in-france`.
- **Fiche produit** : affichage de la localisation (zone / réserve).
- **Objectifs annuels** : tableau 12 mois + simulateur d'augmentation (€ / %).

### Ops
- Version applicative bumpée à `1.0.0` (API + `/api/health`).
- Script **`scripts/go_live_reset.py`** (one-shot) : vide l'historique
  opérationnel (ventes, clients, fidélité, clôtures Z, FEC) en **conservant
  l'inventaire**, avec garde-fou qui annule (ROLLBACK) si le catalogue bouge.
- **Suppression de `scripts/purge_databases.py`** (rasait aussi l'inventaire)
  pour éviter toute fausse manipulation.

## [0.8.0] - 2026-04-28 — Refonte Relation Client (4 PRs)

Refonte complète de la relation client autour de 3 piliers : programme
fidélité simplifié, Personal Shopper réservé aux membres, espace client
repensé en 6 zones. Backend prédictif enrichi, panneau « compagnon caisse »
au POS, fiche client détaillée admin. 4 PRs distinctes mergées sur main
sans interruption de service.

### Added

**PR1 — Fondations fidélité + auth + souscription POS**
- Migration `0031`: drop `loyalty_accounts.tier`, ajoute `membership_number`
  format `V######` (V + 6 chiffres) unique avec backfill, ajoute
  `clients.{loyalty_subscribed_at, loyalty_expires_at, loyalty_subscription_mode}`,
  table `magic_link_tokens`, seed `app_settings` pour 3 modes souscription.
- Service `magic_link`: OTP 6 chiffres (10 min TTL, 5 tentatives max,
  rate-limit 3/h/email + 30/h/IP), JWT client 1 h.
- Service `membership_id`: génération `V######` retry-safe, lookup, regex.
- Service `loyalty.subscribe()` avec anti-doublon (`LoyaltyDuplicateError`)
  + helper `loyalty_active(client) -> bool` exposé pour PS gating.
- Service `loyalty_expiry`: cron quotidien 03:30, zero les comptes
  inactifs depuis 24 mois avec une transaction `adjust` négative.
- Service `loyalty_config`: 3 modes (`free` / `paid` / `first_purchase`)
  configurables depuis `/settings`.
- Endpoints: `POST /api/auth/magic-link/{request,verify}`,
  `POST /api/pos/loyalty/subscribe`, `GET /api/pos/clients/identify`,
  `GET/PUT /api/admin/loyalty/config`, helper `get_current_client` JWT.
- POS: bouton « Souscription fidélité » + modal RGPD (CGU/newsletter/profilage),
  affichage `V######` post-création, gestion 409 doublon.
- Receipt: footer fidélité (membre = nom + n° + solde + gain ; non-membre =
  « auriez gagné X pts » + adhésion).
- Frontend public: `/account/login` magic-link.

**PR2 — Personal Shopper gated + recherche sémantique + alertes tendance**
- Migration `0032`: ajout `ConsentPurpose.trend_alerts` (PG enum) +
  `clients.last_trend_alert_at`.
- `PersonalShopperGatedError` + `_enforce_gating(customer)`: refuse
  non-membre (`loyalty_required`) ou consent profilage absent/révoqué
  (`profiling_consent_required`). Branché sur les 2 endpoints v2.
- Service `personal_shopper_search`:
  - Normalisation requête (lowercase + tokens triés alpha) → cache key sha1.
  - Cache Redis 24 h avec fallback in-memory.
  - Extraction filtres via Claude Haiku 4.5 (JSON strict) + fallback regex
    (taille / couleur / catégorie / prix max).
  - Ranking `trend_score` + recency, top 8 produits `stock|display`.
- Service `trend_alerts`:
  - Cron quotidien 11:00.
  - Sélection produits: `trend_score >= 70` arrivés <36 h.
  - Audience: loyalty active + consent profilage + consent trend_alerts +
    `last_trend_alert_at` NULL ou >7 j.
  - Match cosine 0.6 visual + 0.4 text >= 0.65 vs taste profile.
  - Email Brevo/SMTP/sim avec lien désinscription.
- Endpoints: `POST /crm/account/personal-shopper/{toggle,search}`,
  `GET /crm/account/personal-shopper/live`,
  `POST /crm/account/trend-alerts/toggle`,
  `POST /admin/trend-alerts/run`.
- Frontend public `/account/shopper`: hydratation email magic-link,
  écran bloquant non-membre, toggle 1-clic activation profilage, grille
  4 colonnes responsive, barre recherche sémantique.

**PR3 — Espace client UX (6 zones) + juridique**
- Refonte espace client en 6 zones isolées + mobile-first:
  `/account` (dashboard), `/fidelite`, `/shopper`, `/selection`, `/offres`,
  `/historique`, `/rgpd`.
- Composants partagés `AccountShell` + `AccountNav` (drawer mobile +
  sidebar desktop, hydratation email, déconnexion).
- 5 endpoints support: `GET /crm/account/{coupons,transactions,consents}`,
  `POST /crm/account/consents/{purpose}` (toggle générique avec mirror
  legacy `email_optin`/`sms_optin`).
- Pages légales: CGV art. 6 réécrit (1 €=1 pt, péremption 24 mois,
  3 modes adhésion, PS + alertes tendance, pas de vente en ligne) ;
  mentions légales avec DPO + sous-traitants ; confidentialité avec
  buckets profilage et trend_alerts détaillés (contenu rectifié en 1.1.2
  concernant Anthropic et la durée du profil).
- `/account/rgpd`: consentements lisibles + toggles + export Article 20 +
  demande suppression 30 j (annulable).

**PR4 — Backend renforcé**
- Service `pos_companion.companion_payload()`:
  - Loyalty (points + gain panier + rachat max 50 %).
  - 3 suggestions complémentaires via mapping `CATEGORY_COMPLEMENTS`
    (robe→accessoires/chaussures…), ranking `trend_score`.
  - Coupons applicables (`validate_coupon`).
  - Alertes RFM (`at_risk`, `champion`, `hibernating`) + birthday <7 j +
    milestone fidélité <14 pts.
- Service `predictive_targeting`:
  - `weighted_sales_count(audience='loyal_active')`: ×2 multiplier sur
    les ventes des clientes loyalty active, fallback flat si cohorte <30.
  - `dominant_tastes_loyal_active(period_days=90)`: top catégories /
    marques / couleurs / tailles.
- Endpoints: `GET /pos/clients/{id}/companion`,
  `GET /crm/clients/{id}/full` (6 sections agrégées),
  `GET /admin/predictive/audience`.
- Frontend admin `/clients/[id]`: 6 onglets (Synthèse / Achats / Fidélité /
  Goûts / RGPD / Audit).
- `/clients` table: bouton "Fiche → /clients/[id]" + bouton "Aperçu" modal.
- Composant POS `ClientCompanion`: panneau latéral auto-rafraîchi
  (debounce 300 ms) sur mutation panier.

### Changed

- `cahier_service`: `gold_pct` → `loyalty_pct`, `compute_crm_gold` →
  `compute_crm_loyalty`, `abonnements_gold` → `adhesions_fidelite`.
  La sémantique passe de "tier gold" à "tout membre fidélité".
- `wallet`: drop tier (couleur unique teal `#008678`, label
  « Carte fidélité Vintiz »), `_membership_number()` lit la valeur
  persistée plutôt que SHA-derive.
- `personal_shopper`: drop `tier` du prompt Claude et de `_render_message`.
- `customer_brief`: drop `tier`, ajoute `membership_number` + `loyalty_active`.
- `audit.py`: `_SENSITIVE_FIELDS[LoyaltyAccount]` passe de
  `("tier", "points")` à `("membership_number", "points")`.
- Frontend admin `/clients`: drop colonne tier, affiche `membership_number`.
- Frontend admin `/pos`: drop fonctions `tierLabel/tierColor`, modal
  souscription remplace activation directe.

### Removed

- Système de réservation 48 h: stubs frontend (`/account/data`,
  `/dev/compte`), checks `smoke_prod.sh`, références dans `purge.py`
  et `purge_databases.py` (la table avait déjà été drop par migration 0027).
- Endpoint `/api/reservations/*`, `/api/pos/products/{id}/reservation-holder`
  (déjà supprimés en backend, doc nettoyée).
- Page `/account/data` (remplacée par `/account` + 6 sous-pages).

### Breaking changes

- ⚠️ `loyalty_accounts.tier` colonne supprimée. Code consommant cette
  valeur doit lire `membership_number` (présent sur tous les comptes
  après backfill 0031).
- ⚠️ Wallet passes émis avec ancien format `VTZ-XXXXXXXXXX` deviennent
  invalides — base proche de zéro pré-ouverture, à régénérer pour les
  comptes existants depuis `/clients`.
- ⚠️ Endpoints `?email=` sur `/api/crm/account/*` continuent de
  fonctionner pour PR1-3 mais seront migrés sur JWT cookie dans une
  itération ultérieure (la PR3 utilise toujours `?email=` côté frontend).

### Tests

- 60 nouveaux tests verts (membership_id, loyalty_subscribe, magic_link,
  loyalty_expiry, receipt_loyalty_footer, ps_gating, ps_search,
  trend_alerts, account_endpoints, pos_companion, predictive_targeting,
  clients_full).

### Hotfix au passage

- `apps/site/src/app/account/login/page.tsx`: apostrophe non échappée
  (`Modifier l'email…` → `&apos;`) qui faisait échouer le prod build
  Next.js (commit `ffb5a76`).

---

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
