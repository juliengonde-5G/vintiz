# Guide de deploiement Vintiz

## Pre-requis serveur (VPS Scaleway)

- Ubuntu 22.04+ ou Debian 12+
- Docker Engine 24+ et Docker Compose v2
- Git
- Minimum 3 vCPU, 4 Go RAM, 40 Go SSD

## DNS

Configurer les enregistrements A (pointer vers l'IP du VPS) :

| Domaine | Type | Valeur |
|---|---|---|
| vintiz.fr | A | IP_DU_VPS |
| www.vintiz.fr | A | IP_DU_VPS |
| app.vintiz.fr | A | IP_DU_VPS |
| api.vintiz.fr | A | IP_DU_VPS |

## Installation sur le serveur

```bash
# 1. Cloner le projet (branche main)
git clone -b main https://github.com/juliengonde-5G/vintiz.git /opt/vintiz
cd /opt/vintiz

# 2. Configurer l'environnement
cp .env.production.template .env
nano .env
# → Remplir POSTGRES_PASSWORD (mot de passe fort)
# → Remplir SECRET_KEY (openssl rand -hex 32)
# → Remplir ANTHROPIC_API_KEY
# → Mettre a jour DATABASE_URL avec le mot de passe choisi
# → Configurer SumUp (voir section « Hardware POS » ci-dessous)

# 3. Premier deploiement
chmod +x scripts/deploy.sh scripts/backup.sh
./scripts/deploy.sh --first-run

# 4. Configurer le backup automatique (tous les jours a 3h)
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/vintiz/scripts/backup.sh >> /var/log/vintiz-backup.log 2>&1") | crontab -
```

## Verification post-deploiement

```bash
# Verifier que tous les conteneurs tournent
docker compose -f docker/docker-compose.prod.yml ps

# Verifier l'API
curl https://api.vintiz.fr/api/health

# Verifier le site
curl -I https://vintiz.fr

# Verifier le back-office
curl -I https://app.vintiz.fr

# Consulter les logs
docker compose -f docker/docker-compose.prod.yml logs -f

# Smoke test complet (read-only, valide les routes Phase 4)
bash scripts/smoke_prod.sh https://api.vintiz.fr
# avec token manager pour les checks authentifies :
export VINTIZ_API_TOKEN="$(curl -s -X POST https://api.vintiz.fr/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"vintiz2026"}' | jq -r .access_token)"
bash scripts/smoke_prod.sh https://api.vintiz.fr
```

## Mise a jour

```bash
cd /opt/vintiz
./scripts/deploy.sh                   # maj code + migrations Alembic
./scripts/deploy.sh --test-products   # maj + seed 15 produits de test POS
./scripts/deploy.sh --first-run       # premier deploiement (+ seed 300 produits)
./scripts/deploy.sh --rollback        # retour version precedente
```

## Hardware POS — mise en service boutique

### 1. Configuration SumUp (`.env`)

```env
SUMUP_ENVIRONMENT=sandbox         # sandbox | production
SUMUP_API_KEY=                    # vide → simulation en memoire
SUMUP_MERCHANT_CODE=
SUMUP_SANDBOX_AUTO_DELAY_SEC=5    # 0 = approbation manuelle
```

Trois modes :

- **production** — appels reels api.sumup.com (frais SumUp). Necessite cle
  production + merchant code.
- **sandbox** — cle SumUp sandbox, appels API reels en mode test.
- **simulation** (defaut sans cle) — sandbox en memoire. Event log visible
  dans `/settings > Paiement`, approve/decline manuel par checkout, transition
  PENDING → PAID apres `SUMUP_SANDBOX_AUTO_DELAY_SEC` secondes.

### 1bis. Configuration Phase 4 (email + wallet)

```env
# Email transactional (P4-003) — gateway unifie Brevo > SMTP > simulation.
# Si BREVO_API_KEY est posee, Brevo gagne. Sinon fallback SMTP.
# Sinon simulation (logge la tentative, ne plante pas).
BREVO_API_KEY=                    # xkeysib-xxx
EMAIL_FROM_ADDRESS=noreply@vintiz.fr
EMAIL_FROM_NAME=Vintiz Vernon

# Wallet pass (P4-004) — payload pret, signing a plugger cote ops
WALLET_PASS_TYPE_IDENTIFIER=pass.fr.vintiz.loyalty
WALLET_TEAM_IDENTIFIER=           # ABCDE12345 (Apple Developer)
WALLET_GOOGLE_ISSUER_ID=          # 19 chiffres (Google Pay & Wallet)
WALLET_GOOGLE_CLASS_SUFFIX=vintiz_loyalty
```

Sans `BREVO_API_KEY`, les crons anniversaire (09:00 quotidien) et nouvelles
arrivees (vendredi 10:00) tournent en mode simulation : les coupons sont
crees en DB mais aucun email n'est envoye. Logs API : "[email simulated]".

#### Activation Brevo (recommandee en prod)

Brevo (ex-Sendinblue) offre 300 emails transactionnels gratuits par jour,
suffisant pour la majorite des boutiques. Procedure :

1. Creer un compte gratuit sur https://app.brevo.com/account/register.
2. Verifier le domaine d'envoi (DKIM/SPF) via Brevo > Settings > Senders &
   IP. Obligatoire pour eviter le spam (sinon les codes magic-link tomberont
   dans l'onglet "Promotions" voire en spam).
3. Creer une cle API : Brevo > SMTP & API > API Keys > Generer une nouvelle
   cle (cocher "Send transactional emails"). Format `xkeysib-…`.
4. Coller la cle dans **/settings > Communication** (UI back-office) : la
   valeur est persistee en DB et prend le pas sur les variables d'env. Saisir
   "Adresse expediteur" + "Nom expediteur" puis cliquer "Enregistrer".
5. Cliquer "Envoyer un email de test" pour valider la chaine end-to-end.
6. Si l'email arrive : c'est OK. Si l'envoi est marque "SIMULE", c'est que la
   cle n'a pas ete persistee — verifier les permissions du fichier
   `data/app_config.json` (lecture/ecriture par l'utilisateur API).

Alternativement, on peut poser `BREVO_API_KEY=xkeysib-…` dans `.env` du
backend et redeployer. La valeur UI reste prioritaire, ce qui permet une
rotation de cle sans redeploiement.

#### Mode simulation explicite (dev / staging)

Pour developper sans envoyer de vrais emails, mettre Provider = "Simulation"
dans /settings > Communication. Tous les emails seront logues mais pas
envoyes. Le code OTP magic-link apparaitra dans les logs API au format
`[email simulated] to=… subject=Code de connexion Vintiz : 123456`.

#### Signature des passes Wallet

La signature `.pkpass` Apple est desormais implementee si toutes les variables
suivantes sont posees :

```env
WALLET_TEAM_IDENTIFIER=ABCDE12345          # Apple Developer Team ID
WALLET_PASS_TYPE_IDENTIFIER=pass.fr.vintiz.loyalty
WALLET_APPLE_P12_PATH=/secrets/vintiz_pass.p12   # cert + cle privee
WALLET_APPLE_P12_PASSWORD=...
WALLET_APPLE_WWDR_PATH=/secrets/AppleWWDRCAG4.pem # cert intermediaire WWDR (G4)
WALLET_PASS_ASSETS_DIR=/opt/vintiz/wallet-assets/ # icon.png, icon@2x.png, logo.png
```

Procedure :
1. Compte Apple Developer (99$/an) -> Certificates, Identifiers & Profiles ->
   creer un Pass Type ID `pass.fr.vintiz.loyalty`.
2. Generer un certificat de signature (.cer) puis l'exporter en .p12 avec sa
   cle privee depuis Keychain.
3. Telecharger AppleWWDRCAG4.cer (Apple Worldwide Developer Relations - G4)
   et le convertir en PEM (`openssl x509 -inform DER -in AppleWWDRCAG4.cer
   -out AppleWWDRCAG4.pem`).
4. Deposer le .p12 + le .pem dans `/secrets/` et poser les vars d'env.
5. Optionnel : deposer 3 icones PNG (29x29, 58x58, 87x87) dans
   WALLET_PASS_ASSETS_DIR -> meilleur rendu sur l'iPhone.
6. Tester : `curl -i "https://api.vintiz.fr/api/crm/account/wallet/apple?email=cliente@x.fr"`
   -> doit retourner `Content-Type: application/vnd.apple.pkpass` + binaire.

Pour Google Wallet :
```env
WALLET_GOOGLE_ISSUER_ID=3388000000022000000   # 19 chiffres, donne par Google Pay & Wallet Console
WALLET_GOOGLE_CLASS_SUFFIX=vintiz_loyalty
WALLET_GOOGLE_SERVICE_ACCOUNT_JSON=/secrets/google-wallet-sa.json
```

Sans ces certs/credentials, le bouton "Ajouter a Apple/Google Wallet" renvoie
une 503 explicite et le bouton "Telecharger le QR" reste fonctionnel (PNG
scanne au POS pour identifier la cliente).

### 2. Seeder les 15 produits de test

```bash
# Sur le VPS
cd /opt/vintiz
./scripts/deploy.sh --test-products
# ou directement dans le conteneur
docker exec vintiz-api python scripts/seed_test_products.py
```

Les 15 codes-barres Code 128 (TEST0001 → TEST0015) sont dans le repo :
`docs/POS_TEST_BARCODES.md` + `docs/test_barcodes/*.png`.

### 3. Cote physique (boutique)

| Materiel | Branchement |
|---|---|
| iPad | Safari → `https://app.vintiz.fr/pos` |
| Douchette Inateck 160B | USB HID (adaptateur Lightning/USB-C sur iPad) |
| Imprimante 80 mm | AirPrint (Wi-Fi) + option « open drawer on print » |
| Tiroir-caisse | RJ11 branche sur l'imprimante |
| TPE SumUp Solo | Compte SumUp (sandbox ou production) |

### 4. Verification

```bash
# Config SumUp active (necessite authentification)
curl -H "Authorization: Bearer <TOKEN>" https://api.vintiz.fr/api/pos/payments/cb/sandbox/config
# → { "environment": "sandbox", "api_key_set": false, ... }

# Produit test present
curl https://api.vintiz.fr/api/inventory/products/search?q=TEST0001 \
     -H "Authorization: Bearer <TOKEN>"
```

Sur l'iPad : scanner `TEST0001` → produit ajoute au panier → *Encaisser*
especes → *Imprimer* → ticket papier + ouverture tiroir = OK.

## Acces par defaut

| Service | URL | Identifiants |
|---|---|---|
| Site vitrine | https://vintiz.fr | (public) |
| Back-office | https://app.vintiz.fr | admin / vintiz2026 |
| API docs | https://api.vintiz.fr/docs | (Swagger UI) |

**IMPORTANT** : Changer le mot de passe admin apres la premiere connexion.

## Architecture des services

```
Internet
   |
   v
[Caddy :80/:443]  (HTTPS automatique Let's Encrypt)
   |
   +-- vintiz.fr       → [site :3001]   Next.js
   +-- app.vintiz.fr   → [web :3000]    Next.js PWA
   +-- api.vintiz.fr   → [api :8000]    FastAPI
                              |
                    +---------+---------+
                    |                   |
              [db :5432]          [redis :6379]
              PostgreSQL 16        Redis 7
```

## Maintenance

```bash
# Logs d'un service specifique
docker logs vintiz-api -f --tail 100

# Restart d'un service
docker compose -f docker/docker-compose.prod.yml restart api

# Backup manuel
./scripts/backup.sh

# Restauration d'un backup
gunzip -c /opt/vintiz/backups/vintiz_XXXXXXXX.sql.gz | docker exec -i vintiz-db psql -U vintiz vintiz
```

### Rotation SECRET_KEY (annuelle ou sur incident)

`SECRET_KEY` signe les JWT manager + magic-link client. La faire tourner
invalide tous les JWT en circulation — chaque utilisateur devra se
reconnecter. Procédure :

```bash
# 1. Générer une nouvelle clé (32 bytes hex)
NEW_SECRET=$(openssl rand -hex 32)

# 2. Sauvegarder l'ancienne clé en variable secondaire si besoin de
#    grace period courte (sinon ignorer cette étape)
ssh vintiz "grep ^SECRET_KEY= /opt/vintiz/.env"

# 3. Mettre à jour /opt/vintiz/.env (sur le VPS)
ssh vintiz "sed -i \"s|^SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET|\" /opt/vintiz/.env"

# 4. Restart de l'API (les sessions existantes deviennent invalides)
ssh vintiz "cd /opt/vintiz && docker compose -f docker/docker-compose.prod.yml restart api"

# 5. Vérifier que le boot a réussi (refus de boot si SECRET_KEY vide)
ssh vintiz "docker logs vintiz-api --tail 20"
```

**Quand la faire tourner** :
- annuelle préventive (calendrier sécurité)
- immédiate si fuite suspectée (push accidentel sur Git, machine compromise)
- après le départ d'un dev ayant eu accès au VPS

`ADMIN_BOOTSTRAP_KEY` (utilisée seulement par `/admin/create-tables`)
peut être tournée indépendamment et ne casse aucune session active.

## Pieges connus migrations / build

- **Numerotation des revisions Alembic** : si deux PR ajoutent en parallele
  une migration `revision = "00XX"` (exemple recent : `0022_add_fk_indexes`
  vs `0022_remap_store_zones`), `alembic upgrade head` echoue avec
  `Multiple head revisions`. Toujours re-baser les revisions sur la vraie
  tete (`alembic heads` localement avant de pousser).
- **Hash de mot de passe** : `app/core/security.py` importe `bcrypt`
  directement (et plus via `passlib`). Le pin `bcrypt>=4.1.0` doit rester
  dans `apps/api/pyproject.toml`, sinon le boot uvicorn casse avec
  `ModuleNotFoundError: bcrypt`.
- **Migration 0026 (remap zones)** : passe les `products.zone_id` qui
  pointent vers les anciennes zones (Vitrine gauche, Mur fond, …) a
  `NULL`. C'est attendu — les produits restent visibles dans
  l'inventaire, ils sont juste a re-affecter a une des 11 nouvelles
  zones via `/zones/{id}` ou `merchandising.suggest_zone()`.
