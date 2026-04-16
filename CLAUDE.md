# Vintiz — Guide de développement

Boutique de seconde main premium — Vernon, Normandie.

## Architecture

Monorepo avec 3 applications :

```
apps/
  api/          FastAPI (Python 3.11) — API REST + services IA
  web/          Next.js 14 (App Router) — Interface d'administration
  site/         Next.js 14 — Site vitrine public + espace client
scripts/        Scripts de maintenance (seed_data.py)
```

## Stack technique

| Couche | Technologie |
|---|---|
| API backend | FastAPI + SQLAlchemy async (PostgreSQL) |
| Auth | JWT (python-jose) |
| IA | Anthropic Claude (claude-haiku-4-5) |
| Payment CB | SumUp API (simulation si non configuré) |
| Email | SMTP standard (simulation si non configuré) |
| SMS | Twilio (simulation si non configuré) |
| Météo | OpenWeatherMap API |
| Admin UI | Next.js 14 App Router + Tailwind CSS |
| Site public | Next.js 14 App Router + Tailwind CSS |
| Barcode | python-barcode + Pillow |

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
# Obligatoire
DATABASE_URL=postgresql+asyncpg://user:password@localhost/vintiz
SECRET_KEY=votre-cle-secrete-jwt

# IA (sans cette clé, fallback sur données statiques)
ANTHROPIC_API_KEY=sk-ant-...

# Météo Vernon (sans cette clé, widget météo indisponible)
OPENWEATHER_API_KEY=votre-cle-openweather

# CB SumUp (sans ces clés, simulation automatique)
SUMUP_API_KEY=votre-cle-sumup
SUMUP_MERCHANT_CODE=votre-merchant-code

# Email SMTP (sans ces clés, simulation)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=email@domaine.fr
SMTP_PASSWORD=mot-de-passe

# SMS Twilio (sans ces clés, simulation)
TWILIO_ACCOUNT_SID=ACxxxx
TWILIO_AUTH_TOKEN=token
TWILIO_FROM=+33xxxxxxxxx

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Identifiants par défaut

| Utilisateur | Mot de passe | Rôle |
|---|---|---|
| admin | vintiz2026 | Manager |

## Structure API

Base URL: `http://localhost:8000`

| Module | Préfixe | Description |
|---|---|---|
| Auth | `/api/auth` | Login, refresh token |
| Inventaire | `/api/inventory` | CRUD produits, étiquettes, score |
| POS | `/api/pos` | Transactions, caisse, CB SumUp |
| CRM | `/api/crm` | Clients, fidélité, personal shopper |
| IA Booster | `/api/ai` | Vision, checklist, tendances, personas |
| Admin | `/api/admin` | Météo, zones, scoring mensuel |
| Rapports | `/api/reports` | Dashboard, statistiques |

### Endpoints clés

```
POST /api/auth/login                    Connexion
GET  /api/inventory/products            Liste produits (paginée)
GET  /api/inventory/products/{id}       Fiche produit
GET  /api/inventory/products/{id}/label Étiquette PNG
GET  /api/inventory/products/{id}/score Score détaillé
POST /api/pos/transactions              Créer une vente
POST /api/pos/payments/cb/initiate      Initier paiement SumUp
GET  /api/pos/transactions/{id}         Détail ticket
POST /api/pos/transactions/{id}/resend  Renvoyer ticket (email/SMS)
GET  /api/admin/weather                 Météo Vernon
GET  /api/ai/weekly-checklist           Checklist semaine IA
GET  /api/ai/trends                     Tendances mode
POST /api/ai/persona/marketing          Rapport marketing IA
POST /api/ai/persona/juridique          Audit RGPD IA
GET  /api/crm/clients/lookup?email=...  Lookup client public
GET  /api/crm/clients/personal-shopper?email=... Personal shopper
```

## Fonctionnalités principales

### 1. Inventaire
- Création produit avec génération automatique code-barres
- Fiche produit cliquable avec score détaillé (6 composantes)
- Date de mise en rayon, emplacement zone
- Édition inline prix / zone / statut
- Bouton "Générer étiquette" → PNG téléchargeable/imprimable

### 2. POS (Caisse)
- Interface tactile optimisée pour tablette (≥768px)
- Recherche produit par scan code-barres ou texte
- Remises par article (0-30%)
- 3 modes de paiement : Espèces (rendu monnaie), CB SumUp (TPE), Chèque
- Fidélité : affichage points, toggle rachat (1pt = 0,10€)
- Reçu généré et envoyable par email/SMS

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

### 5. Paramétrage zones
- 7 zones prédéfinies (plan boutique L 98m²)
- Édition : nom, description, capacité, types de produits, couleur

### 6. Espace client (site public)
- Login par email (sans mot de passe)
- Carte fidélité (Bronze/Silver/Gold)
- Historique achats
- Personal Shopper IA : sélection personnalisée basée sur l'historique

## Design tokens (Tailwind)

```css
teal:      #1A7A6A  (couleur principale)
rose/pink: #F4A7B9  (accent)
cream/bg:  #FAF8F5  (fond)
charcoal:  #2C2C2C  (texte)
gold:      #C9A84C  (fidélité Gold)
```

## Moteur prédictif

Voir `docs/PREDICTIVE_ENGINE.md` pour la documentation détaillée.

## Tests et seed data

```bash
# Seeder 300 produits + 50 clients + 200 transactions
PYTHONPATH=apps/api python scripts/seed_data.py

# Le script est idempotent (peut être relancé sans dupliquer)
```

## Git workflow

Branche de travail : `claude/prepare-pos-software-stoSD`

```bash
git push -u origin claude/prepare-pos-software-stoSD
```

## Hardware POS — test de mise en service

Voir `docs/POS_TEST_BARCODES.md` pour la série de 15 produits de test +
codes-barres scannables (Code128), et la procédure complète de test avec
iPad, douchette USB, imprimante 80 mm, tiroir RJ11 et TPE SumUp Solo.

```bash
# 1. Configurer SumUp sandbox
SUMUP_ENVIRONMENT=sandbox
SUMUP_API_KEY=<sandbox-key>     # vide → mode simulation auto

# 2. Seeder les 15 produits de test et régénérer les codes-barres
PYTHONPATH=apps/api python scripts/seed_test_products.py
```
