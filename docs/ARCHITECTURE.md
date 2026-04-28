# Architecture Vintiz

## Vue d'ensemble

Vintiz V2 est le systeme de gestion complet pour la boutique Vintiz a Vernon, specialisee dans la vente de vetements de seconde main premium (segment feminin, marques et qualite). Ce n'est ni une friperie ni une ressourcerie. Il couvre la caisse certifiee NF525, la gestion d'inventaire, le CRM client, l'IA Booster (aide a la vente), le site vitrine et le back-office. Le projet est organise en monorepo avec trois applications principales.

## Stack technique

| Couche       | Technologie                        |
| ------------ | ---------------------------------- |
| API          | Python 3.11, FastAPI, SQLAlchemy 2 |
| Base de donnees | PostgreSQL 16                   |
| Cache / file | Redis 7                            |
| Back-office  | Next.js 14, React 18, TypeScript   |
| Site vitrine | Next.js 14, React 18, TypeScript   |
| IA           | Anthropic Claude (API)             |
| Paiement CB  | SumUp (production / sandbox / simulation) |
| Barcode      | python-barcode + Pillow (Code 128) |
| Infra        | Docker Compose, Scaleway VPS       |

## Structure monorepo

```
vintiz/
├── apps/
│   ├── api/          # API FastAPI (modeles, schemas, routes, auth)
│   ├── web/          # Back-office Next.js (caisse, inventaire, stats)
│   └── site/         # Site vitrine vintiz.fr (landing, a propos)
├── assets/           # Logos, lettrages, etiquettes
├── docker/           # Dockerfiles et docker-compose
├── docs/             # Documentation projet
└── scripts/          # Scripts utilitaires
```

## Schema de la base de donnees

Tables principales :

- **users** : comptes utilisateurs, roles (admin, employee)
- **categories** : categories de produits (vetements, accessoires, etc.)
- **products** : articles en inventaire avec prix, taille, etat, photos
- **transactions** : ventes et remboursements (enregistrements de caisse)
- **transaction_items** : lignes de detail par transaction
- **z_reports** : rapports Z quotidiens (cloture de caisse)
- **audit_logs** : journal d'audit pour conformite NF525
- **subscribers** : inscriptions newsletter du site vitrine

## Infrastructure

### Environnement de developpement

Docker Compose orchestre cinq services :

1. **db** : PostgreSQL 16 Alpine (port 5432)
2. **redis** : Redis 7 Alpine (port 6379)
3. **api** : FastAPI via Uvicorn (port 8000)
4. **web** : Next.js back-office (port 3000)
5. **site** : Next.js site vitrine (port 3001)

### Production (Scaleway VPS)

