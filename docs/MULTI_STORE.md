# Vintiz multi-boutique — chaîne d'installation & exportabilité

> Statut : **plan d'action + socle d'installation livré** (phase 1).
> Cette note raisonne globalement sur le passage d'une application mono-boutique
> (Vintiz Vernon) à une application **exportable** sur d'autres boutiques, et
> décrit la chaîne d'installation/paramétrage à mettre en place.

## 1. Constat de départ

L'application est aujourd'hui **mono-tenant** :

- une seule base PostgreSQL (`DATABASE_URL`), un seul schéma `public` ;
- aucune notion de `store_id` / `tenant_id` sur les ~25 modèles ;
- l'identité boutique (nom, adresse, horaires, TVA, surface…) vit dans
  `data/app_config.json` (`shop_info`), le matériel dans `data/hardware.json` ;
- les rôles utilisateurs (`manager` / `collaborateur`) sont globaux ;
- la TVA est gérée **par produit** (`Product.tva_rate`, défaut 20 %), gelée à la
  vente sur `TransactionItem.tva_rate` (NF525) ; un défaut boutique existe dans
  `shop_info.vat_rate_percent` (référence).

Conclusion : le comportement « par boutique » est déjà **piloté par fichier de
config** (app_config + hardware + le flag `features.zoning_enabled` ajouté). Ce
qui manque, c'est (a) une **isolation des données** entre boutiques et (b) une
**chaîne d'installation** qui paramètre une nouvelle boutique de bout en bout.

## 2. Stratégie d'isolation des bases (le choix structurant)

Trois options classiques, du plus simple au plus complexe :

| Option | Principe | Isolation | Effort | Reco |
|---|---|---|---|---|
| **A. Une base + un déploiement par boutique** | Chaque boutique = sa propre stack (DB + API + web), `DATABASE_URL` distinct. Le code reste mono-tenant. | Totale (physique) | **Faible** (déjà compatible) | ✅ **Recommandé pour démarrer** |
| B. Schéma par boutique | Un seul cluster PG, un schéma par boutique (`SET search_path`). | Forte | Moyen (Alembic multi-schéma, routing par hôte) | Plus tard si coût infra |
| C. Row-Level (`store_id` partout + RLS) | Une base partagée, `store_id` sur toutes les tables + policies PG. | Logique | **Élevé** (migration de 25 modèles, audit RLS, risque perf) | Déconseillé au départ |

**Recommandation : Option A.** Elle est **déjà réalisable** sans refactor du
domaine : l'app est mono-tenant, on déploie une instance par boutique (chacune
avec son `DATABASE_URL`, son `data/`, ses secrets). L'isolation RGPD/fiscale est
parfaite (les données d'une boutique ne peuvent physiquement pas fuir vers une
autre), les sauvegardes (cf. backup exhaustif) et le reset go-live restent
simples. Le coût est opérationnel (N stacks) — acceptable pour quelques
boutiques, et industrialisable via le `docker-compose.prod.yml` paramétré par
boutique + la GitHub Action de déploiement.

Le passage ultérieur à B/C est possible **sans rien jeter** : la phase de
paramétrage ci-dessous centralise déjà tout ce qui est « propre à la boutique »,
donc introduire un `store_id` reviendrait à déplacer ce contexte du fichier vers
une colonne — un travail mécanique, pas un redesign.

## 3. Phase de paramétrage (ce qui rend le comportement indépendant par boutique)

Tout ce qui suit est **déjà** ou **devient** piloté par la config de la
boutique, sans toucher au code métier :

