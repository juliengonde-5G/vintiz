# Audit Vintiz 2026-05 — Boutique seconde main Vernon

> **Date** : 26 avril 2026
> **Branche** : `claude/structure-shop-app-3pbeo`
> **Auteur** : audit pilote (Claude Opus 4.7) + ground-truth code
> **Périmètre** : ERP + site vitrine + Personal Shopper + AI Booster
> **Public** : dirigeant, manager, équipe, sous-traitants techniques

---

## Sommaire

- [§1 — Synthèse exécutive](#1--synthèse-exécutive)
- [§2 — Audit fonctionnel par module](#2--audit-fonctionnel-par-module)
- [§3 — Audit complémentaire Personal Shopper IA](#3--audit-complémentaire-personal-shopper-ia)
- [§4 — Audit complémentaire AI Booster](#4--audit-complémentaire-ai-booster)
- [§5 — Personas terrain](#5--personas-terrain)
- [§6 — Comparaison marché](#6--comparaison-marché)
- [§7 — Plan d'évolution du scoring](#7--plan-dévolution-du-scoring)
- [§8 — Bibliothèque de prompts IA](#8--bibliothèque-de-prompts-ia)
- [§9 — Roadmap exécutable](#9--roadmap-exécutable)
- [§10 — Annexes](#10--annexes)

---

## §1 — Synthèse exécutive

Vintiz est un produit **plus mature que ne le laissait penser le brief initial**. Les 4 phases planifiées en avril 2026 sont effectivement livrées (NF525, RGPD, multi-photos, refund, PIN cashier, mode offline POS, embeddings pgvector, markdown engine, KPIs retail, RFM, wallet payload, réservations 48h, badges POS IA). Le code source vérifié au 26 avril 2026 confirme :

- **18 migrations Alembic** appliquées (de `0001_email_optin` à `0018_reservations`)
- **93 tests verts** (suite isolée backend)
- **Build green** sur les 3 apps (api FastAPI, web Next.js admin, site Next.js public)
- **5 services IA** opérationnels avec fallback déterministe (Vision Sonnet-4, Personal Shopper Haiku-4.5, Mapping Sonnet-4, Social Posts Haiku-4.5, Review Reply Haiku-4.5)

### 5 zones d'amélioration prioritaires post-audit

| # | Zone | Pourquoi maintenant | Livrable |
|---|---|---|---|
| 1 | **Mapping boutique trop schématique** | Aujourd'hui : rectangles colorés flottants sans cadre architectural ni mobilier. Bloque l'usage en réunion équipe. | L2.2 — refonte isométrique 2.5D + mobilier paramétrable |
| 2 | **Poids scoring hardcodés** | Camille (manager) ne peut pas ajuster sans déploiement. Pas de saisonnalité, pas de seuil de consignation. | L4 — UI sliders + table `app_settings` + 8 composantes v2 |
| 3 | **AI Booster orphelin de visuel** | La page `/ia` (1131 lignes) montre des scores nus. Aucune photo, aucun argument, aucune action 1-tap. | L2.5 — 4 onglets cartes visuelles + fashion-watch |
| 4 | **POS fidélité pauvre** | Le lookup client renvoie nom + points + tier. Sophie (cashier) n'a pas de contexte de vente additionnelle. | L2.3 — `LoyaltyCustomerCard` avec dernière visite, catégories, suggestions PS du jour |
| 5 | **Cahier du jour mono-temporel** | Aujourd'hui : page jour J unique. Pas de J-1 archivable, pas d'événements Vernon/Giverny, pas de vacances scolaires. | L2.4 — refonte 2 temps + moteur prédictif local |

### Différenciateurs marché

Vintiz se distingue clairement de Lightspeed POS / Shopify POS / Vinted Pro / Recommerce sur **3 axes** :

1. **Personal Shopper IA** avec embeddings pgvector + Claude Haiku narrative + fallback déterministe
2. **AI Booster** (scoring 6 composantes + markdown engine + window display + ai_mapping)
3. **Cycle de vie produit FSM 8 statuts** strictement aligné sur le métier seconde main (commande → carton → étiquetage → mise en rayon → retour tri → don)

Ces 3 axes méritent **un investissement renforcé** plutôt qu'une parité fonctionnelle avec les ERP retail neufs.

### Reportés / supprimés

- **Reporting ESS dédié** (P4-002) : page supprimée sur retour utilisateur, calcul backend conservé pour exports ad-hoc
- **Encoder embeddings CLIP/SigLIP** : remplacement du hashing trick SHA1 actuel reporté (effort > 1 semaine)
- **Wallet pass signing** : payload prêt, signature Apple Developer + Google Issuer à plugger côté ops

---

## §2 — Audit fonctionnel par module

> Méthode : pour chaque sous-module, 7 points : statut déploiement / pertinence / pratiques marché / gap / persona / recommandations / UX.

### §2.1.a — Encaissement (espèces + SumUp + code-barres)

**1. Statut déploiement** : ✅ complet
- POS interface tactile : `apps/web/src/app/pos/page.tsx` (1728 lignes)
- Espèces : numpad tactile, presets smartcash, rendu monnaie auto, ouverture tiroir RJ-12 sur impulsion ESC p m
- SumUp : 3 modes (production / sandbox / simulation), polling, push direct au TPE Solo si `SUMUP_READER_ID` configuré, fallback sandbox in-memory si pas de clé
- Code-barres : douchette Inateck USB HID, focus auto champ recherche, résolution exact match `barcode` + fallback recherche 1 résultat
- Mode offline : IndexedDB queue + idempotence `client_uuid` + auto-drain au reconnect
- PIN cashier 4 chiffres bcrypt, `cashier_id` traçable sur `Transaction` / `CashDrawer` / `ZReport`
- Refund cash/card/cheque/avoir avec ticket retour 80mm
- Split payment supporté côté modèle (Transaction.payments 1-N) et UI

**2. Pertinence** : très bonne. Le POS est **production-ready** pour Vernon avec tous les hardware certifiés (MUNBYN ESC/POS, SATO SBPL, SumUp Solo, Inateck, Safescan SD-4141).

**3. Pratiques marché**
- **Lightspeed Retail K** : POS web + iPad, hardware Star/Square certifié, pricing à partir de 79€/mois. Force : intégration comptable Sage. Gap Vintiz : pas d'export Sage natif.
- **Shopify POS** : POS Pro 89$/mois, hardware Stripe Reader/Star, marketplace apps. Force : marketplace UX/dev. Gap Vintiz : pas de marketplace publique d'extensions.
- **Square for Retail** : 60$/mois, US-centric. Force : analytics temps réel granulaires.
- **Sumup Solo + Sumup App** : starter pack pour TPE, écosystème simple. Vintiz utilise déjà SumUp Solo + va plus loin avec encaissement complet.

**4. Gap analysis**
- ❌ Pas d'export comptable Sage / Cegid / EBP
- ❌ Pas d'écran "ticket différé" (cas client revient avec article cassé sans ticket)
- ❌ Pas de gestion multi-devises (limité € — non bloquant pour Vernon)
- ⚠ Le timeout SumUp peut bloquer la cashier 3-9s sur polling (à mitiger avec timeout 45s côté UI)
- ⚠ Pas de double affichage écran client (vitrine TPE vs écran caisse)

**5. Persona** : **Sophie (cashier)** — voir §5

**6. Recommandations**
- **R1 (P0)** : modal SumUp avec timeout 45s + bouton "Continuer / Annuler" → évite blocage si TPE en panne (L2.3)
- **R2 (P1)** : enrichir `LoyaltyCustomerCard` au lookup client → vente additionnelle (L2.3)
- **R3 (P2)** : exporteur comptable Sage 50/100 (format ASCII PNM) — futur
- **R4 (P3)** : double affichage client via second écran iPad mini sur vitrine TPE — futur

**7. UX**
- Sidebar permanente sur md+ gaspille 64px sur iPad 1024×768 → collapsible (L2.1)
- Discount strip caché par défaut → auto-expand si déjà 1 remise au panier (heuristique d'usage)
- Toast feedback offline avec haptic feedback `navigator.vibrate` au drain réussi
- Modal post-vente avec réimpression ticket en 1 tap

**Action complémentaire (sur retour utilisateur)** : le script `scripts/test_pos_e2e.py` (L3.6) automatise un cycle complet de 10 étapes (login PIN → ouverture caisse → lookup → scan → remise → coupon → split payment → ticket → fermeture caisse → Z report) avec mode offline simulé au milieu. Permet une validation fonctionnelle reproductible avant chaque release.

---

### §2.1.b — Stock & inventaire (chaîne logistique en 5 étapes ordonnées)

> **L'ordre des actions est verrouillé sur retour utilisateur — non modifiable** :
> **1. Commande → 2. Carton → 3. Étiquetage → 4. Mise en rayon → 5. Retour tri**

#### Étape 1 — Commande (centre de tri Solidarité Textiles)

**Statut** : ⚠ partiel
- Modèle `Batch` existe (`apps/api/app/models/batch.py`) avec `date_reception`, `nb_articles`, `origine`, `opérateur`
- Endpoints `POST /api/inventory/batches` et `GET /api/inventory/batches/{id}` opérationnels
- ❌ Pas de pré-saisie d'arrivage prévu (commande passée AU centre de tri avant réception)
- ❌ Pas de bon de commande PDF imprimable

**Recommandation** : ajouter un statut `Batch.status = ordered | in_transit | received | sorted | tagged` (FSM) + endpoint `POST /api/inventory/batches/order` qui crée un batch en statut `ordered` avant l'arrivée physique.

#### Étape 2 — Carton (réception physique boutique)

**Statut** : ✅ complet
- `POST /api/inventory/batches/{id}/assign-product` rattache un produit fraîchement scanné au lot
- UI : `/inventory` permet création produit avec batch_id

**Persona** : **Léa (employée tri/étiquetage)**

**UX recommandée** : nouveau Kanban inventaire 5 colonnes alignées sur la FSM produit (`/admin/inventory/kanban`) — drag & drop entre colonnes pour validation rapide des transitions.

#### Étape 3 — Étiquetage (Vision IA + barcode + impression SATO)

**Statut** : 🟡 partiel
- ✅ Vision Sonnet-4 extrait 15 attributs (`services/ai_vision.py`)
- ✅ Barcode généré (préfixe `VTZ` + 6 chiffres)
- ✅ Driver SATO SBPL prêt (`services/sato_service.py`)
- ❌ **Bouton "Imprimer étiquette" non branché côté UI** sur fiche produit (P1-011 ouvert)
- ❌ Pas d'orchestration `from-photo` (créer produit depuis 1 photo + Vision auto-remplit les champs)

**Recommandation prioritaire** : `POST /api/inventory/products/from-photo` (L3.2) qui orchestre :
1. Vision analyse photo
2. Mapping `vision.type` → `category_id`
3. Lookup BrandTier pour résoudre la marque
4. Génération barcode
5. Création Product + Photo + scoring + suggestion zone
6. Réponse complète

#### Étape 4 — Mise en rayon (transition `TAGGED → DISPLAYED` + zone)

**Statut** : 🟡 partiel
- FSM produit fonctionnelle (`services/product_lifecycle.py`)
- `merchandising.suggest_zone()` existe
- ❌ La suggestion zone **n'est pas appelée automatiquement** à l'étiquetage (Léa doit le faire manuellement)
- ❌ Le filtre par tag de zone (`Homme / Femme / dernière démarque`) n'existe pas

**Recommandation** : enrichir `suggest_zone()` pour filtrer par `gender_hint` (extrait par Vision) + tags zone (L2.2). Brancher l'appel automatique à la transition TAGGED → DISPLAYED.

#### Étape 5 — Retour tri (cron auto au-delà de N jours)

**Statut** : ✅ existe via `services/return_to_sorting.py` + `services/markdown_engine.py`
- Cron quotidien évalue les produits en `DISPLAYED` avec score < seuil
- Action : transition `RETURNED_TO_SORTING` ou `DONATED`
- ❌ Pas de bon de retour PDF imprimable pour le centre de tri

**Recommandation** : générer un bon de retour PDF (export `apps/api/app/services/return_slip_pdf.py`) listant les articles à retourner avec barcode + photo miniature.

#### Pratiques marché

- **Brightpearl** (Sage) : ERP retail multi-canal, ordre logistique configurable, fort sur multi-warehouse. Gap : surdimensionné pour 1 boutique.
- **Cin7** : inventory + B2B + EDI. Force : connecteurs marketplaces. Gap : non adapté au retail seconde main.
- **Stock&Buy** : low cost, simple. Force : prix. Gap : pas d'IA, pas de FSM 5 étapes.
- **Stockflow** (français) : ERP simple FR. Force : support local. Gap : pas de POS intégré.

**Vintiz se positionne** : ERP **vertical seconde main** avec FSM 5 étapes verrouillée et IA intégrée — positionnement unique sur le marché français.

---

### §2.1.c — Reporting retail (sans ESS — supprimé sur retour utilisateur)

**Statut** : ✅ complet
- KPIs retail : sell-through, GMROI, AIT, CA/m²/mois (`services/retail_kpis.py`)
- Comparateurs S-1 / M-1 / A-1
- Heatmap horaire
- RFM segmentation (`services/rfm.py`, cron mensuel)
- Dashboard `/dashboard` avec KPIs jour, météo, transactions récentes

**Suppression demandée** : la page reporting ESS dédiée est jugée **non pertinente**. Le calcul backend (kg revalorisés, CA reversé) est conservé pour exports ad-hoc à destination de Solidarité Textiles.

**Pratiques marché**
- **RetailNext** : analytics pro avec capteurs IoT (compteurs entrée). Gap Vintiz : pas de capteur IoT (à étudier en Phase 6).
- **Lightspeed Analytics** : intégré au POS Lightspeed, dashboards riches. Gap Vintiz : pas d'export Looker/Metabase.
- **Square Dashboard** : temps réel granulaire. Vintiz à parité.

**Recommandation** : intégration Metabase ou Apache Superset en lecture seule sur la base PostgreSQL (lecture-seule via vues matérialisées) — futur Phase 5.

---

### §2.1.d — SEO + monitoring réseaux sociaux

**Statut** : ✅ complet
- `services/visibility.py` + `services/seo_smoke_test` couvrent sitemap, robots, metas, OG, JSON-LD
- Snapshots SEO persistés (`SEOSnapshot` + cron quotidien)
- 4 posts RS / semaine via Claude Haiku (`prompts/v1/social_posts.md`)
- Mentions Insta/TikTok saisissables en backoffice (manuel + scraper si Graph API)
- Avis Google : saisie manuelle + brouillon de réponse Claude

**Pratiques marché**
- **Brand24** / **Mention** : monitoring multi-réseaux pro (~99-149$/mois). Gap Vintiz : pas d'écoute auto multi-canal.
- **SEMrush** / **Ahrefs** : SEO tracking position keywords, backlinks. Gap : pas de tracking position SERP automatisé.
- **Yext** : Local SEO + GBP centralisé. Gap : pas de GBP automation.

**Recommandation**
- **R1** : intégrer suivi position SERP via API DataForSEO ou Serpstack pour keywords ciblés Vernon (10-20 mots-clés)
- **R2** : OAuth Search Console pour tirer impressions/clics quotidiens
- **R3** : intégrer Brand24-like via webhook (post manuel acceptable v1)

---

### §2.1.e — CRM clients + carte fidélité

**Statut** : ✅ très complet
- Lookup public, personal shopper v1 (legacy) + v2 (embeddings)
- Onboarding cold-start (6 styles + 5 occasions + 6 budgets + catégories)
- Avoir / store credit avec ledger
- Consentements RGPD versionnés
- Export JSON portable (Article 20)
- Soft delete + purge cron 30j
- Wallet pass payload Apple + Google
- Anniversaire automatique
- Réservations 48h
- Coupons

**Faiblesse identifiée (sur retour utilisateur)** : le lookup client au POS ne donne pas assez de contexte vente additionnelle à Sophie. Il faut afficher : nom complet, dernière visite, catégories favorites, marques favorites, taille, **suggestions PS du jour** cliquables → ajout direct au panier.

→ Voir L2.3 pour le composant `LoyaltyCustomerCard`.

**Pratiques marché**
- **LoyaltyLion** : Shopify-only, gamification, tiers. Force : levée de panier moyen +12% prouvée. Gap Vintiz : pas de gamification (badges, jeux).
- **Smile.io** : multi-plateforme, simple. Gap : pas d'IA.
- **Yotpo Loyalty** : enterprise, intégration UGC. Gap : Vintiz a déjà l'IA, pas l'UGC.

**Recommandation**
- **R1** : enrichir lookup POS (L2.3) — priorité immédiate
- **R2** : Wallet pass signing (clés Apple Developer + Google Issuer) — sortir du payload "preview"
- **R3** : badges gamification (1ère visite / 5e visite / parrainage) — futur

---

### §2.2.a — Site vitrine public

**Statut** : ✅ complet
- Landing optimisée Vernon
- Sitemap + robots dynamiques
- JSON-LD `Store`, OG, Twitter
- GA4 + Search Console verification
- Pages CGV, mentions légales, confidentialité (réécrites Phase 1)
- Espace client `/account` : login email, carte fidélité, historique, personal shopper, export RGPD

**Pratiques marché** : standards Local SEO + Google Business Profile.

**Recommandation**
- **R1** : Lighthouse 90+ sur les 4 pages clés (mesurer + optimiser images / fonts)
- **R2** : Schema.org `LocalBusiness` enrichi avec horaires + zones desservies + paiements acceptés
- **R3** : intégration GBP Posts API pour relayer les 4 posts Claude social_posts (futur)

---

### §2.2.b — Démonstration sélection produit (site vitrine)

**Statut** : 🟡 partiel
- Site `/site` permet réservation 48h via produit (P4-005)
- ❌ Pas de catalogue public navigable (le site reste "vitrine" sans liste produits)

**Pratiques marché**
- **Vinted** / **Vestiaire Collective** : catalogue marketplace public. Gap : Vintiz n'est PAS une marketplace (vente boutique).
- **Once Again** (FR) : site vitrine + click & collect. Référence pertinente.

**Recommandation**
- **R1** : page `/boutique` listant les 50 produits "vedettes" (top score) avec photos + prix + bouton "Réserver"
- **R2** : pas de paiement en ligne (vente reste en boutique) mais réservation 48h en cohérence avec l'existant
- **R3** : SEO produit individuel `(/produit/{slug})` pour capter les recherches longue traîne

---

## §3 — Audit complémentaire Personal Shopper IA

> **Pourquoi cet audit** (sur retour utilisateur) : Personal Shopper et AI Booster sont les deux marqueurs de différenciation. L'audit doit couvrir : prise de vue, détection produit, scoring, mapping, sélection personnalisée, ingénierie data/scoring, analyse historique ventes.

### §3.1 — Pipeline data complet

```
[Inateck scanner barcode]
        +
[Photo manuelle iPad ou upload]
        ↓
[POST /api/inventory/products/{id}/photos/upload]   (5 MB max, jpg/png/webp)
        ↓
[apps/api/uploads/products/{product_id}/{uuid}.{ext}]
        ↓
[ai_vision.analyze_photo_from_url(photo_url)]        (Claude Sonnet-4)
        ↓
[15 attributs normalisés JSON]                       (type, couleur, marque, taille, état,
                                                      saison, style, occasion, motif, coupe,
                                                      defauts, description, gamme, confiance)
        ↓
[EmbeddingService.upsert_product_embedding]
   ↓ visual_features (category_id, brand, color, size, condition, price_bucket)
   ↓ text_features (brand + name/description tokens)
   ↓ Hashing trick SHA1 → 256 dim
   ↓ INSERT product_embeddings (HNSW pgvector index)
        ↓
[scoring_service.compute_score]                      (6 composantes [0,20] × poids)
        ↓
[merchandising.suggest_zone]                         (gender_hint + tags zone)
        ↓
[Product final en DB avec score + zone suggérée]
```

**Migration** : `0008_add_embeddings.py` crée :
- `CREATE EXTENSION IF NOT EXISTS vector;`
- Tables `product_embeddings` (visual_vec, text_vec) et `customer_taste_profiles` (visual_centroid, text_centroid)
- Index HNSW cosine `ix_product_visual_hnsw` et `ix_product_text_hnsw`

### §3.2 — Calcul du taste profile cliente

**Service** : `EmbeddingService.recompute_taste_profile()` (`embeddings.py:226-319`)

**Formule** :
```
TASTE_HALF_LIFE_DAYS = 180

Pour chaque transaction des 50 derniers achats :
   age_days = (now - transaction.date).days
   weight = 0.5 ^ (age_days / 180)
   visual_sum += product_embedding.visual * weight
   text_sum += product_embedding.text * weight

visual_centroid = normalize_L2(visual_sum)
text_centroid = normalize_L2(text_sum)
```

**Effet** :
- Achat d'aujourd'hui : poids 1.0
- Achat il y a 180 jours : poids 0.5
- Achat il y a 360 jours : poids 0.25
- Achat il y a 720 jours : poids 0.06

### §3.3 — Cold-start onboarding

**Service** : `services/onboarding.py`

**Inputs** (formulaire 6 questions, < 2 min) :
- 1 à 3 styles parmi : minimaliste / vintage / bohème / chic / sport / rock
- 1 à 3 occasions : quotidien / bureau / soirée / weekend / cérémonie / été / festival
- Budget : 1 tranche parmi 6 (< 20€ / 20-40€ / 40-60€ / 60-100€ / 100-150€ / 150€+)
- Catégories préférées (libre)

**Calcul du centroïde initial** :
- `visual_centroid` synthétisé depuis l'union des features des 6 styles sélectionnés
- `n_purchases_analyzed = 0` pour marquer cold-start
- `algo_version = "cold-start-v1-2026-04"`
- Remplacé par scoring réel après 1ère transaction

### §3.4 — Recommandation à la cliente

**Service** : `PersonalShopperService.recommend()`

**Étapes** :
1. **Filtre catalogue** : produits en `DISPLAYED`, en stock, dans budget cliente
2. **Similarité cosinus** : top 20 candidats par `visual_centroid <-> product.visual_vec`
3. **Diversification** : MMR (Maximal Marginal Relevance) — pénalité similarité intra-set, garantit que les 5 recos finales ne sont pas toutes la même robe noire
4. **Narrative Claude** : prompt `prompts/v1/personal_shopper.md` (Haiku 4.5, 512 tokens max) avec inputs :
   - Cliente info (prénom, tier, dernière visite)
   - 3 derniers achats
   - Tailles + couleurs préférées
   - 5 candidats finalistes (résumés)
   - Météo Vernon
5. **Logging** :
   - `recommendation_set_id` UUID
   - 1 event `customer_recommendation_shown` par produit (avec score, position, fallback_used)
6. **Fallback déterministe** : si Claude indispo, template texte mentionnant les achats passés + liste des 5 candidats

### §3.5 — Click tracking + feedback loop

**Endpoint** : `POST /api/crm/personal-shopper-v2/click`
- Logge event `customer_recommendation_clicked` avec `recommendation_set_id` + `product_id` + `position`

**Faiblesse identifiée** : le click N'EST PAS RÉINJECTÉ dans le `taste_profile`. C'est un signal important perdu.

**Recommandation v2** : créer un job nightly qui pondère le `visual_centroid` avec les products cliqués (poids = 0.3) en plus des achetés (poids = 1.0).

### §3.6 — Faiblesses identifiées

1. ⚠ **Encoder hashing trick SHA1** : le 256-dim embedding est un placeholder, pas un signal visuel réel. Conséquence : la similarité cosinus rapproche des produits avec mêmes features structurées (catégorie + marque + couleur + taille + condition + price_bucket) mais ignore l'**aspect visuel** (motif, coupe, finitions). À remplacer par CLIP ou SigLIP.

2. ⚠ **Pas de feedback loop click → taste_profile** : on perd un signal d'engagement.

3. ⚠ **Pas d'A/B testing** : impossible de comparer 2 versions de prompt en parallèle.

4. ⚠ **Pas de cold-start visuel** : aujourd'hui questionnaire texte uniquement. L'idéal serait 5 photos style "j'aime / j'aime pas" pour calibrer le `visual_centroid` initial avec un signal réel.

5. ⚠ **Pas de plafond de fréquence** : une cliente Gold qui revient 3x/jour reçoit la même reco 3x. Il faut filtrer les produits déjà vus < 24h.

### §3.7 — Recommandations Phase 5

| # | Reco | Effort | Impact |
|---|---|---|---|
| PS-R1 | Remplacer encoder SHA1 par CLIP via Replicate / HuggingFace Inference API (ou OpenAI text-embedding-3-large pour le texte) | 1-2 sem | Qualité reco +30 à +50% |
| PS-R2 | Feedback loop click → taste_profile (job nightly) | 3j | Personnalisation +15% |
| PS-R3 | A/B testing prompts (algo_version multi) + métrique conversion | 5j | Optimisation continue |
| PS-R4 | Cold-start visuel (5 photos j'aime / j'aime pas) | 5j | Cold-start qualité +25% |
| PS-R5 | Filtre "déjà vu < 24h" avant rendering | 1j | Anti-répétition |
| PS-R6 | Multi-langue prompt (anglais pour clientes touristes Giverny) | 2j | International |

---

## §4 — Audit complémentaire AI Booster

### §4.1 — Scope du module

L'AI Booster regroupe 4 sous-services :

1. **Mapping boutique** (`services/ai_mapping.py`) — placement zones, recommandations agencement
2. **Scoring produit** (`services/scoring_service.py`) — note 0-100 avec 6 composantes
3. **Markdown engine** (`services/markdown_engine.py`) — règles déclaratives JSON, cron nightly
4. **Window display** (`services/merchandising.py`) — proposition vitrine hebdomadaire

### §4.2 — Détail formule scoring

```python
# Source : apps/api/app/services/scoring_service.py:62-177

def compute_score(...) -> dict:
    # 6 sub-scores [0, 20]
    score_age = max(0, 20 - days_on_shelf // 3)        # 0 si > 60j
    score_prix = ...                                     # 20 si <= 50% catégorie avg
    score_condition = condition_map[condition]           # 5 à 20 selon état
    score_brand = brand_score or _legacy_brand_score()   # luxury 20, premium 15, mid 10, autre 8
    score_category = category_trend / 5                  # category_trend [0,100] → [0,20]
    score_photos = _photo_subscore(...)                  # count + Vision confidence

    # Total pondéré × 5 → [0, 100]
    total = (score_age * 0.30
           + score_prix * 0.20
           + score_condition * 0.20
           + score_brand * 0.15
           + score_category * 0.10
           + score_photos * 0.05) * 5
```

**Action recommandée selon score** :
- `< 30` : RETIRER (rouge)
- `30-50` : RÉDUIRE PRIX -15% (orange)
- `50-70` : METTRE EN AVANT (jaune)
- `70+` : MAINTENIR (vert)

### §4.3 — Faiblesses identifiées (enrichies sur retour utilisateur)

| # | Faiblesse | Conséquence | Solution |
|---|---|---|---|
| AB-W1 | Poids hardcodés (0.30/0.20/0.20/0.15/0.10/0.05) | Camille ne peut pas ajuster sans déploiement | L4 — UI sliders + table `app_settings.scoring_config_v1` |
| AB-W2 | Pas de saisonnalité catégorie | Manteau noté pareil en juin et en novembre | L4 — `season_boost.category_calendar` |
| AB-W3 | Pas de seuil "consignation longue" | Produit oublié garde un score > 0 indéfiniment | L4 — `consignment_threshold` + cron |
| AB-W4 | **Pas de signal "transition de saison"** | Score chute brutalement quand un manteau passe en avril | **Composante 7 v2 : rampe de décroissance progressive sur 3-6 semaines** |
| AB-W5 | **Pas de capteur "tendance fashion"** | Aucun signal externe (Vinted, Vogue, Instagram, Trendalytics) | **Composante 8 v2 : signal fashion-watch via cron quotidien** |
| AB-W6 | Window display orphelin de UI | La reco hebdo existe mais personne ne la voit | L2.5 onglet "Vitrine de la semaine" |
| AB-W7 | Reco placement non branchée à l'étiquetage | Léa doit appeler `suggest_zone()` manuellement | L2.2 + intégration FSM `TAGGED → DISPLAYED` |
| AB-W8 | Présentation des recos en table de scores nus | Pas de photo, pas d'argument, pas d'action 1-tap | L2.5 — refonte cartes visuelles |

### §4.4 — Présentation visuelle attendue (refonte UI `/ia`)

Aujourd'hui, la page `/ia` (1131 lignes) liste les produits en table avec score numérique. À reconstruire en **carrousel de cartes recommandation visuelles** :

```
┌───────────────────────────────────────────────────────────────┐
│  📷 [photo produit]    Robe Sandro fluide bordeaux T36         │
│                       Score 78  •  En rayon depuis 14j         │
│                                                                │
│  💡 Action recommandée :  METTRE EN AVANT VITRINE              │
│                                                                │
│  Pourquoi ?                                                    │
│  • Couleur tendance bordeaux (+12% recherches Vinted ce mois)  │
│  • Cliente Clara (Gold) a acheté 2 robes Sandro en 2025        │
│  • Stock zone "Robes" à 60% — bon créneau visibilité           │
│                                                                │
│  Pièces similaires en boutique :                               │
│  [thumb] [thumb] [thumb]  (cliquables)                         │
│                                                                │
│  [Accepter] [Reporter] [Pourquoi pas ?]                        │
└───────────────────────────────────────────────────────────────┘
```

**4 onglets** dans la nouvelle UI :
1. **Recommandations du jour** — carrousel cartes (par urgence décroissante)
2. **Vue saisons** — calendrier 12 mois × catégories avec rampes
3. **Influence fashion** — couleurs / coupes / marques en hausse (signal externe)
4. **Vitrine de la semaine** — proposition window display visualisée en isométrique

### §4.5 — Audit du mapping boutique (refonte demandée)

**État actuel** : `apps/web/src/app/zones/page.tsx` (458 lignes)
- Canvas 16:10 avec rectangles drag/resize en coordonnées % (0-100)
- Zones colorées en `linear-gradient` selon `color_code`
- Heatmap occupation : couleur change selon `count / capacity` (yellow 40%, teal 70%, pink 95%+)
- Shapes : rect / rounded / circle
- Champ `Store.photo_url` existe mais inutilisé en render

**Diagnostic** : rendu **purement schématique**, sans cadre architectural ni mobilier. Bloque l'usage en réunion équipe (Sophie / Léa / Camille ne se "projettent" pas dans le plan).

**Refonte demandée** (sur retour utilisateur) :
- **Représentation isométrique 2.5D** (vue cavalière 30°) avec sol carrelé subtil
- **Bibliothèque mobilier paramétrable** : portants (3 tailles), mannequins (homme/femme/enfant), étagères (4n/5n), tables présentation, comptoir caisse, cabines essayage, vitrine, mur, porte, tête de gondole — 10 assets SVG isométriques
- **Affectation zones par tag** : multi-select parmi `homme | femme | enfant | accessoire | derniere_demarque | nouveaute | premium | saisonnier | vitrine | tete_gondole`
- **Filtres** au-dessus du canvas : "Voir uniquement zones FEMME" / "DERNIÈRE DÉMARQUE" → grise les autres
- **Mapping IA filtre par tag** : `merchandising.suggest_zone()` prend un `gender_hint` extrait de Vision et un set de tags pour filtrer les zones candidates
- **Export PNG / PDF A3** pour impression réunion équipe

Voir L2.2 pour le détail technique.

### §4.6 — Recommandations Phase 5+

| # | Reco | Effort | Impact |
|---|---|---|---|
| AB-R1 | UI sliders pondération scoring (8 composantes v2) | 2j | Camille autonome |
| AB-R2 | Composante 7 — rampe transition saison | 3j | Évite chutes brutales |
| AB-R3 | Composante 8 — fashion-watch (Google Trends + Vinted public) | 5j | Signal externe |
| AB-R4 | Refonte UI `/ia` — 4 onglets cartes visuelles | 3-4j | Adoption +50% |
| AB-R5 | Mapping isométrique 2.5D + mobilier + tags zones | 3-4j | Plan réunion utilisable |
| AB-R6 | Brancher `suggest_zone()` à l'étiquetage auto | 1j | Léa gain temps |
| AB-R7 | Bouton "Imprimer étiquette" sur fiche produit | 1j | Boucle Vision → étiquette |
| AB-R8 | Window display dans UI `/ia` onglet 4 | 2j | Reco hebdo enfin visible |

---

## §5 — Personas terrain

### Sophie — Cashier (employée, 28 ans, 6h/jour iPad caisse)

**Profil** : embauchée en mars 2026, 2 ans d'expérience retail (Pimkie). Connaît bien l'iPad mais pas les ERP retail.

**Journée type** :
- 9h45 : prise de poste, login PIN, ouverture caisse avec fond 100€
- 10h-12h30 : encaissement matinée, lookup clientes, suggestions vente additionnelle
- 12h30-14h : pause
- 14h-19h : encaissement après-midi, gestion retours, conseil clientes
- 19h-19h30 : clôture caisse, Z report, comptage espèces

**Pain points actuels** :
- Sidebar prend 64px sur l'iPad → panier serré
- Modal CB SumUp peut bloquer 9s en polling sans bouton "annuler"
- Lookup client : peu d'info, doit demander manuellement les goûts → conversation difficile
- Pas de notification au manager si écart de caisse ou anomalie

**Attentes** :
- Plus d'espace utile sur l'écran caisse
- "Brief vente additionnelle" instantané au lookup client
- Modal CB avec timeout cleanable
- Toast feedback positif au drain offline réussi

### Camille — Manager boutique (38 ans, 2h/jour iPhone + desktop)

**Profil** : manager Vintiz Vernon depuis l'ouverture. Background : 12 ans en boutique mode (Sandro/Maje). Utilise principalement son iPhone le matin pour le cahier du jour, et desktop le soir pour le reporting + ajustements.

**Journée type** :
- 8h30 : café + cahier du jour J sur iPhone (validation prévisionnel, mot à l'équipe)
- 9h-9h45 : briefing équipe, signature cahier
- En journée : SAV ponctuels, validations achats, gestion équipe
- 19h30 : sur desktop, revue Z report, validation vitrine semaine, ajustements scoring si besoin
- 21h : commentaire performance J-1 dans cahier archivé

**Pain points actuels** :
- Cahier du jour mono-temporel : pas de vue J-1 archivée commentable
- Pas de calendrier événements Vernon/Giverny → planifie à l'aveugle
- Scoring poids non ajustables : doit demander à Julien (dirigeant) un déploiement
- Pas de push notif stratégiques (objectif jour atteint, écart Z report > 50€)

**Attentes** :
- Cahier 2 temps + événements + opérations commerciales paramétrables
- UI sliders scoring autonome
- Push notifs sur indicateurs critiques

### Léa — Employée tri/étiquetage (24 ans, 4h/jour iPad backstage)

**Profil** : étudiante en alternance école de mode. Connaît bien la photo et la mode, peu les outils ERP.

**Journée type** :
- 14h-15h30 : réception batches + tri visuel + photos
- 15h30-17h : étiquetage (Vision + barcode + impression SATO) + mise en rayon
- 17h-18h : préparation vitrine selon recommandation IA hebdo

**Pain points actuels** :
- Bouton "Imprimer étiquette" non branché → doit passer par scripts SSH
- Pas d'orchestration "from-photo" → doit créer produit vide puis remplir manuellement
- Pas de Kanban inventaire 5 colonnes → vue éparpillée
- Window display recommendation orpheline → exécute sa propre intuition

**Attentes** :
- Endpoint `/products/from-photo` qui crée la fiche en 1 clic
- Bouton "Imprimer étiquette" branché à `sato_service`
- Kanban inventaire visualisable
- UI vitrine avec mannequins habillés des produits proposés

### Clara — Cliente Gold récurrente (45 ans, 2x/mois iPhone)

**Profil** : cliente fidèle depuis l'ouverture. Aime Sandro et Maje. Tier Gold (245 points). Avoir 12,50€. Achète robes principalement.

**Parcours type** :
- Reçoit notif anniversaire / nouvelles arrivées hebdo (P4-008/P4-009)
- Visite app Vintiz le samedi matin
- Consulte Personal Shopper → 5 recos
- Réserve 1-2 articles (P4-005)
- Vient en boutique récupérer

**Pain points actuels** :
- Personal shopper visible mais sans feedback boucle (clics non ré-injectés)
- Wallet pass payload pas signé (pas activable sur iPhone)
- Pas de cold-start visuel (formulaire texte uniquement)

**Attentes** :
- Recos qui s'améliorent quand elle clique
- Wallet pass actif dans Apple Wallet
- Onboarding visuel ludique

### Julien — Dirigeant ESS / lien Solidarité Textiles (52 ans, 1x/sem desktop)

**Profil** : créateur Vintiz, lien associatif avec Solidarité Textiles (centre de tri Vernon). Vision business + impact ESS.

**Pain points actuels** :
- Pas de tableau de bord impact (kg revalorisés, % flux centre de tri vendu, CA reversé)
- Pas d'export comptable Sage
- Pas de KPIs longitudinaux (12 mois glissants)

**Attentes** :
- Calcul kg/€-reversé conservé en backend (export ad-hoc) — page dédiée jugée non pertinente
- Export comptable Sage (futur Phase 5)
- Vue 12 mois avec saisonnalité

---

## §6 — Comparaison marché

### Tableau récapitulatif

| Fonction | Vintiz | Lightspeed Retail | Shopify POS | Vinted Pro | Recommerce | Verdict |
|---|---|---|---|---|---|---|
| POS hardware certifié | ✅ MUNBYN+SATO+SumUp | ✅ Star+Square | ✅ Star+Stripe | ❌ marketplace | ❌ | À parité |
| NF525 | ✅ chaînage SHA-256 + export DGFiP | ✅ | ✅ | n/a | ✅ | À parité |
| Mode offline POS | ✅ IndexedDB + idempotence | ✅ | ✅ | n/a | ⚠ | À parité |
| Multi-utilisateur PIN | ✅ bcrypt 4 chiffres | ✅ | ✅ | n/a | ✅ | À parité |
| Cycle de vie produit FSM 8 statuts | ✅ aligné seconde main | ⚠ in/out | ⚠ in/out | n/a | ✅ | **Vintiz devant** |
| **IA pricing/markdown** | ✅ moteur déclaratif Sonnet | ⚠ règles statiques | ⚠ règles statiques | ❌ | ⚠ scoring interne | **Vintiz devant** |
| **Personal shopper IA** | ✅ Haiku + pgvector + cold-start | ❌ | ⚠ apps tierces | ⚠ algo plateforme | ❌ | **Vintiz devant** |
| **Mapping boutique IA** | ⚠ schématique (en cours refonte iso 2.5D) | ❌ | ❌ | ❌ | ❌ | **Vintiz unique** |
| Réservation 48h | ✅ | ⚠ via apps | ⚠ via apps | n/a | ❌ | À parité |
| Wallet pass mobile | ⚠ payload prêt non signé | ✅ | ✅ | ❌ | ⚠ | À finaliser |
| Email automation | ✅ Brevo > SMTP | ✅ Mailchimp | ✅ Klaviyo | ✅ | ✅ | À parité |
| Multi-boutique | ❌ mono-store | ✅ | ✅ | n/a | ✅ | Limitation Vintiz |
| Marketplace public | ❌ vitrine seule | ✅ multi-canal | ✅ multi-canal | ✅ marketplace | ✅ | Choix Vintiz (pas marketplace) |
| Tarif | ~ self-hosted Scaleway | 79€/mois | 89$/mois POS Pro | commission % | abo + commission | Vintiz coût infra ~ 50€/mois |

### Synthèse positionnement

Vintiz n'essaie pas de concurrencer Lightspeed/Shopify sur la largeur fonctionnelle. **Il se positionne comme un ERP vertical seconde main** avec 3 différenciateurs forts :
1. **Personal Shopper IA** (pgvector + Claude Haiku) — aucune solution off-the-shelf à ce niveau
2. **AI Booster** (scoring 6→8 composantes + markdown engine + window display + ai_mapping)
3. **Cycle de vie 8 statuts** strictement aligné métier seconde main (commande → carton → étiquetage → mise en rayon → retour tri → don)

**Recommandation stratégique** : ne pas chercher à rattraper Lightspeed sur la comptabilité ou le multi-boutique avant que les 3 différenciateurs soient solides à 100% (refonte UI `/ia`, scoring v2, mapping iso 2.5D, encoder CLIP/SigLIP).

---

## §7 — Plan d'évolution du scoring

### §7.1 — État v1 (existant)

6 composantes pondérées :

| # | Composante | Poids | Borne sub-score | Logique |
|---|---|---|---|---|
| 1 | Age | 30% | [0, 20] | `20 - days_on_shelf // 3` |
| 2 | Prix | 20% | [0, 20] | Ratio sale_price / category_avg |
| 3 | Condition | 20% | [5, 20] | Map enum (excellent → correct) |
| 4 | Marque | 15% | [5, 20] | BrandTier DB ou fallback hardcodé |
| 5 | Catégorie trend | 10% | [0, 20] | category_trend / 5 |
| 6 | Photos | 5% | [0, 20] | count + Vision confidence |

Formule : `total = Σ(sub_score × poids) × 5` → [0, 100]

### §7.2 — v2 (à livrer en L4)

**8 composantes**, 2 nouvelles + 6 ajustées :

| # | Composante | Poids v1 | Poids v2 | Détail v2 |
|---|---|---|---|---|
| 1 | Age | 30% | **27%** | + courbe configurable (linear/exp/step) |
| 2 | Prix | 20% | **18%** | inchangé |
| 3 | Condition | 20% | **18%** | inchangé |
| 4 | Marque | 15% | **13%** | inchangé |
| 5 | Catégorie trend | 10% | **9%** | inchangé |
| 6 | Photos | 5% | **5%** | inchangé |
| 7 | **Transition saison** | — | **5%** | rampe 4 sem avant `season_start` (0→20) + plein cœur (20) + rampe 4 sem avant `season_end` (20→5) |
| 8 | **Fashion-watch** | — | **5%** | signal externe Google Trends + Vinted public + hashtags Insta |

Total = 100%.

### §7.3 — Configuration paramétrable (table `app_settings.scoring_config_v1`)

```json
{
  "version": 2,
  "weights": {
    "age": 0.27, "price": 0.18, "condition": 0.18,
    "brand": 0.13, "category": 0.09, "photos": 0.05,
    "season_transition": 0.05, "fashion_watch": 0.05
  },
  "age_decay": {
    "curve": "linear",            // linear | exponential | step
    "max_score_days": 0,
    "min_score_days": 60,
    "saturation_days": 90
  },
  "season_boost": {
    "enabled": true,
    "boost_pct": 0.15,
    "category_calendar": {
      "Manteau": [10, 11, 12, 1, 2],
      "Robe": [4, 5, 6, 7, 8],
      "Maillot": [5, 6, 7]
    }
  },
  "consignment_threshold": {
    "enabled": true,
    "max_days": 120,
    "action_after": "RETURNED_TO_SORTING"
  },
  "updated_by": "camille@vintiz.fr",
  "updated_at": "2026-05-..."
}
```

### §7.4 — UI sliders (admin)

Onglet `Scoring IA` dans `/settings` avec 6 sections :
1. Pondération (8 sliders, validation somme = 100%)
2. Décroissance temporelle (radio courbe + 3 sliders + graphique)
3. Boost saisonnier (toggle + tableau catégories × mois)
4. Seuil de consignation (toggle + slider + dropdown action)
5. Aperçu impact (bouton "Simuler" → 10 produits avec score avant/après)
6. Sauvegarde

### §7.5 — v2.5 / v3 (futur)

**v2.5** (Phase 6, ~1 mois) :
- **Sell-through rate** par catégorie : si tourne vite (ratio ventes / stock > 0.5), boost `category_trend`
- **Momentum produit** : nb de "vues fiche client" sur 7j (event log) → bonus de score
- **Couleur saisonnière** : pondération couleur × météo Vernon
- **Click-through Personal Shopper** : produits cliqués gagnent +10% score

**v3** (Phase 7, ~2 mois) :
- Régression logistique entraînée chaque semaine sur (features produit) → (vendu en ≤ 14j ?)
- Le modèle remplace les poids manuels par des poids appris
- Conservation du fallback hardcodé si entraînement échoue
- A/B testing : 50% catalogue scoring v2, 50% scoring v3

### §7.6 — Pratiques retail seconde main (références)

| Acteur | Logique scoring | Apprentissage Vintiz |
|---|---|---|
| **Vinted Pro** | Boost basé sur engagement (likes, partages, vues) | Composante "Momentum produit" (v2.5) |
| **Vestiaire Collective** | Decay 30% à J+30, 50% à J+60, retrait à J+90 | Seuil consignation paramétrable (v2) |
| **Recommerce / Back Market** | Ratio prix / état (refurbished grade A/B/C) | Composante prix × condition (déjà faite) |
| **Once Again** (FR) | Scoring manuel + cycle de remise auto | Markdown engine déjà déclaratif |
| **Imparfaite** | Pas d'IA scoring, démarque manuelle | Vintiz devant |

---

## §8 — Bibliothèque de prompts IA

### §8.1 — Inventaire

| Prompt | Fichier | Modèle | Usage | Fallback |
|---|---|---|---|---|
| `vision_intake.md` | à créer | claude-sonnet-4-20250514 | Extraction 15 attributs depuis photo | `{"error": ...}` |
| `personal_shopper.md` | ✅ existe | claude-haiku-4-5 | Reco narrative cliente | Template texte déterministe |
| `store_mapping.md` | à créer | claude-sonnet-4-20250514 | Reco placement zone + démarque | Heuristique zone_matches_category |
| `window_display.md` | à créer | claude-haiku-4-5 | Sélection vitrine semaine | Top 6 par score brut |
| `pricing_decision.md` | à créer | claude-haiku-4-5 | Décision démarque pièce limite | Règle markdown engine |
| `social_posts.md` | ✅ existe | claude-haiku-4-5 | 4 posts RS / semaine | Template variables |
| `review_reply.md` | à créer | claude-haiku-4-5 | Réponse avis Google | Template selon note |

### §8.2 — Règles communes (à respecter)

1. **System prompt court** (max 200 tokens) : rôle, ton, contraintes de format
2. **Few-shot examples** dans user message pour les sorties JSON complexes
3. **Bornage explicite** des valeurs (enum dans description)
4. **Penalty explicite** sur l'hallucination ("Si tu ne sais pas, retourne null pour ce champ")
5. **Structure de sortie** annoncée en début de user message
6. **Logging** : chaque appel doit logger `algo_version`, `latency_ms`, `tokens_in`, `tokens_out`, `cost_eur`, `provider` dans `events.event_log`
7. **Versioning** : entête `<!-- v1.0-2026-05 -->` dans chaque fichier
8. **Variables** : encadrées `{{variable}}` (Jinja-like) interpolées par `prompt_loader.render()`

### §8.3 — Modèles de prompts (extraits clés)

#### `personal_shopper.md` (existant — référence)

```markdown
<!-- v1.0-2026-04 -->
Tu es Personal Shopper Vintiz, boutique seconde main premium à Vernon.

Règle d'or : tu ne recommandes QUE les pièces présentes dans le contexte
ci-dessous. Tu ne JAMAIS invente une pièce.

Ton : chaleureux, professionnel, jamais commercial agressif. 4-6 phrases max.
Tu mentionnes le prénom de la cliente. Tu fais lien avec ses derniers achats si pertinent.

# Contexte cliente
{{cliente_info}}

# Derniers achats
{{derniers_achats}}

# Tailles & couleurs
{{tailles}} / {{couleurs}}

# Pièces candidates en boutique aujourd'hui
{{candidats}}

# Météo Vernon
{{meteo}}

Réponds en français, 4-6 phrases, sans liste à puces.
```

#### `vision_intake.md` (à créer)

```markdown
<!-- v1.0-2026-05 -->
Tu es expert en analyse de vêtements seconde main. À partir d'une photo,
tu extrais 15 attributs en JSON strict (pas de markdown).

Règle absolue : si tu ne sais pas, retourne `null` pour ce champ.
Ne JAMAIS halluciner une marque ou une matière non visible.

Schema de sortie :
{
  "type": "robe|pantalon|veste|manteau|pull|chemise|jupe|top|accessoire|chaussures|sac|autre",
  "couleur": "bleu marine",
  "couleur_secondaire": null,
  "matiere": "coton|laine|soie|polyester|cuir|jean|lin|autre|null",
  "marque": "Sandro" | null,
  "taille": "S|M|L|XL|36|38|40|null",
  "etat": "excellent|tres_bon|bon|correct",
  "saison": "ete|hiver|mi-saison|toute_saison",
  "style": "minimaliste|vintage|boheme|chic|sport|rock|romantique|casual|business",
  "occasion": ["bureau","weekend","ceremonie","quotidien","soiree","ete","festival"],
  "motif": "uni|raye|fleuri|carreaux|pois|animal|geometrique|autre",
  "coupe": "slim|droit|oversize|cintre|fluide|ample|ajuste",
  "defauts": ["tache poignet droit","..."],
  "description": "Robe Sandro fluide bordeaux taille 36, en excellent état",
  "gamme_estimee": "entree|moyenne|premium",
  "confiance": 0.85
}
```

#### `store_mapping.md` (à créer)

```markdown
<!-- v1.0-2026-05 -->
Tu es expert merchandising pour boutique seconde main premium.
Tu analyses l'état actuel des zones et tu génères des recommandations
d'agencement actionnables, justifiées, faisables.

Sortie JSON strict avec 3 sections :
- recommendations[] : reco court-terme (j+1 à j+7)
- zone_suggestions[] : suggestions placement de pièces individuelles
- arrangement_changes[] : modifications structurelles (déplacement portant, etc.)

Chaque reco doit avoir :
- title (5-8 mots)
- reasoning (2 phrases max — pourquoi ?)
- impact_estimate ("low|medium|high")
- effort ("5min|15min|30min|1h+")

Données disponibles :
{{zone_stats}}
{{trending}}
{{stale}}
{{hot_categories}}
{{tags_zones}}
```

#### `window_display.md` (à créer)

```markdown
<!-- v1.0-2026-05 -->
Tu es styliste de vitrine pour boutique seconde main premium à Vernon.
Tu choisis 6 pièces (1 vedette + 5 secondaires) parmi les candidates,
selon : météo prévue 5 jours, événements locaux Vernon/Giverny, tendances.

Sortie JSON strict :
{
  "theme": "Printemps en bord de Seine",
  "vedette": { "product_id": "...", "reason": "..." },
  "secondaires": [
    { "product_id": "...", "reason": "...", "position": "gauche|droite|fond" },
    ...
  ],
  "color_palette": ["bordeaux","crème","kaki"],
  "duration_days": 7
}

Données :
{{season}}
{{weather_5d}}
{{top_score_products}}
{{events_locaux}}
```

#### `pricing_decision.md` (à créer)

```markdown
<!-- v1.0-2026-05 -->
Tu es analyste pricing pour boutique seconde main.
Tu décides si une pièce limite (score 30-50) doit être démarquée,
maintenue, ou retournée au tri.

Sortie JSON strict :
{
  "action": "MAINTENIR|DEMARQUER_10|DEMARQUER_20|DEMARQUER_30|RETOUR_TRI|DON",
  "reason": "1 phrase",
  "expected_uplift": "low|medium|high"
}

Données :
{{produit}}
{{score_breakdown}}
{{days_on_shelf}}
{{prix_actuel}}
{{categorie_avg}}
{{stock_categorie}}
```

#### `review_reply.md` (à créer)

```markdown
<!-- v1.0-2026-05 -->
Tu réponds aux avis Google de la boutique Vintiz Vernon.
Ton : professionnel, chaleureux, sincère. Jamais générique.

Règles :
- Note 5★ : remercier nominativement, mentionner 1 détail spécifique de l'avis
- Note 3-4★ : remercier + adresser le point soulevé + invitation au dialogue
- Note 1-2★ : excuse sincère + responsabilité + appel téléphone privé
- 3-5 phrases max, jamais d'emojis

Données :
{{note}}
{{commentaire}}
{{client_name}}
{{date_avis}}
```

### §8.4 — Conseils de rédaction (pour modifier un prompt)

1. **Tester avec 5 cas extrêmes** avant de pousser : photo floue, marque inconnue, vêtement abîmé, taille ambiguë, vintage 1960
2. **Mesurer la stabilité** : 5 appels successifs avec même input → variance ≤ 10% sur les 15 champs
3. **Auditer les hallucinations** : compter `null` retournés vs valeurs inventées (objectif : > 95% de précision)
4. **Versioning Git** : 1 commit = 1 modification de prompt avec test bench attaché
5. **A/B testing** : router 10% du trafic sur la nouvelle version pendant 1 semaine, comparer la métrique business (CTR pour PS, taux d'acceptation pour Booster)

---

## §9 — Roadmap exécutable

### Découpage en 6 livrables successifs

| # | Livrable | Effort | Bloquant pour suivant ? |
|---|---|---|---|
| L1 | Audit consolidé MD (ce document) | 1j | Non |
| L2 | UX btq : sidebar collapsible + mapping iso 2.5D + mobilier + tags zones + POS fidélité + cahier 2 temps + UI `/ia` | 5-7j | Non |
| L3 | Dataset démo : flag `is_test`, endpoint from-photo, 50 produits + 20 clientes témoins, scripts test PS / test POS / purge | 2-3j | L2 |
| L4 | Config scoring + scoring v2 (rampe transition saison + signal fashion-watch + decay temporel + seuil consignation) | 2-3j | L1 |
| L5 | Benchmark IA : test bench prompts Claude vs Mistral / GPT-4.1 / Gemini, recommandation finale | 2j | Non |
| L6 | Suppression reporting ESS dédié | 0.5j | Non |

**Total estimé** : 12,5 à 16,5 jours-homme.

### Tickets actionnables (par livrable)

#### L2 — UX btq

- L2.1 : sidebar collapsible iPad (`apps/web/src/components/layout/Sidebar.tsx`)
- L2.2 : mapping iso 2.5D + mobilier + tags zones (10 SVG + 7 composants React + 3 endpoints CRUD)
- L2.3 : POS fidélité enrichie (`LoyaltyCustomerCard` + service `customer_brief`)
- L2.4 : cahier du jour 2 temps + événements + opérations (`local_calendar` + `commercial_operations` + cron prévisionnel)
- L2.5 : refonte UI `/ia` 4 onglets cartes visuelles

#### L3 — Dataset démo

- L3.1 : migration `is_test` (Product + Client) + endpoint purge
- L3.2 : endpoint `POST /api/inventory/products/from-photo`
- L3.3 : `scripts/seed_demo_products.py` (50 produits via URLs externes)
- L3.4 : `scripts/seed_witness_clients.py` (20 clientes témoins variées)
- L3.5 : `scripts/test_personal_shopper_witness.py`
- L3.6 : `scripts/test_pos_e2e.py`
- L3.7 : `scripts/purge_test_data.py`

#### L4 — Scoring v2

- L4.1 : service `scoring_config.py` + table `app_settings`
- L4.2 : endpoints `GET/PUT /api/admin/scoring-config` + preview
- L4.3 : UI `ScoringWeightsPanel` (8 sliders + courbe + saison + seuil)
- L4.4 : composantes 7 (transition saison) + 8 (fashion-watch) dans `compute_score`
- L4.5 : service `fashion_watch.py` + cron quotidien Google Trends + Vinted
- L4.6 : migration `prompts/v1/` (extraction des 5 prompts inline restants)

#### L5 — Benchmark IA

- L5.1 : `scripts/ai_benchmark.py` (7 prompts × 20 cas × 5 modèles)
- L5.2 : rubrique de notation (4 axes par prompt, notation humaine 0-5)
- L5.3 : rapport `docs/AI_BENCHMARK_2026_05.md`
- L5.4 : service `ai_router.py` (multi-provider abstraction)
- L5.5 : UI admin `AIRoutingPanel`

#### L6 — Suppression ESS

- L6.1 : retirer page `/reports/ess-report` si présente
- L6.2 : marquer P4-002 obsolete dans `PLAN_ACTION_2026.md`
- L6.3 : conserver calcul backend pour exports ad-hoc

### Verification globale

```bash
# Tests
cd apps/api && pytest

# Lint + build
cd apps/api && ruff check app
cd apps/web && npm run lint && npm run build
cd apps/site && npm run lint && npm run build

# Cycle utilisateur de bout en bout
cd apps/api && alembic upgrade head
python scripts/purge_test_data.py
PYTHONPATH=apps/api python scripts/seed_demo_products.py
PYTHONPATH=apps/api python scripts/seed_witness_clients.py
PYTHONPATH=apps/api python scripts/test_personal_shopper_witness.py
PYTHONPATH=apps/api python scripts/test_pos_e2e.py
```

### Critères d'acceptation par persona

| Persona | Test | Critère |
|---|---|---|
| Sophie | Ouvrir POS sur iPad | Sidebar masquée, panier 14 items sans scroll, modal CB timeout 45s, `LoyaltyCustomerCard` apparaît au lookup |
| Camille | Modifier poids scoring | Slider + simu + sauvegarde en < 30s, signature cahier J et J-1 |
| Léa | Créer produit depuis photo | 1 clic sur "Photo + URL" → fiche pré-remplie, bouton imprimer étiquette branché |
| Clara | Lancer Personal Shopper | 5 recos cohérentes avec son style, narrative Claude OK, pas de `fallback_used` |
| Julien | Exporter plan boutique | Bouton "Exporter PDF" → A3 imprimable avec mobilier + tags zones |

---

## §10 — Annexes

### §10.1 — Fichiers de référence (ground-truth)

| Sujet | Fichier | Lignes clés |
|---|---|---|
| Formule scoring | `apps/api/app/services/scoring_service.py` | 62-177 |
| Vision 15 attributs | `apps/api/app/services/ai_vision.py` | 16-135 |
| Personal Shopper recommend | `apps/api/app/services/personal_shopper.py` | 47-285 |
| Embeddings + taste profile | `apps/api/app/services/embeddings.py` | 226-319 |
| Cold-start onboarding | `apps/api/app/services/onboarding.py` | 31-135 |
| Markdown engine déclaratif | `apps/api/app/services/markdown_engine.py` | 94-321 |
| AI mapping zones | `apps/api/app/services/ai_mapping.py` | 132-285 |
| POS UI | `apps/web/src/app/pos/page.tsx` | 1728 lignes |
| Mapping zones UI | `apps/web/src/app/zones/page.tsx` | 458 lignes |
| Settings tabs UI | `apps/web/src/app/settings/page.tsx` | 1329 lignes |
| AI Booster page | `apps/web/src/app/ia/page.tsx` | 1131 lignes |
| Cahier service | `apps/api/app/services/cahier_service.py` | — |
| AppSetting model | `apps/api/app/models/audit.py` | 25-30 |
| Migration pgvector | `apps/api/alembic/versions/0008_add_embeddings.py` | 40-102 |
| Prompts versionnés | `apps/api/prompts/v1/personal_shopper.md` + `social_posts.md` | — |

### §10.2 — Comparaison audits successifs

| Document | Date | Apport principal | Statut |
|---|---|---|---|
| `AUDIT_VINTIZ_2026.md` | avril 2026 | Vision V1 (event store, pgvector, NF525, 6 prompts, 5 personas) | Complet |
| `AUDIT_VINTIZ_DELTA_V2.md` | avril 2026 | Triangulation (3 audits parallèles ayant lu code) | Complet |
| `AUDIT_GROUND_TRUTH.md` | 26 avril 2026 | Vérification code vs audits V1+V2 | Complet |
| `PHASE_1_CLOTURE.md` | 26 avril 2026 | Clôture 10 tickets P0 | Phase 1 close |
| **`AUDIT_2026_05_BOUTIQUE.md`** | **mai 2026** | **Personas + comparaison marché + UX btq + scoring v2 + biblio prompts + benchmark IA** | **Ce document** |

### §10.3 — Commandes utiles

```bash
# Démarrage local
cd apps/api && uvicorn app.main:app --reload --port 8000
cd apps/web && npm run dev          # port 3000
cd apps/site && npm run dev         # port 3001

# Diagnostic
./scripts/diag.sh

# Reset DB prod (idempotent, à utiliser avec précaution)
./scripts/reset-prod.sh

# Backup
./scripts/backup.sh

# Smoke test post-deploy
./scripts/smoke_prod.sh

# Génération barcodes test
PYTHONPATH=apps/api python scripts/seed_test_products.py --docs-only
```

### §10.4 — Glossaire

| Terme | Définition |
|---|---|
| **AIT** | Average Inventory Turn — taux de rotation moyen du stock |
| **ESS** | Économie Sociale et Solidaire (Solidarité Textiles est un acteur ESS) |
| **FSM** | Finite State Machine — cycle de vie produit en états discrets |
| **GMROI** | Gross Margin Return On Inventory — marge brute / valeur stock moyen |
| **HNSW** | Hierarchical Navigable Small World — index pgvector pour similarité cosinus rapide |
| **MMR** | Maximal Marginal Relevance — algo de diversification de top-K |
| **NF525** | Norme française fiscale obligatoire pour caisse (chaînage SHA-256) |
| **PoS** | Point of Sale — caisse |
| **RFM** | Recency / Frequency / Monetary — segmentation client classique |
| **Sell-through** | Ratio ventes / stock initial sur une période |

---

**Fin du document.**

Pour la mise en œuvre des livrables L2-L6, se référer à `/root/.claude/plans/je-d-veloppe-une-application-cheeky-dewdrop.md`.








