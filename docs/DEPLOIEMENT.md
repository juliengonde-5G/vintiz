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