- VPS Scaleway DEV1-M (3 vCPU, 4 Go RAM)
- Docker Compose production (`docker/docker-compose.prod.yml`)
- Reverse proxy **Caddy** avec HTTPS automatique (Let's Encrypt)
- Sauvegardes PostgreSQL quotidiennes (`scripts/backup.sh`, crontab 3h)

**Domaines :**
- `vintiz.fr` → Site vitrine (landing page, newsletter)
- `app.vintiz.fr` → Back-office PWA (caisse, inventaire, dashboard)
- `api.vintiz.fr` → API FastAPI (REST)

**Deploiement :**
```bash
# Premier deploiement
./scripts/deploy.sh --first-run

# Mises a jour
./scripts/deploy.sh
```

## Architecture POS hardware

Le POS (`apps/web/src/app/pos`) est concu pour fonctionner avec le materiel
boutique suivant :

```
                       [ iPad Safari ]
                     https://app.vintiz.fr
                              |
           +------------------+------------------+
           |                  |                  |
           v                  v                  v
  [ Douchette USB HID ]  [ Imprimante 80mm ]  [ TPE SumUp Solo ]
    Inateck 160B            AirPrint Wi-Fi      Wi-Fi / compte
  (tape + Entree)         port RJ11 ---> [ Tiroir-caisse ]
```

Flux d'un encaissement :

1. **Scan** — la douchette tape le barcode + *Enter* dans le champ recherche
   POS (auto-focus). Le handler resout le code via
   `GET /api/inventory/products/search?q=…` (match exact sur `barcode` prioritaire,
   sinon seul resultat) et ajoute au panier.
2. **Encaisser** — choix du moyen de paiement :
   - *Especes* — numpad tactile, rendu monnaie calcule.
   - *CB* — `POST /api/pos/payments/cb/initiate` cree un checkout SumUp,
     l'UI poll toutes les 3 s jusqu'a `PAID` / `FAILED`.
   - *Cheque* — saisie libre.
3. **Validation** — `POST /api/pos/transactions` cree la vente + chaine de
   hash NF525.
4. **Ticket** — `GET /api/pos/transactions/{id}/receipt` renvoie un texte 80 mm.
   Bouton *Imprimer* → `window.print()` AirPrint → l'imprimante declenche le
   kick pulse RJ11 = tiroir ouvert.
5. **Cloture** — en fin de journee, fermeture caisse + rapport Z.

## Conformite NF525

Le systeme de caisse respecte les exigences NF525 :

- **Chaine de hash** : chaque transaction est liee a la precedente via un hash SHA-256, garantissant l'inalteration des donnees.
- **Rapports Z** : cloture de caisse quotidienne avec totaux, TVA et hash de verification.
- **Journal d'audit** : toutes les operations critiques (ventes, modifications, suppressions) sont tracees dans `audit_logs` avec horodatage, utilisateur et detail de l'action.
- **Inalterabilite** : aucune suppression physique des transactions ; les annulations creent de nouvelles ecritures.
- **Archivage** : conservation des donnees pendant la duree legale (6 ans minimum).

## Phases de developpement

### Phase 1 -- MVP Caisse & Inventaire (LIVREE)

- Structure monorepo, Docker, PostgreSQL, Redis
- Page "Ouverture Prochaine" (vintiz.fr) avec collecte emails
- API FastAPI : auth JWT/RBAC, inventaire CRUD, POS, CRM, reporting
- Conformite NF525 : hash chain SHA-256, Z reports, audit trail
- Frontend PWA : login, dashboard, inventaire, caisse, cloture Z
- Services : code-barres, etiquettes, tickets, tiroir-caisse
- Script seed data (admin, categories, grille tarifaire, zones)
- Deploiement : Caddy reverse proxy, HTTPS, backup automatise

### Phase 2 -- CRM & Reporting avance (LIVREE)

Fidelite client (cagnotte, ventes privees), dashboard analytics, rapports predictifs, integration meteo.

### Phase 3 -- IA Booster (LIVREE)

Claude Vision (analyse photo produit), scoring tendance, mapping surface de vente, mode styliste cabine, recommandations hebdomadaires.

### Phase 4 -- Hardware POS (LIVREE)

iPad + douchette Inateck 160B + imprimante 80 mm + tiroir RJ11 + TPE SumUp Solo.
Handler scanner, impression AirPrint, ouverture tiroir via driver, SumUp
sandbox avec event log live et approve/decline manuel, 15 produits de test
pre-integres pour la mise en service (`docs/POS_TEST_BARCODES.md`).

### Phase 5 -- Site vitrine complet & Social

Site vintiz.fr public complet, extranet client, gestion reseaux sociaux, SEO local.

### Audit avril 2026 -- Phases P1 -> P4 (LIVREE)

Plan d'action issu de l'audit `docs/AUDIT_2026_04.md`, livre du 16 au 26 avril
2026. Voir `docs/AUDIT_2026_04_PHASE4_CLOSE.md` pour la cartographie complete
ticket -> PR.

- **P1** -- conformite NF525 (hash chain renforce + DGFiP export), RGPD
  (consent ledger + export portable + soft delete 30j + cron purge),
  cashier PIN, refund flow CB/cheque/avoir, multi-photos produit.
- **P2** -- event store generique, embeddings pgvector (256-dim),
  Personal Shopper v2, life-cycle FSM produit, mapping booster vitrine,
  POS offline (IndexedDB + replay idempotent).
- **P3** -- markdown engine (regles declaratives + cron nocturne),
  brand tiers (table editable manager), visibility module (snapshots SEO,
  posts sociaux Claude, suggested replies avis Google), import CSV.
- **P4** -- KPIs retail (sell-through, GMROI, AIT, CA/m^2/mois),
  rapport ESS Solidarite Textiles, segmentation RFM mensuelle,
  email gateway Brevo (Brevo > SMTP > simulation), Wallet pass payload
  (Apple .pkpass + Google LoyaltyObject), email anniversaire + coupon
  -10% 7j, email hebdo nouvelles arrivees, badges IA POS (velocite /
  stale / marque / score), mobile dashboard sticky.
- **Refonte Relation Client (avril 2026)** -- programme fidelite simplifie
  (1 €=1 pt, V######, peremption 24mo, 3 modes adhesion configurables),
  magic-link OTP email pour l'espace client (fin du `?email=`),
  Personal Shopper gated (membre + consent profilage) avec recherche
  semantique texte libre (Claude Haiku + cache Redis 24h), alertes
  produit tendance (cron 11:00, frequency cap 7j), espace client en
  6 zones isolees (`/account` + 5 sous-pages), POS Companion (panneau
  cart-aware: loyalty + suggestions complementaires + coupons + alertes
  RFM), fiche client admin `/clients/[id]` 6 onglets, predictive
  engine `audience='loyal_active'` ×2 multiplier. Suppression complete
  du systeme de reservation 48h.

Suite : 422 tests pytest, 32 migrations Alembic, 15 crons APScheduler,
~140 endpoints REST, 14 pages admin web.
