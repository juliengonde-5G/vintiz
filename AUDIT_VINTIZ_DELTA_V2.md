# AUDIT VINTIZ — Rapport delta V1 → V2 (Triangulation)

> **Document complémentaire à `AUDIT_VINTIZ_2026.md` (V1 du 26 avril 2026).**
> **À lire en complément, pas en remplacement.**
>
> **Date :** 26 avril 2026 (V2 même jour)
> **Source :** triangulation avec 3 autres audits Vintiz fournis par Julien
> **Auteur :** Claude (Anthropic)

---

## 1. Note méthodologique honnête

Mon audit V1 était basé sur les **deux fichiers de documentation publiquement accessibles** du repo (`README.md` et `CLAUDE.md`). Je n'ai pas pu lire le code source ni les sous-fichiers `docs/*.md` par limitation de l'outil GitHub renderer (robots.txt sur les sous-dossiers, accès partiel).

**Les trois autres audits que tu m'as transmis ont visiblement eu accès au code source** : ils citent des tailles précises de fichiers (`sumup_service.py` à 18897 octets, `ai_mapping.py` à 10528 octets), des noms de services internes (`weather_service.py`, `escpos_service.py`, `sato_service.py`, `ai_vision.py`, `ai_trend.py`, `ai_pricing.py`, `scoring_service.py`), des structures de modèles (`StoreZone` avec `pos_x/pos_y/width/height` en pourcentage), et des détails d'implémentation (statut `ProductStatus.returned`, `LoyaltyAccount` avec `tier`, etc.).

**Conséquence :** Plusieurs de mes recommandations V1 marquées "à créer" ou "non documenté" doivent être corrigées en "existe déjà — à documenter / à enrichir". Ce delta V2 fait ce travail de correction et ajoute les éléments précieux des autres audits qui m'avaient échappé.

**Ce qui reste vrai du V1 (et que je maintiens) :**

