# Guide de deploiement Vintiz V3

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
./scripts/deploy.sh
```

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