| Domaine | Où c'est stocké | Statut |
|---|---|---|
| Identité (nom, tagline, logo) | `shop_info` | existant |
| Localisation (adresse, ville, pays) | `shop_info` | existant |
| Horaires d'ouverture | `shop_info.hours` | existant |
| Surface (m²) — KPI CA/m² | `shop_info.surface_m2` + `kpis-config` | existant |
| **Gestion TVA** (taux par défaut + taux réduits) | `shop_info.vat_rate_percent` + `Product.tva_rate` | existant (par produit) |
| Légal/bancaire (SIRET, RCS, IBAN…) | `shop_info` | existant |
| **Zonage / mapping** activable | `features.zoning_enabled` | ✅ livré |
| Encaissement (SumUp) | `sumup` | existant |
| Imprimantes (ticket MUNBYN, étiquette Zebra), tiroir, douchette, **format étiquette** | `hardware.json` | existant |
| Email/SMS (Brevo/SMTP/Twilio) | `email` / `sms` | existant |
| Caisse (fond, tolérance, sacs) | `cash_management` / `pos` | existant |
| **Droits utilisateurs** | table `users` (`role`) | existant (par déploiement) |
| **Statut d'installation** | `installation` | ✅ livré (phase 1) |

La nouveauté de cette phase 1 est la section **`installation`** d'`app_config`
et l'écran **`/setup`** qui orchestre ces réglages dans un ordre guidé, vérifie
ce qui est configuré, puis marque la boutique « installée ».

## 4. Chaîne d'installation livrée (phase 1)

API (`/api/admin/installation`, manager) :

- `GET /api/admin/installation` → `{installed, installed_at, completed_steps,
  checklist:[{key,label,done,hint}]}`. La checklist est **calculée** en
  inspectant la config réelle (identité renseignée, TVA, matériel, au moins un
  second utilisateur, choix zonage), donc elle reflète l'état réel, pas une
  case cochée à la main.
- `PUT /api/admin/installation` → marquer des étapes complétées / `installed`.

UI `/setup` : assistant en étapes qui réutilise les endpoints existants
(`shop-info`, `features`, `hardware`, `users`) :

1. **Identité & localisation** — nom, adresse, ville, horaires.
2. **Fiscalité** — taux de TVA par défaut.
3. **Organisation boutique** — activer/désactiver le **zonage**.
4. **Matériel** — lien vers `/settings > Matériel` (imprimantes, tiroir,
   douchette, **format d'étiquette**).
5. **Utilisateurs & droits** — lien vers `/admin/users`.
6. **Finalisation** — « Marquer la boutique comme installée ».

Un bandeau « installation à terminer » s'affiche tant que `installed = false`.

## 5. Reste à faire pour le vrai multi-boutique (phases suivantes)

1. **Industrialiser le déploiement Option A** : un template
   `docker-compose.<boutique>.yml` + variables (`DATABASE_URL`, domaine Caddy,
   secrets) générés depuis un manifeste boutique ; étendre la GitHub Action pour
   cibler la bonne stack.
2. **Provisioning d'une nouvelle boutique** : script `scripts/new_store.py`
   (créer DB, appliquer migrations, seed catégories/zones par défaut **ou non
   selon `zoning_enabled`**, créer le 1ᵉʳ manager, écrire `app_config.json`).
3. **Console multi-boutique (optionnel)** : si besoin d'une vue consolidée,
   préférer un **entrepôt analytique** alimenté par export (le requêteur
   sur-mesure existe déjà) plutôt que de casser l'isolation transactionnelle.
4. **TVA multi-pays** : `tva_service` supporte déjà 0/2.1/5.5/10/20 ; pour
   l'international, rendre la liste des taux configurable par boutique.

## 6. Pourquoi cette approche ne casse rien

- Aucune migration destructive : `installation` est additif (fichier de config),
  comme `features`.
- Le code métier ignore le multi-tenant : une instance = une boutique, exactement
  comme aujourd'hui. L'« exportabilité » est obtenue par **déploiement**, pas par
  réécriture.
- La phase de paramétrage centralise le « propre à la boutique » → le jour où un
  `store_id` devient nécessaire (Option B/C), le périmètre à migrer est déjà
  identifié et borné.
