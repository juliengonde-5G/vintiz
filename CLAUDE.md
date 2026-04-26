# Vintiz — Guide de développement

Boutique de seconde main premium — Vernon, Normandie.

## Architecture

Monorepo avec 3 applications :

```
apps/
  api/          FastAPI (Python 3.11) — API REST + services IA
  web/          Next.js 14 (App Router) — Interface d'administration
  site/         Next.js 14 — Site vitrine public + espace client
scripts/
  seed_data.py            300 produits + 50 clients + 200 transactions
  seed_test_products.py   15 produits de test POS + codes-barres PNG
  deploy.sh               Déploiement production (Docker Compose)
  backup.sh               Backup PostgreSQL
docs/
  POS_TEST_BARCODES.md    Codes-barres scannables + procédure hardware
  test_barcodes/*.png     Barcodes Code 128 pour la douchette
```

## Stack technique

| Couche | Technologie |
|---|---|
| API backend | FastAPI + SQLAlchemy async (PostgreSQL) |
| Auth | JWT (python-jose) |
| IA | Anthropic Claude (claude-haiku-4-5) |
| Payment CB | SumUp API — 3 modes : production / sandbox / simulation |
| Email | SMTP standard (simulation si non configuré) |
| SMS | Twilio (simulation si non configuré) |
| Météo | OpenWeatherMap API |
| Admin UI | Next.js 14 App Router + Tailwind CSS |
| Site public | Next.js 14 App Router + Tailwind CSS |
| Barcode | python-barcode + Pillow (Code 128) |
| Impression ticket | AirPrint iPad via `window.print()` format 80 mm |
| Douchette | USB HID (Inateck 160B), champ recherche POS auto-focus |
| Tiroir-caisse | Kick RJ11 via imprimante thermique (option driver) |

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
POST /api/auth/login                         Connexion (manager username/password)
POST /api/pos/cashier/login                  Identifier le cashier au POS via PIN 4 chiffres
POST /api/pos/cashier/set-pin                Définir/changer un PIN (manager only)
POST /api/pos/cashier/clear-pin              Retirer un PIN (manager only)
GET  /api/pos/cashier/list                   Lister utilisateurs + statut PIN (manager only)
GET  /api/inventory/products                 Liste produits (paginée)
GET  /api/inventory/products/search?q=…      Recherche (filtre stock+display par défaut, &include_sold=true sinon)
GET  /api/inventory/products/{id}            Fiche produit
GET  /api/inventory/products/{id}/label      Étiquette PNG
GET  /api/inventory/products/{id}/score      Score détaillé
POST /api/pos/transactions                   Créer une vente
GET  /api/pos/transactions/{id}/receipt      Texte du ticket (80 mm)
POST /api/pos/transactions/{id}/resend       Renvoyer ticket (email/SMS)
POST /api/pos/drawer/open                    Ouvrir la caisse (fond initial)
POST /api/pos/drawer/close                   Fermer + rapport Z
GET  /api/pos/drawer/current                 État tiroir
POST /api/pos/payments/cb/initiate           Initier paiement SumUp
GET  /api/pos/payments/cb/{id}/status        Poller statut SumUp
DELETE /api/pos/payments/cb/{id}             Annuler checkout
GET  /api/pos/payments/cb/sandbox/config     Config SumUp (env, clés)
GET  /api/pos/payments/cb/sandbox/state      Event log sandbox (live)
POST /api/pos/payments/cb/sandbox/{id}/approve  Valider manuellement
POST /api/pos/payments/cb/sandbox/{id}/decline  Refuser manuellement
GET  /api/admin/weather                      Météo Vernon
GET  /api/admin/audit-logs                   Journal AuditLog (manager only, filtres entity/action/user_id)
GET  /api/ai/weekly-checklist                Checklist semaine IA
GET  /api/ai/trends                          Tendances mode
POST /api/ai/persona/marketing               Rapport marketing IA
POST /api/ai/persona/juridique               Audit RGPD IA
GET  /api/crm/clients/lookup?email=…         Lookup client public
GET  /api/crm/clients/personal-shopper?email=…  Personal shopper
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

### 5. Paramétrage zones
- 7 zones prédéfinies (plan boutique L 98m²)
- Édition : nom, description, capacité, types de produits, couleur

### 6. Espace client (site public)
- Login par email (sans mot de passe)
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

Branche de travail : `claude/prepare-pos-software-stoSD`

```bash
git push -u origin claude/prepare-pos-software-stoSD
```

## Hardware POS — mise en service

Matériel supporté :

| Composant | Référence testée | Connexion |
|---|---|---|
| Tablette caisse | iPad (Safari) | — |
| Douchette code-barres | **Inateck 160B** | USB HID (clavier) |
| Imprimante ticket | 80 mm thermique | AirPrint (Wi-Fi) |
| Tiroir-caisse | RJ11 | Branché sur imprimante |
| TPE | **SumUp Solo** | Wi-Fi / compte SumUp |

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
