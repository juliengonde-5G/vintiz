# Architecture Vintiz V2

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
- Docker Compose en mode production
- Reverse proxy Caddy / Nginx avec HTTPS automatique
- Sauvegardes PostgreSQL quotidiennes

## Conformite NF525

Le systeme de caisse respecte les exigences NF525 :

- **Chaine de hash** : chaque transaction est liee a la precedente via un hash SHA-256, garantissant l'inalteration des donnees.
- **Rapports Z** : cloture de caisse quotidienne avec totaux, TVA et hash de verification.
- **Journal d'audit** : toutes les operations critiques (ventes, modifications, suppressions) sont tracees dans `audit_logs` avec horodatage, utilisateur et detail de l'action.
- **Inalterabilite** : aucune suppression physique des transactions ; les annulations creent de nouvelles ecritures.
- **Archivage** : conservation des donnees pendant la duree legale (6 ans minimum).

## Phases de developpement

### Phase 1 -- Fondations (en cours)

Structure monorepo, infrastructure Docker, modeles de donnees, authentification JWT, scaffold API et front-end.

### Phase 2 -- MVP Caisse

Systeme de caisse complet : scan / saisie produit, panier, paiement (especes, CB, mixte), tickets, conformite NF525, rapports Z.

### Phase 3 -- Gestion et intelligence

Inventaire avance (import Excel, etiquettes, stats), tableau de bord analytique, assistant IA pour pricing et descriptions.

### Phase 4 -- Site vitrine et lancement

Site vintiz.fr public, newsletter, integration reseaux sociaux, deploiement production sur Scaleway.
