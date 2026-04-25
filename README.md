# Vintiz

Logiciel de gestion pour boutique de seconde main premium — Vernon, Normandie.

## Structure du projet

```
apps/
  api/          FastAPI (Python 3.11) — API REST
  web/          Next.js 14 — Interface d'administration
  site/         Next.js 14 — Site vitrine public + espace client
docker/         Dockerfiles + docker-compose.yml
scripts/        seed_data.py, diag.sh, deploy.sh
.claude/        Hooks Claude Code (session-start)
```

## Démarrage

### Développement local

```bash
# PostgreSQL (Ubuntu)
pg_ctlcluster 16 main start

# API
cd apps/api && pip install -r requirements.txt
PYTHONPATH=apps/api uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Admin UI
cd apps/web && npm install && npm run dev        # :3000

# Site vitrine
cd apps/site && npm install && npm run dev       # :3001

# Données de test
PYTHONPATH=apps/api python scripts/seed_data.py
```

Identifiants par défaut : `admin` / `vintiz2026`

### Production (VPS Docker)

```bash
cd /opt/vintiz
docker compose -f docker/docker-compose.prod.yml up -d
bash scripts/diag.sh   # vérifier l'état
```

## Architecture de production

Tous les services tournent en Docker Compose sur le VPS (`/opt/vintiz`).
Caddy assure le reverse proxy HTTPS sur les ports 80/443.

| Service        | Technologie          | Accès                     |
|----------------|----------------------|---------------------------|
| `vintiz-api`   | FastAPI Python 3.11  | interne :8000 (via Caddy) |
| `vintiz-db`    | PostgreSQL 16        | interne :5432             |
| `vintiz-web`   | Next.js 14           | interne :3000 (via Caddy) |
| `vintiz-site`  | Next.js 14           | interne :3001 (via Caddy) |
| `vintiz-caddy` | Caddy 2              | public :80 :443           |
| `vintiz-redis` | Redis 7              | interne :6379             |

> **Note** : le port 8000 n'est pas exposé à l'hôte. `curl localhost:8000` depuis le VPS échoue — utiliser `docker exec vintiz-api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"`.

## Variables d'environnement

Fichier `.env` à la racine du projet (copier depuis `.env.example`) :

```env
DATABASE_URL=postgresql+asyncpg://vintiz:PASSWORD@db:5432/vintiz
SECRET_KEY=...
ANTHROPIC_API_KEY=sk-ant-...
OPENWEATHER_API_KEY=...
POSTGRES_USER=vintiz
POSTGRES_PASSWORD=...
POSTGRES_DB=vintiz
```

> En dev, `DATABASE_URL` utilise `localhost` à la place de `db`.

## Déploiement

```bash
# Depuis la machine de dev
git push -u origin claude/fix-product-features-LbqVr

# Sur le VPS
cd /opt/vintiz
git fetch origin claude/fix-product-features-LbqVr
git reset --hard origin/claude/fix-product-features-LbqVr
docker compose -f docker/docker-compose.prod.yml up -d --build
```

## Diagnostic

```bash
bash scripts/diag.sh
```

Détecte automatiquement Docker vs local, vérifie PostgreSQL, l'API, les tables et Caddy. Redémarre automatiquement ce qui ne répond pas.
