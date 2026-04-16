# Changelog Vintiz

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