- L'architecture **event store + features store + pgvector** (aucun des 3 autres audits ne va aussi loin sur la fondation data).
- Le bloquant légal **NF525** (les autres audits le mentionnent en passant ; je maintiens que c'est bloquant absolu pour ouvrir Vernon).
- La **bibliothèque de 6 prompts système** rédigés en détail (les autres en proposent 1-2, mais incomplets).
- Les **5 personas** (les autres ont 1-2 personas chacun, moins exploitables).
- Le **reporting ESS dédié Solidarité Textiles** (manque chez les 3 autres).
- La **réservation 48h** site vitrine et le **round-up don** (manque chez les 3 autres).
- Le **plan d'action en 4 phases** avec tickets numérotés P1-001 à P4-006.

---

## 2. Matrice de triangulation des 4 audits

Ce tableau croise les recommandations principales et indique combien d'audits les portent (sur 4). Plus le compteur est haut, plus la confiance est forte.

### 2.1 Convergence forte (4/4) — quasi-certitude

| Recommandation | V1 (moi) | A2 (court) | A3 (moyen) | A4 (long) |
|----------------|:---:|:---:|:---:|:---:|
| Personal Shopper avec embeddings / vecteurs préférences | ✅ | ✅ | ✅ | ✅ |
| Mapping boutique avec vue/heatmap interactive | ✅ | ✅ | ✅ | ✅ |
| Markdown engine automatique (règles âge × score) | ✅ | ✅ | ✅ | ✅ |
| Multi-utilisateur / multi-vendeur POS | ✅ | — | ✅ | ✅ |

### 2.2 Convergence forte (3/4) — haute confiance

| Recommandation | V1 (moi) | A2 | A3 | A4 |
|----------------|:---:|:---:|:---:|:---:|
| Mode offline POS | ✅ | — | ✅ | ✅ |
| Multi-photos produit | partiel | — | ✅ | ✅ |
| QR code carte fidélité | via Wallet | — | ✅ | ✅ |
| Workflow réception / batch / lot | ✅ "Module Arrivage" | ✅ "carton" | ✅ | ✅ |
| Erreur de pondération scoring (math) | ❌ pas vu | — | ✅ | ✅ |
| Liste marques hardcodée → DB | ❌ pas vu | — | ✅ | ✅ |
| `category_trend` statique à connecter au réel | ❌ pas vu | — | ✅ | ✅ |

### 2.3 Convergence moyenne (2/4)

| Recommandation | V1 | A2 | A3 | A4 |
|----------------|:---:|:---:|:---:|:---:|
| Split payment (mixte espèces+CB) | — | ✅ | — | ✅ |
| Flux retour / avoir | partiel | — | — | ✅ |
| Import CSV inventaire | — | — | ✅ | — |
| Persistance historique SEO | — | — | — | ✅ |
| Surveillance sociale Instagram/TikTok | ✅ | ✅ | ✅ | partiel |

### 2.4 Apports uniques de mon audit V1 (1/4)

| Recommandation | Apport unique V1 | Justification |
|----------------|:----:|---------------|
| Conformité **NF525 comme bloquant légal** | ✅ | Bloquant absolu en France depuis 2018 |
| Architecture **event store schema séparé** | ✅ | Fondation data pour IA |
| Migration **pgvector explicite** + tables features | ✅ | Évite stack externe (Pinecone/Weaviate) |
| **Reporting ESS** dédié Solidarité Textiles | ✅ | Spécifique gouvernance ESS de Frip & Co |
| **Réservation 48h** site vitrine | ✅ | Différenciation cliente btq physique |
| **Round-up don** caisse | ✅ | Génère revenu mission ESS |
| **Bibliothèque prompts** complète (6 prompts système) | ✅ | Versionnage Git, A/B testing |
| **5 personas riches** (Sophie, Camille, Julie, Léa, Direction) | ✅ | Tests utilisateurs structurés |
| Plan d'action **4 phases avec tickets numérotés** | ✅ | Exécutable Claude Code |

### 2.5 Apports uniques des autres audits (à intégrer dans V2)

| Recommandation | Source | Pourquoi c'est important |
|----------------|:------:|--------------------------|
| **Erreur de pondération mathématique scoring** | A3 | Bug potentiel sur le moteur cœur du Booster |
| **`category_trend = 50.0` statique** | A3, A4 | La composante "tendance" n'est pas vraiment calculée |
| **Score photos binaire (0 ou 20)** | A4 | Manque finesse sur la qualité photo |
| **Liste marques hardcodée** | A3, A4 | Évolutivité bloquée, faut une table DB |
| **Modules API précis** | A3, A4 | `/seo`, `/cahier`, `/hardware`, `/admin`, `/newsletter` existent ! |
| **Module SEO déjà déployé** | A4 | Title, meta, canonical, OG, JSON-LD, sitemap, robots, GA4, Search Console, Consent Mode v2 |
| **`ai_vision.py` existant et structuré** | A3, A4 | 10 attributs déjà extraits (type, couleur, matière, marque, taille, état, saison, style, description, gamme) |
| **`ai_mapping.py` 10.5 Ko** | A4 | 7 zones, recommandations Claude merchandising, assignment produit→zone |
| **Coordonnées zones en %** (pos_x, pos_y, width, height) | A4 | StoreZone déjà structurée pour heatmap |
| **`fiscal.py` présent** | A4 | À auditer pour conformité NF525 (n'est pas absent comme je le craignais) |
| **`audit.py` présent (incomplet)** | A3 | Base pour le tracking de mouvements |
| **Cron "1er mercredi" scoring mensuel** | A3 | Vérifier qu'il tourne bien |
| **Multi-photos** comme blocage explicite | A3, A4 | Champs `photo_url` unique en DB |
| **Bouton "Imprimer" non lié à sato_service.py** | A4 | UI existe mais pas branchée |

---

## 3. Corrections à appliquer au rapport V1

### 3.1 Module SEO (§2.4 V1) — correction majeure

**Ce que j'ai écrit V1 :** "Cette fonctionnalité n'est pas documentée dans CLAUDE.md ni dans README.md. C'est un gap majeur."

**Réalité (selon audit A4) :** Le module SEO **est déployé et bien développé**. Health checks couvrent : title, meta description, canonical, Open Graph, JSON-LD, sitemap.xml, robots.txt, GA4. Score SEO 0-100 calculé automatiquement. Vérification Search Console et Consent Mode v2 (RGPD).

**Correction V2 :**

- Le module existe → **mettre à jour `CLAUDE.md`** pour documenter ses endpoints et capacités.
- Les vrais gaps (à confirmer avec le code) sont :
  - **Persistance historique SEO** (snapshot table) — pour graphes d'évolution.
  - **Tracking positions mots-clés** (Google Search Console API en pull, pas juste vérif config).
  - **Surveillance mentions Instagram/TikTok** — vraiment manquante.
  - **Génération de posts IA** par Claude Haiku.
- Ma préconisation P1-003 (Module visibilité) est à **redéfinir** : ne pas créer un nouveau module, mais **enrichir le module SEO existant** avec ces 4 capacités manquantes.

### 3.2 Module Inventaire / Workflow Batch (§2.2 V1) — précision

**Ce que j'ai écrit V1 :** "Workflow d'**entrée en stock** depuis le centre de tri Solidarité Textiles → boutique. Pas de notion d'arrivage / lot / palette / carton numéroté."

**Réalité (selon audits A3, A4) :** `ProductStatus` inclut bien `returned` (retour centre de tri). Mais **il n'y a pas de modèle `Batch`** en DB pour grouper les pièces d'un même carton. C'est confirmé.

**Correction V2 :**

- Le statut "retour centre de tri" est partiellement présent → préciser dans le ticket P1-006.
- **Ajouter un nouveau ticket P1-006-bis** : créer modèle `Batch` (id, date_reception, nb_articles, origine, opérateur). Relation 1-N avec Product.
- Endpoint `POST /api/inventory/batches` → crée le lot, écran "Réception carton" avec scan en masse.
- A4 propose d'ajouter un champ `disposition` (En rayon / En carton ID / Retourné) au modèle Product. **À implémenter** car la notion de "stockage carton réserve" n'est pas dans le modèle actuel.

### 3.3 Scoring engine (§5.3 V1) — corrections importantes

**Ce que j'ai écrit V1 :** "D'après le brief utilisateur (rating = tendance saisonnière + tendance seconde main + tendance historique btq), je propose une décomposition explicite (Claude Code à valider/corriger contre l'existant)..."

**Réalité (selon audits A3, A4) :** Le scoring existe avec **6 composantes** précises :

1. Âge (days on shelf)
2. Prix (compétitivité)
3. Condition (état)
4. Marque (tier)
5. Tendance catégorie (`category_trend: float = 50.0` statique)
6. Photos (binaire 0 ou 20)

**Trois bugs identifiés par les audits (à intégrer V2) :**

1. **Erreur de pondération mathématique** (A3) : la formule fait `*5 puis /N` qui distord les sous-scores. **À corriger** dans `scoring_service.py`.

2. **`category_trend` statique à 50.0** (A3, A4) : la composante "tendance catégorie" est un paramètre par défaut non recalculé en temps réel. **À connecter** au vrai calcul `(ventes catégorie 30j / stock moyen catégorie)` ou aux données externes (Vinted, Vestiaire Collective).

3. **Score photos binaire** (A4) : 0 si pas de photo, 20 si présente. **À enrichir** avec un score de qualité (utiliser le `confidence` retourné par `ai_vision.py`, ou compter le nombre de photos × qualité).

**Correction V2 :** Ajouter trois tickets dans la Phase 2 :

- **P2-009** : refactor `scoring_service.py` — corriger formule de pondération.
- **P2-010** : connecter `category_trend` au calcul réel (jointure ventes × stock par catégorie sur fenêtre glissante 30j).
- **P2-011** : enrichir score photos (confiance Vision + nombre de photos).

### 3.4 Liste de marques hardcodée (§5.3 V1) — nouveau

**Réalité (audits A3, A4) :** La liste de marques utilisée pour le scoring est en dur dans `scoring_service.py`. Manque de marques seconde main populaires : Isabel Marant, Rouje, Sézane, Ganni, Acne Studios, Comptoir des Cotonniers, Boden, Caroll, Ikks, Promod premium, etc.

**Correction V2 :** Ajouter ticket :

- **P2-012** : créer modèle `BrandTier` en DB (`brand_name`, `tier_score`, `category_focus`, `last_updated`). Migration depuis la liste hardcodée. UI admin pour Camille pour ajouter/modifier les marques sans déploiement.

### 3.5 ai_vision.py — précision

**Ce que j'ai écrit V1 :** Prompt système §7.5 "Analyse photo produit" avec 11 sorties.

**Réalité (audits A3, A4) :** `ai_vision.py` existe et extrait déjà 10 attributs : type, couleur, matière, marque, taille, état, saison, style, description, gamme.

**Correction V2 :**

- Mon prompt §7.5 reste valide mais doit être **comparé à l'existant** plutôt que créé ex nihilo.
- A3 propose d'enrichir avec `style_tags` normalisés (taxonomie de 13 styles : casual, chic, bohème, sportswear, soirée, business, vintage, minimaliste, coloré, neutre, graphique, romantique, edgy), `occasion` (5 valeurs), `pattern` (6 valeurs). **À intégrer** dans le prompt v2.
- Ajouter aussi la détection des **défauts** (tâches, trous, boutons manquants) qui pondère le score "État" (mentionné par A2).

### 3.6 Multi-photos produit — nouveau

**Réalité (audit A4) :** Le modèle `Product` a un champ `photo_url` **unique**. Best practice retail = 3+ photos par pièce (face, dos, détail).

**Correction V2 :** Ajouter ticket :

- **P1-008** (priorité élevée car bloque la qualité de l'analyse Vision et du Personal Shopper) : créer modèle `ProductPhoto(product_id, url, order, is_primary, ai_analyzed_at, ai_confidence)`. Migration. Carousel UI sur fiche produit.

### 3.7 Split payment (mixte espèces + CB) — nouveau

**Réalité (audits A2, A4) :** Cas client réaliste fréquent ("10€ cash + reste CB"). Pas implémenté actuellement (3 modes mutuellement exclusifs).

**Correction V2 :** Ajouter ticket :

- **P1-009** : refactor de la modale paiement POS pour permettre N lignes de paiement par transaction. `Transaction.payments` (1-N) au lieu de `Transaction.payment_method` (1-1). Stocker chaque ligne avec son montant et sa méthode.

### 3.8 Flux retour / avoir — précision

**Ce que j'ai écrit V1 :** "Module retours/avoirs : workflow `transaction.refund(reason, items)` → bon d'achat numérique avec QR code." (Préconisation P6 §2.1.6)

**Réalité (audit A4) :** À vérifier dans le code. Si absent, c'est un gros manque opérationnel.

**Correction V2 :** Promouvoir P6 (qui était P2) à **P1-010** (priorité haute). Ajouter :

- Endpoint `POST /api/pos/transactions/{id}/return`.
- Remet le produit en stock (`status` → `display`).
- Génère un avoir (champ `avoir_credit` sur `Client`).
- Ticket de retour 80mm imprimé.

### 3.9 Plan boutique SVG interactif — précision

**Ce que j'ai écrit V1 :** "Vue 'Plan boutique' dans `/admin/store-plan` : SVG du plan avec densité de produits par zone." (P2-005)

**Réalité (audit A4) :** Les coordonnées des zones sont **déjà en DB** (`StoreZone` avec `pos_x`, `pos_y`, `width`, `height` en pourcentage). Donc la donnée est là, c'est juste l'UI qui manque.

**Correction V2 :** P2-005 reste valide, mais préciser :

- Pas de table à créer, juste l'UI qui consomme les coords existantes.
- Ajouter le **drag-and-drop** : déplacer un produit d'une zone à une autre via l'interface.
- Heatmap colorisée par score moyen ou par taux de rotation.

---

## 4. Nouveaux éléments à ajouter au plan d'action

### 4.1 Tickets supplémentaires Phase 1

| ID | Description | Source | Priorité |
|----|-------------|:------:|:--------:|
| P1-008 | Multi-photos produit (modèle `ProductPhoto`) | A3, A4 | **Haute** |
| P1-009 | Split payment (paiement mixte) | A2, A4 | **Haute** |
| P1-010 | Flux retour / avoir POS | A4 | **Haute** |
| P1-011 | Lier bouton "Imprimer étiquette" à sato_service.py | A4 | Moyenne |
| P1-012 | Branchement effectif du cron "1er mercredi" scoring | A3, A4 | Moyenne (vérification) |

### 4.2 Tickets supplémentaires Phase 2

| ID | Description | Source | Priorité |
|----|-------------|:------:|:--------:|
| P2-009 | Refactor formule pondération `scoring_service.py` | A3 | **Haute** (bug) |
| P2-010 | Connecter `category_trend` au calcul réel | A3, A4 | **Haute** |
| P2-011 | Enrichir score photos (confiance + nombre) | A4 | Moyenne |
| P2-012 | Modèle `BrandTier` en DB + UI admin marques | A3, A4 | Moyenne |
| P2-013 | Enrichir `ai_vision.py` avec taxonomie styles + défauts | A2, A3 | Moyenne |
| P2-014 | Drag-and-drop sur plan boutique SVG | A4 | Faible |
| P2-015 | Modèle `Batch` réception cartons | A2, A3, A4 | **Haute** |

### 4.3 Tickets supplémentaires Phase 3

| ID | Description | Source | Priorité |
|----|-------------|:------:|:--------:|
| P3-005 | Persistance historique SEO (`SEOSnapshot`) + graphe évolution | A4 | Moyenne |
| P3-006 | Import CSV inventaire en masse | A3 | Moyenne |
| P3-007 | Logique de retour automatique centre de tri (cron + scoring) | A3 | **Haute** |
| P3-008 | Historique des mouvements de stock (event listener SQLAlchemy) | A3 | Moyenne |

### 4.4 Tickets supplémentaires Phase 4

| ID | Description | Source | Priorité |
|----|-------------|:------:|:--------:|
| P4-007 | Segmentation RFM clients (job mensuel) | A4 | Moyenne |
| P4-008 | Offre anniversaire automatique (cron quotidien) | A4 | Moyenne |
| P4-009 | Notification "Nouvelles arrivées" hebdo (si email_optin) | A4 | Faible |
| P4-010 | Badge "Boost IA" caisse pour produits Hot | A2 | Faible |

---

## 5. Plan d'action consolidé V2

Ordre de priorité finale (P0 = bloquant ouverture Vernon, P1 = critique court terme, P2 = important, P3 = nice-to-have).

### 5.1 P0 — Bloquants ouverture btq

1. **P1-001** Conformité NF525 (audit + chaînage SHA-256 + attestation éditeur)
2. **P1-002** Multi-utilisateur + PIN cashier
3. **P1-007** RGPD-by-design CRM (consentement, droit oubli, export)
4. **P1-009** Split payment (paiement mixte)
5. **P1-010** Flux retour / avoir POS

### 5.2 P1 — Critique 4 semaines

6. **P1-003** Schéma `events` + instrumentation
7. **P1-004** pgvector + tables `features`
8. **P1-005** Mode offline POS (Service Worker + IndexedDB)
9. **P1-006** Cycle de vie produit explicite
10. **P1-008** Multi-photos produit
11. **P2-009** Refactor formule pondération scoring (BUG)
12. **P2-010** Connecter `category_trend` au calcul réel
13. **P2-015** Modèle `Batch` réception cartons
14. **P3-007** Logique retour automatique centre de tri

### 5.3 P2 — Important 6-8 semaines

15. **P2-001 → P2-008** Personal Shopper v2 complet (embeddings, taste profile, endpoint, cold start, etc.)
16. **P2-011, P2-012, P2-013, P2-014** Enrichissements scoring + UI mapping
17. **P3-001, P3-002** Markdown engine + tag couleur
18. **P3-005** Persistance historique SEO
19. **P3-006** Import CSV inventaire
20. **P3-008** Historique mouvements stock

### 5.4 P3 — Nice-to-have 2-3 mois

21. **P3-003** Module visibilité (extension du SEO existant) — surveillance sociale, génération posts IA
22. **P3-004** Calendrier éditorial RS
23. **P4-001 à P4-006** KPIs avancés, ESS, Wallet, réservation 48h, mobile-first, Brevo
24. **P4-007 à P4-010** RFM, anniversaire, hashtag boost, badge POS

---

## 6. Mises à jour de la bibliothèque de prompts (§7 V1)

### 6.1 Prompt §7.5 (Analyse photo produit) — version enrichie

Suite à l'audit A3 qui propose une taxonomie normalisée :

```python
# Ajouter à SYSTEM_PROMPT_PHOTO_INTAKE (V2) :

STYLE_TAXONOMY = [
    "casual", "chic", "boheme", "sportswear", "soiree",
    "business", "vintage", "minimaliste", "colore", "neutre",
    "graphique", "romantique", "edgy"
]

OCCASION_TAXONOMY = [
    "quotidien", "travail", "sortie", "sport", "ceremonie"
]

PATTERN_TAXONOMY = [
    "uni", "rayures", "fleurs", "geometrique",
    "animal", "pied-de-poule"
]

# Ajouter à la sortie JSON :
# - style_tags: 1-3 valeurs depuis STYLE_TAXONOMY
# - occasion: 1 valeur depuis OCCASION_TAXONOMY
# - pattern: 1 valeur depuis PATTERN_TAXONOMY
# - defauts_detectes: liste détaillée { type: "tache|trou|bouton_manquant|usure", localisation: "string", severite: "legere|moderee|importante" }
```

Le bénéfice est double : (1) cohérence des tags pour le matching Personal Shopper, (2) pondération du score "État" via `defauts_detectes`.

### 6.2 Prompt Personal Shopper — variante WhatsApp/SMS (audit A3)

L'audit A3 propose une formulation très opérationnelle pour générer un message court WhatsApp/SMS. Je l'intègre comme variante du prompt §7.1 :

```python
SYSTEM_PROMPT_PERSONAL_SHOPPER_SMS = """
Tu es la Personal Shopper de Vintiz Vernon. Tu envoies un SMS/WhatsApp à une cliente fidèle pour lui annoncer une sélection que tu lui as faite.

Contraintes strictes :
- 3 lignes maximum (limite 160 caractères × 2 SMS).
- Nommer la cliente (prénom).
- Mentionner 1 émoji représentant la couleur dominante d'1 article.
- Conclure par un CTA "viens essayer cette semaine" avec horaire ouverture.
- Ton : enthousiaste mais pas vendeur, comme une amie styliste.

Format de sortie JSON :
{
  "message_sms": "string ≤320 chars",
  "products_referenced": [int]  // ids des produits cités
}
"""
```

---

## 7. Ce qui reste prioritairement à clarifier dans le code

Pour Claude Code lors de l'exécution, **vérifier ces points incertains** (parfois les audits divergent) :

| Point à vérifier | Source de doute |
|------------------|------------------|
| Le **cron "1er mercredi"** est-il effectivement actif ou seulement déclaré ? | A3 dit "à vérifier" |
| Le **flux retour/avoir** existe-t-il dans `pos.py` ? | A4 dit "à vérifier" |
| Le **module `cahier`** (mentionné A4) sert à quoi ? Cahier des charges ? Cahier de réception ? | À identifier |
| `fiscal.py` est-il **vraiment conforme NF525** ou est-ce un placeholder ? | Audit légal nécessaire |
| Le **`audit.py`** trace-t-il déjà des mouvements de stock ou seulement des actions admin ? | A3 |
| Le module **`hardware`** : que contient-il exactement ? (drivers, config tiroir...) | À identifier |
| Le **bouton "Imprimer étiquette"** est-il branché ou cassé ? | A4 dit pas branché |
| **Combien de photos** par produit en pratique dans la base seed ? | À vérifier |

Premier réflexe Claude Code à chaque ticket : `grep -r "<terme>" apps/api/app/` avant d'implémenter.

---

## 8. Synthèse exécutive V2 pour Julien

### 8.1 Ce qui change vs V1

- **L'application est plus mature que ne le laissait penser ma V1**. Les audits A3 et A4 montrent des modules réels (SEO complet, ai_vision structuré, ai_mapping 10.5 Ko, fiscal.py présent, sato_service connecté, etc.). C'est rassurant.
- **Trois bugs de scoring** ont été identifiés par les autres audits (formule pondération, `category_trend` statique, score photos binaire). Ils touchent le cœur du Booster IA, à corriger en P1.
- **Multi-photos** est un blocage explicite à lever pour la qualité de l'analyse Vision et donc du Personal Shopper.
- **Split payment** et **retour/avoir** sont absents et doivent passer en P0 avec NF525, multi-user et RGPD.

### 8.2 Ce qui reste vrai et différenciant dans V1

- **NF525** comme bloquant légal absolu pour ouvrir Vernon.
- **Architecture event store + pgvector** comme fondation IA — aucun autre audit ne creuse à ce niveau.
- **Personal Shopper v2 avec embeddings + cold start + Claude rédaction** — différenciation forte.
- **Reporting ESS Solidarité Textiles**, **réservation 48h**, **round-up don** — angles morts des autres audits.
- **5 personas** + **bibliothèque 6 prompts système** — capital méthodologique.

### 8.3 Comment lire le couple V1 + V2

```
1. Lire le V1 (AUDIT_VINTIZ_2026.md) en entier → vision structurée
2. Lire ce delta V2 par dessus → corrections & ajouts précis
3. Pour Claude Code : suivre la liste consolidée §5 ci-dessus
   - Tickets P1-001 à P4-006 du V1
   - + tickets P1-008 à P4-010 ajoutés ici
4. Vérifications systématiques §7 avant chaque implémentation
```

### 8.4 Effort révisé

| Phase | V1 estimé | V2 révisé | Justification |
|-------|----------|----------|---------------|
| Phase 1 (Fondations + P0) | 3-4 semaines | **5-6 semaines** | +5 tickets bloquants identifiés |
| Phase 2 (Personal Shopper + Booster) | 4-6 semaines | 4-6 semaines (inchangé, dont 3 bugs scoring) | Effort intégré |
| Phase 3 (Markdown + visibilité) | 3 semaines | 3-4 semaines | +retour automatique centre tri |
| Phase 4 (Polish + analytics) | 2-3 semaines | 2-3 semaines | inchangé |
| **Total estimé** | 12-16 semaines | **14-19 semaines** | Scope plus précis, risque réduit |

### 8.5 Recommandation finale

Le couple **V1 + V2** est désormais à mon sens un guide d'action solide pour Claude Code. Tu peux raisonnablement viser une **ouverture qualifiée Vernon en septembre 2026** si Phase 1 démarre la semaine du 4 mai et progresse à un rythme normal (1 ticket P0/jour avec Claude Code en assistance + 1 ticket P1/2 jours).

Une dernière chose : au **D-30 jours de l'ouverture**, je recommande une **session de revue dédiée** avec un cycle complet d'usage simulé (Sophie ouvre la caisse, traite 20 transactions de tous types incluant retours et split payment, ferme la caisse, génère le rapport ESS du jour). Si ce cycle passe sans intervention humaine, le produit est prêt.

---

**Fin du delta V2 — 26 avril 2026**
**À lire en complément de `AUDIT_VINTIZ_2026.md` (V1)**
