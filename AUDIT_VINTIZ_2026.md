# AUDIT VINTIZ — Rapport d'audit fonctionnel & plan d'action

> **Document destiné à :** Julien Gondé (Président) + Claude Code (exécution)
> **Périmètre :** Application Vintiz (ERP boutique seconde main + site vitrine + Personal Shopper + AI Booster)
> **Repository :** https://github.com/juliengonde-5G/vintiz/
> **Branche audit :** `main` (référence) + `claude/fix-product-features-LbqVr` / `claude/prepare-pos-software-stoSD`
> **Date de l'audit :** 26 avril 2026
> **Boutique cible :** Frip & Co — 6 rue Saint-Jacques, Vernon (Eure, 27)
> **Version :** 1.0

---

## 0. Sommaire exécutif

### 0.1 Vue synthétique

Vintiz est un ERP boutique seconde main premium en monorepo (FastAPI + 2× Next.js 14), conteneurisé Docker, déployé sur VPS Scaleway derrière Caddy. Le périmètre fonctionnel couvert dans le code (lu dans `CLAUDE.md`) est déjà large : POS tactile iPad avec douchette USB HID, intégration SumUp Solo (3 modes : prod/sandbox/simulation), inventaire avec génération de codes-barres, scoring produit 6 composantes, dashboard manager, espace client carte fidélité avec Personal Shopper IA, et un module "AI Booster" exploitant Claude Vision + Haiku 4.5.

**Ce qui marche bien aujourd'hui (état lu dans la doc) :**

- Stack moderne et maintenable, séparation propre API / admin / vitrine.
- Hardware POS clairement spécifié (Inateck 160B, 80mm thermique, RJ11, SumUp Solo) — c'est rare et c'est précieux.
- Mode "simulation SumUp" permettant de développer/tester sans frais réels.
- Intégration LLM déjà présente (Claude Haiku 4.5) pour scoring, checklist hebdo, persona marketing/juridique.
- Tickets renvoyables email/SMS avec graceful fallback en mode simulation.

**Les 7 zones d'écart majeures vs. marché (résumé — détails par module) :**

| # | Zone | Risque/Manque | Priorité |
|---|------|---------------|----------|
| 1 | **Personal Shopper** : recommandation basée historique uniquement | Moteur trop pauvre vs. Pixyle/Refabric (pas de visual similarity, pas de filtres style/morphologie) | **P0** |
| 2 | **AI Booster — Mapping boutique** : zones statiques, pas de planogramme dynamique | Manque de heatmap, pas de score "facing visibility", pas de recommandation cross-merchandising | **P0** |
| 3 | **Pricing dynamique** : 6 composantes scoring mais pas de markdown engine connecté | Pas de pricing piecewise (J+30/J+60/J+90), pas d'élasticité prix, pas de tag couleur/semaine | **P1** |
| 4 | **SEO & RS monitoring** : non documenté dans `CLAUDE.md` | Fonctionnalité annoncée dans le brief non visible côté code | **P1** |
| 5 | **Reporting Retail** : KPIs journaliers OK mais pas de cohorte client / sell-through par catégorie | Manque sell-through rate, GMROI, panier moyen par persona | **P1** |
| 6 | **Carte de fidélité** : Bronze/Silver/Gold codé mais pas de gamification / triggers SMS comportementaux | Vs. Sephora/Nike Run Club : manque le "next reward" et le push évènementiel | **P2** |
| 7 | **Données froides** : pas d'évidence d'un vrai data warehouse / event store pour entraînement modèles | Risque de plafond de qualité du Personal Shopper et du Booster sans schéma événementiel | **P0** |

### 0.2 Trois recommandations structurantes

1. **Établir une couche événementielle (event store)** avant de pousser plus loin l'IA. Sans `events` table normalisée (`product_viewed`, `product_tried`, `product_sold`, `customer_visited`, `zone_entered`...), le Personal Shopper et le Booster vont plafonner sur des règles statiques. C'est le socle.

2. **Découpler le scoring (rating) du pricing**. Aujourd'hui les 6 composantes du score sont mentionnées pour décrire l'attrait produit, mais la doc ne montre pas explicitement la table de correspondance `score → prix` ni `âge_btq → markdown`. Il faut un **markdown engine** déclaratif (config en base, pas en code) que le manager peut éditer.

3. **Industrialiser la prise de vue produit**. Le Personal Shopper et la détection AI sont aussi bons que les images d'entrée. Aujourd'hui Claude Vision est appelée ; la qualité dépend de la rigueur de prise de vue. Il faut un workflow guidé (cadre, fond, lumière) pour les 100-200 produits hebdo qui transitent en btq.

### 0.3 Effort estimé

| Phase | Effort | Échéance recommandée |
|-------|--------|----------------------|
| **Phase 1 — Fondations data + corrections P0** | 3-4 semaines (Claude Code + revue Julien) | Mai 2026 |
| **Phase 2 — Personal Shopper v2 + Booster Mapping** | 4-6 semaines | Juin-Juillet 2026 |
| **Phase 3 — Markdown engine + SEO/RS monitoring** | 3 semaines | Septembre 2026 |
| **Phase 4 — UX polish + analytics avancées** | 2-3 semaines | Octobre 2026 |

---

## 1. Méthodologie de l'audit

Pour chaque fonctionnalité du brief (1.a → 3.b), le rapport applique la grille suivante :

1. **Statut documentation** — ce qui est explicitement décrit dans `README.md` + `CLAUDE.md` (les seuls documents publics du repo).
2. **Pertinence du développement** — analyse de cohérence du choix technique vs. besoin métier.
3. **Pratiques marché** — comparaison avec : Circle-Hand, Ricochet, SimpleConsign, ThriftCart, KORONA, Shopify POS + Circular AI, Rose POS (consignment) et LEAFIO/PlanoHero (visual merchandising).
4. **Gaps identifiés** — différences observables.
5. **Persona utilisateur** — vue d'un acteur réel du parcours.
6. **Préconisations** — actions concrètes, priorisées, exécutables par Claude Code.
7. **Ajustements UX** — interventions UI précises.

Une note importante sur le périmètre : je n'ai pas pu lire les fichiers source au-delà des deux fichiers de doc publics (`README.md` et `CLAUDE.md`), ni les schémas de base. Quand je dis "non documenté", cela veut dire **non visible dans la doc publique** — il est possible que la fonctionnalité existe dans le code. La première action de Claude Code en lisant ce rapport est donc systématiquement : **vérifier le code, mettre à jour `CLAUDE.md` si la doc est en retard sur le code, sinon implémenter**.

### 1.1 Personas de référence utilisés

| Code | Persona | Description courte |
|------|---------|--------------------|
| **P-CLI-FID** | Cliente fidèle Julie, 38 ans, Vernon | Carte Gold, vient 2×/mois, panier moyen 65€, pousse les copines à venir, sensible au matching style |
| **P-CLI-DEC** | Cliente découverte Léa, 25 ans, Évreux | Carte Bronze récente, 1 visite, cherche des pièces uniques pour Insta, sensible aux trends Vinted |
| **P-EMP-BTQ** | Employée boutique Sophie, 45 ans | A peur de la techno mais doit gérer le POS, étiquetage, mise en rayon ; volume = 100 pièces/jour à intégrer |
| **P-MAN-RET** | Manager retail Camille (Julien IRL en partie) | Décide pricing, vitrine, suit les KPIs, aime les rapports synthétiques exploitables sur mobile |
| **P-COM-DIR** | Direction Solidarité Textiles | Suit la rentabilité par boutique, décide d'ouvrir une 2ème boutique si modèle réplicable |

Ces 5 personas reviennent dans chaque section du rapport quand pertinent.

---

## 2. Audit fonctionnel — ERP Boutique (Périmètre 1)

### 2.1 — Système d'encaissement (1.a)

#### 2.1.1 Statut documentation

`CLAUDE.md` documente clairement :

- Interface tactile iPad 1024×768 mono-écran (pas de scroll jusqu'à 5-6 articles).
- Champ recherche auto-focus + douchette USB HID Inateck 160B (scan → Entrée → ajout panier).
- 3 modes paiement : Espèces (rendu monnaie + ouverture tiroir auto), CB SumUp (Solo + polling + push direct via `SUMUP_READER_ID`), Chèque.
- Remises par article (palette 0/5/10/15/20/30%).
- Fidélité : affichage points + toggle rachat (1 pt = 0,10€, max 50% panier).
- Ouverture/fermeture caisse : fond initial, rapport Z, écart attendu vs compté.
- Ticket à la demande après vente (modal imprimer/fermer), AirPrint 80mm.
- Reçu renvoyable email/SMS.
- Mode simulation SumUp avec event log + approve manuel.

C'est **propre, complet et différenciant** vs. la majorité des POS du marché.

#### 2.1.2 Pertinence du développement

**Forts :**

- Le choix d'iPad + Inateck 160B (USB HID = clavier émulé) est le couple le plus standard et le plus stable pour un POS retail tactile. Pas de driver custom à maintenir.
- AirPrint pour ticket = pas d'imprimante propriétaire à driver. La pop-up `window.print()` = portable.
- 3 modes SumUp (prod/sandbox/simu) = excellente DX, permet de développer sans frais ni hardware.
- L'ouverture du tiroir via "open drawer on print" sur l'imprimante thermique est la pratique standard.

**Points de vigilance :**

- **Persistance offline** : Square POS, par exemple, prend les paiements CB en mode offline et les traite quand la connexion revient. La doc Vintiz ne mentionne pas de mode offline. Une coupure ADSL à Vernon = caisse bloquée = pertes directes.
- **Multi-utilisateur en caisse** : un seul user `admin` documenté. En pratique en btq, il faut au minimum tracer "qui était à la caisse" pour la responsabilité du fond et l'écart Z. Indispensable légalement (audit, contrôle fiscal NF525 français).
- **Conformité NF525 / loi anti-fraude TVA française** : Pas mentionné dans la doc. C'est **obligatoire** en France pour tout logiciel d'encaissement depuis 2018 (sécurisation, inaltérabilité, conservation 6 ans, archivage). Le décret 2016-1138 et le BOI-TVA-DECLA-30-10-30 imposent attestation éditeur ou certification organisme accrédité (LNE, Infocert).

#### 2.1.3 Pratiques marché

| Critère | Vintiz | Square POS | Shopify POS | Circle-Hand | KORONA |
|---------|--------|------------|-------------|-------------|--------|
| iPad-first | ✅ | ✅ | ✅ | ✅ | ✅ |
| Lecteur code-barres USB HID | ✅ Inateck 160B | ✅ | ✅ | ✅ | ✅ |
| Mode offline CB | ❌ (à confirmer) | ✅ | ❌ | — | ✅ |
| Hotkeys panier | ❓ | ✅ | ✅ | — | ✅ |
| Multi-user / PIN cashier | ❌ | ✅ | ✅ | ✅ | ✅ |
| Conformité NF525 (FR) | ❓ | Partielle | Partielle | — | ✅ |
| Round-up don | ❌ | Via app | Via app | — | ✅ via ThriftCart |
| Commission consignation | N/A pour Frip & Co | Add-on | Add-on | ✅ | ✅ |

#### 2.1.4 Gaps

| Gap | Impact | Sévérité |
|-----|--------|----------|
| Mode offline CB / espèces | Vente bloquée si coupure réseau | **Élevée** |
| Multi-utilisateur + PIN | Traçabilité, audit, écart Z attribué | **Élevée** |
| Conformité NF525 | Risque fiscal légal | **Bloquante** |
| Hotkeys produits courants | Vitesse de scan en heures de pointe | Moyenne |
| Round-up don à Solidarité Textiles | Manque à gagner sur la mission ESS de l'asso | Moyenne |
| Gestion retours/remboursements | Non explicite dans la doc | Moyenne |
| Gestion bons d'achat / avoirs | Non explicite | Moyenne |

#### 2.1.5 Persona — Sophie (P-EMP-BTQ)

> "Le samedi à 11h, j'ai trois clientes en caisse en même temps. Si la connexion plante et que Vintiz me dit 'erreur', qu'est-ce que je fais ? Je note sur un bout de papier ? J'ai aussi peur de me tromper de fond de caisse le matin parce que je n'ose pas dire à Camille que j'ai mis 100€ au lieu de 80€."

→ Sophie a besoin d'un mode offline + d'un PIN personnel (sa caisse n'est pas celle de Léa qui ouvre le mardi) + d'une UI qui *guide* le fond de caisse plutôt que de l'imposer.

#### 2.1.6 Préconisations

**P0 — bloquant (à faire avant ouverture publique de la btq Vernon)**

1. **Conformité NF525** : obtenir une attestation éditeur Vintiz signée + audit du code par avocat fiscaliste. Implémenter le journal d'événements inaltérable (chaînage cryptographique des transactions, ex : SHA-256 chaîné sur `prev_hash + transaction_payload`). Activer l'archivage légal 6 ans avec scellement annuel.
2. **Multi-utilisateur + PIN cashier** : table `users` avec rôles (`manager`, `cashier`), PIN 4 chiffres au login caisse, association `transaction.cashier_id`.

**P1 — important**

3. **Mode offline** : queue locale IndexedDB côté Next.js, rejeu automatique à la reconnexion. Pour CB SumUp spécifiquement, accepter les paiements espèces et basculer SumUp sur "à valider" en différé.
4. **Hotkeys produits** : 6 boutons configurables (sacs Le Tanneur, jeans Levi's, etc. = top 6 produits récurrents).
5. **Round-up don** : option case à cocher en POS, somme arrondie à l'euro supérieur reversée à Solidarité Textiles. Tracker dans une table `donations` séparée.
6. **Module retours/avoirs** : workflow `transaction.refund(reason, items)` → bon d'achat numérique avec QR code.

**P2 — nice-to-have**

7. **Hardware fallback** : si imprimante AirPrint indisponible, afficher un QR code que la cliente scanne pour récupérer son ticket par email immédiat.

#### 2.1.7 Ajustements UX

- Bouton "Suspendre la vente" (sale parking) pour gérer une cliente qui retourne en cabine.
- Indicateur visuel de connectivité (pastille verte/orange/rouge en haut à droite).
- Confirmation "fond de caisse" avec calculatrice tactile au lieu d'un input texte.
- Sur le rapport Z : graphique en camembert paiement par mode + alerte rouge si écart > 5€.

---

### 2.2 — Gestion de stock et d'inventaire (1.b)

#### 2.2.1 Statut documentation

Documenté dans `CLAUDE.md` :

- Création produit avec génération automatique de code-barres (Code 128, python-barcode + Pillow).
- Fiche produit avec score 6 composantes (détaillé sous le module IA).
- Date de mise en rayon, emplacement zone (7 zones prédéfinies pour la btq L 98m²).
- Édition inline prix / zone / statut.
- Bouton "Générer étiquette" → PNG téléchargeable/imprimable.
- Recherche avec filtre stock+display par défaut, `&include_sold=true` sinon.
- Seed de 300 produits + 50 clients + 200 transactions, idempotent.

**Manquant dans la doc :**

- Workflow d'**entrée en stock** depuis le centre de tri Solidarité Textiles → boutique. Pas de notion d'arrivage / lot / palette / carton numéroté.
- Workflow de **retour centre de tri** des invendus (le brief le mentionne explicitement, le code/doc ne semble pas le couvrir).
- Workflow d'**étiquetage en lot** (étiqueter 50 pièces d'un seul coup).
- Statuts produit explicites (`reçu`, `trié`, `étiqueté`, `mis en rayon`, `démarqué`, `invendu`, `retour tri`, `vendu`, `donné`).

#### 2.2.2 Pertinence du développement

**Forts :**

- Code 128 = standard universel, lecture par n'importe quelle douchette.
- Génération PNG = imprimable sur Brother/Dymo/Phomemo (tous les labels supportés par le marché thrift).
- Score 6 composantes intégré au produit = bonne pratique (Circular AI, Refabric font pareil).

**Points de vigilance :**

- Les **7 zones figées** pour 98m² sont commodes pour démarrer mais ne reflètent pas la dynamique d'une btq seconde main : les zones changent avec les saisons (vitrine été, manteau hiver, accessoires Noël).
- Pas de notion de **provenance produit** (lot d'arrivage, donneur si applicable, qualité d'origine).
- Pas de notion de **cycle de vie produit** au sens markdown (J+30, J+60, J+90, retour tri).
- L'idempotence du seed est bonne en dev mais ne dit rien du **vrai workflow d'arrivage** en production.

#### 2.2.3 Pratiques marché

Sur le secteur seconde main, les workflows attendus sont structurés autour de la **vitesse d'intake** car c'est le facteur n°1 de productivité. Circle-Hand permet à un membre du personnel d'entrer jusqu'à 90 articles par heure grâce à la saisie assistée et au pricing assisté. C'est l'étalon à viser.

| Capability | Vintiz | Circle-Hand | Ricochet | ThriftCart | Rose POS |
|------------|--------|-------------|----------|------------|----------|
| Création produit | Manuelle | AI-assistée 90/h | Manuelle/lots | Lots | Manuelle |
| Génération code-barres | ✅ Code 128 | ✅ | ✅ | ✅ | ✅ |
| Workflow arrivage / lot | ❌ | ✅ | ✅ | ✅ | ✅ |
| Cycle de vie + markdown auto | ❌ explicite | ✅ AI | ✅ couleur | ✅ couleur | ✅ |
| Retour centre tri | ❌ | — | ✅ consignor return | — | ✅ donor return |
| Photo IA → fiche pré-remplie | ✅ Claude Vision | ✅ | ❌ | ❌ | ❌ |
| Sell-through par catégorie | ❓ | ✅ | ✅ | ✅ | ✅ |
| Étiquettes lot | ❓ | ✅ | ✅ | ✅ | ✅ |

Vintiz a un **avantage différenciant fort** sur la photo IA → fiche pré-remplie (Claude Vision). C'est un atout marqué qui n'existe pas chez Ricochet/ThriftCart/Rose. À industrialiser.

#### 2.2.4 Gaps

| Gap | Impact | Sévérité |
|-----|--------|----------|
| Workflow arrivage centre de tri → btq | Pas d'idée de la vélocité d'arrivage | **Élevée** |
| Statut "retour centre de tri" | Pas de boucle bouclée pour invendus | **Élevée** |
| Étiquetage en lot (50 pièces d'un coup) | Productivité Sophie en intake | **Élevée** |
| Cycle de vie produit (J+30/J+60...) | Pré-requis du markdown engine | **Élevée** |
| Provenance / lot d'origine | Traçabilité ESS / DSP | Moyenne |
| Photo en vrac → produits multiples | Vitesse intake | Moyenne |
| Recherche par couleur/saison/coupe | Personal Shopper plafonne | Moyenne |

#### 2.2.5 Persona — Sophie (P-EMP-BTQ)

> "Lundi matin, j'ai 3 cartons qui arrivent du centre de tri. 120 pièces. Je dois les sortir, les vérifier, les étiqueter, les mettre en rayon. Si je dois cliquer 8 fois par pièce dans Vintiz, j'y suis encore mercredi. Et celles que je n'arrive pas à passer en caisse parce qu'elles n'ont pas trouvé preneur, qu'est-ce que je fais ? On les met dans un coin et on oublie ?"

#### 2.2.6 Préconisations

**P0 — fondamental**

1. **Schéma de cycle de vie produit explicite** :

```
RECEIVED → SORTED → TAGGED → DISPLAYED →
   ├── SOLD (terminal)
   ├── DONATED (terminal — geste commercial)
   ├── RETURNED_TO_SORTING (terminal côté btq, retour Solidarité Textiles)
   └── DISCOUNTED → DEEP_DISCOUNTED → DEEP_DISCOUNTED_2 → RETURNED_TO_SORTING
```

  Chaque transition génère un événement dans `events` (cf. section 5).

2. **Module Arrivage** : écran "Réception" avec photo carton, comptage, association à un `intake_batch_id`, attribution du lot à un employé pour responsabilité.

3. **Étiquetage en lot** : sélection multiple, génération d'une planche A4 d'étiquettes (PDF) à imprimer en bulk sur la Phomemo ou Brother.

**P1 — important**

4. **Photo "vrac" → fiche multiple** : prendre une photo d'un portant, Claude Vision 4.5 segmente et propose 8-12 fiches pré-remplies à valider une à une (gain × 5 sur l'intake).

5. **Provenance** : champ `intake_source` (centre de tri Rouen, dépôt-vente, don direct boutique) pour le reporting ESS et la conformité DSP.

6. **Recherche enrichie** : index sur `couleur dominante` (extraite par Vision), `saison cible`, `style` (chic, sport, décontracté, vintage), `coupe` (slim, droit, oversize). Pré-requis du Personal Shopper v2.

**P2**

7. **Recommandation de zonage automatique à l'étiquetage** : "Cette robe noire midi, on la met en zone A (vitrine femme habillée)". L'employée valide d'un tap.

#### 2.2.7 Ajustements UX

- **Vue Kanban produit** par statut (drag-and-drop entre `Reçu` / `Trié` / `Étiqueté` / `En rayon` / `Démarqué` / `À retourner`). Chaque colonne avec compteur en temps réel.
- **Scanner intake mode** : un grand bouton "Nouveau lot", caméra prend photo, défile les pièces une à une avec validation rapide.
- **Tableau de bord intake quotidien** : "Aujourd'hui, 47 pièces reçues, 32 étiquetées, 15 mises en rayon, panier moyen prévisionnel : 23€".
- **Alerte invendus** : "12 pièces en rayon depuis 60+ jours, voici le lot à retourner au centre de tri" (génère un bon de retour PDF avec inventaire).

---

### 2.3 — Outil de reporting et gestion d'une boutique Retail (1.c)

#### 2.3.1 Statut documentation

`CLAUDE.md` mentionne :

- KPIs journaliers (CA, panier moyen, nb transactions).
- Widget météo Vernon (OpenWeatherMap).
- Tickets cliquables → modal détail + reprint/email/SMS.
- Endpoint `/api/reports` avec dashboard et statistiques.

C'est **léger** par rapport aux attentes d'un manager retail.

#### 2.3.2 Pertinence du développement

**Forts :**

- Le widget météo est une excellente idée — la corrélation météo/trafic est documentée pour les btq physiques (un samedi pluvieux à Vernon = -30% de trafic). C'est un atout.
- Tickets cliquables avec reprint = bon UX réel d'employée.

**Faibles (par rapport au standard retail) :**

Les KPIs du brief retail moderne sont :

- **Sell-through rate (STR)** = pièces vendues / pièces reçues sur une période. C'est LE KPI seconde main.
- **GMROI** (Gross Margin Return On Inventory).
- **Inventory Turnover** (rotation).
- **Days on Hand** (DOH = âge moyen du stock).
- **Conversion rate** (visiteurs qui achètent — nécessite compteur de personnes).
- **Average Items per Transaction** (AIT = nb pièces / ticket).
- **CA / m² / mois** (sales per square meter).
- **CA / heure d'ouverture** (pour staffing).
- **Top 10 / Bottom 10 catégories** par STR.

Aucun de ces KPIs n'est explicitement documenté dans `CLAUDE.md`.

#### 2.3.3 Pratiques marché

| Reporting | Vintiz | Square POS | Shopify POS | Lightspeed Retail | KORONA |
|-----------|--------|------------|-------------|-------------------|--------|
| KPIs journaliers basiques | ✅ | ✅ | ✅ | ✅ | ✅ |
| Sell-through rate | ❓ | ✅ | ✅ | ✅ | ✅ |
| GMROI / Stock turnover | ❓ | Partiel | ✅ | ✅ | ✅ |
| Cohorte clients | ❓ | ✅ | ✅ | ✅ | Partiel |
| Heatmap horaire | ❓ | Partiel | ✅ | ✅ | ✅ |
| Météo / saisonnalité | ✅ unique | ❌ | ❌ | ❌ | ❌ |
| Export Excel/PDF rapport hebdo | ❓ | ✅ | ✅ | ✅ | ✅ |
| Reporting ESS (DSP, subventions) | ❌ | ❌ | ❌ | ❌ | ❌ |

#### 2.3.4 Gaps

| Gap | Impact | Sévérité |
|-----|--------|----------|
| Sell-through rate par catégorie | KPI n°1 de la seconde main | **Élevée** |
| GMROI | Décision stock/markdown | **Élevée** |
| Days on Hand par produit | Trigger du markdown auto | **Élevée** |
| Heatmap horaire / jour | Décision staffing | Moyenne |
| Cohorte clients (LTV, churn, RFM) | Marketing & fidélité | Moyenne |
| Reporting ESS (DSP, taux de réemploi) | **Spécifique Solidarité Textiles** | **Élevée** |
| Export PDF rapport hebdo automatisé | Codir / partenaires | Moyenne |
| Comparaison vs même semaine N-1 | Suivi tendance | Faible |

#### 2.3.5 Persona — Camille (P-MAN-RET)

> "Le lundi matin je veux savoir : combien on a vendu le week-end, dans quelles catégories, quels sont les invendus de plus de 30 jours, et est-ce que ça corrèle avec la météo. En 30 secondes, sur mon iPhone, dans le métro."

> "Et tous les trimestres, je dois sortir le rapport pour le rapport d'activité Solidarité Textiles : nombre de pièces vendues, nombre retournées au tri, taux de réemploi, CA par catégorie. Aujourd'hui je le fais à la main dans Excel."

#### 2.3.6 Préconisations

**P0**

1. **KPIs retail standard** : ajouter au dashboard `/admin/reports` :
   - Sell-through rate (sur 30/60/90j, par catégorie, par zone)
   - GMROI = (CA − coût d'acquisition) / valeur moyenne du stock
   - Days on Hand (DOH global et par produit)
   - AIT, CA/m²/mois
   - Variations vs N-1 et N-7

2. **Rapport hebdo automatisé** : génération Excel + PDF chaque lundi 6h, envoyé par email à Camille. Format codir clean.

3. **Reporting ESS dédié** : tableau "Mission ESS" avec :
   - Pièces reçues centre de tri / mois
   - Pièces vendues / pièces retournées au tri (taux de réemploi en btq)
   - Tonnage estimé (poids moyen × pièces)
   - CA reversé à Solidarité Textiles
   - Heures d'insertion réalisées (à connecter au futur ERP SOLIDATA)

**P1**

4. **Heatmap horaire** : matrice jours × heures avec CA par case → décision staffing.
5. **Cohortes RFM** clients (Récence, Fréquence, Montant) avec segmentation Bronze/Silver/Gold automatique.
6. **Comparateur** : sélecteur "S-1, M-1, A-1" pour comparer toute période.

**P2**

7. **Prévision IA** du CA week-end basée sur (météo Vernon + saison + jours fériés + historique). Claude Haiku 4.5 peut faire ça avec un prompt système bien rédigé. Précision attendue : ±15%.

#### 2.3.7 Ajustements UX

- **Mobile-first dashboard** : refonte de `/admin` avec un mode mobile premier (Camille consulte en déplacement). Cards compactes, swipe horizontal entre KPIs.
- **Widget météo enrichi** : météo J+1, J+2, J+3 avec indicateur visuel "trafic prévu" (ex : "Samedi pluvieux → -25% trafic estimé, prévoir 1 employée seulement").
- **Mode "Présentation Codir"** : bouton qui passe le dashboard en plein écran, polices grandes, parfait pour réunion équipe.
- **Push notifications stratégiques** : "12 pièces ont 60 jours, déclencher démarque ?", "CA hebdo +18% vs S-1, top catégorie : robes printanières".

---

### 2.4 — SEO du site vitrine et surveillance réseaux sociaux (1.d)

#### 2.4.1 Statut documentation

**Cette fonctionnalité n'est pas documentée dans `CLAUDE.md` ni dans `README.md`.** Le brief utilisateur la mentionne mais aucune trace côté code public.

C'est un **gap majeur** : la fonctionnalité est annoncée mais l'audit de la doc ne la trouve pas. Première action Claude Code : **vérifier dans le code source si elle existe** (chercher mots-clés `seo`, `social`, `instagram`, `facebook`, `monitoring`, `position`, `serp`).

#### 2.4.2 Pertinence du développement attendu

Pour une btq de centre-ville à Vernon, la stratégie SEO/RS pertinente est **locale** :

- SEO local (Google Business Profile, recherche "friperie Vernon", "seconde main Eure", "Frip & Co Vernon").
- Instagram + TikTok = canal n°1 pour Gen Z (Léa, P-CLI-DEC). Pas Facebook Ads en priorité.
- Google reviews count + rating.
- Visibilité sur Maps.

Un SEO national (positionnement vs Vinted/Vestiaire Collective) n'aurait pas de sens pour une btq physique mono-localisée. Ne pas surdimensionner.

#### 2.4.3 Pratiques marché

| Outil | Forces | Coût mensuel | Pertinence Vintiz |
|-------|--------|--------------|-------------------|
| **Google Search Console + Google Business Profile** | Officiel, gratuit, données fiables | 0€ | **Indispensable, baseline** |
| **Ahrefs / SEMrush** | Tracking SERP, backlinks, audit technique | 100-450€ | Surdimensionné pour mono-btq |
| **SE Ranking / Ubersuggest** | Plus accessibles | 30-90€ | Bon ratio |
| **Hootsuite / Later** | Programmation RS, monitoring | 30-50€ | Utile pour Insta/TikTok |
| **Brandwatch / Mention** | Monitoring de marque | 80-300€ | Si volume RS le justifie |

Pour Vintiz, je recommande de **construire un module léger** plutôt que d'intégrer un outil tiers payant : Google Search Console API (gratuite) + Instagram Graph API + scraping doux Google Maps + alertes Mention via RSS.

#### 2.4.4 Gaps

| Gap | Impact | Sévérité |
|-----|--------|----------|
| Module SEO local complet | Acquisition trafic web | **Élevée** (annoncé brief) |
| Tracking position SERP "friperie Vernon" + variantes | Suivi visibilité | **Élevée** |
| Monitoring mentions Insta/TikTok | Veille e-réputation | Moyenne |
| Sentiment analysis avis Google | E-réputation | Moyenne |
| Calendrier éditorial RS | Aide planning publication | Moyenne |
| Alertes pic positif/négatif | Réactivité | Faible |

#### 2.4.5 Persona — Camille (P-MAN-RET)

> "Je veux savoir : 1) est-ce que quand on tape 'friperie Vernon' sur Google, on apparaît, et où. 2) Est-ce qu'on a eu des avis cette semaine, positifs ou négatifs, et lesquels. 3) Combien de mentions Insta avec #fripandco ce mois-ci, et est-ce qu'il y en a une que je devrais reposter. Je n'ai pas le temps d'ouvrir 5 outils."

#### 2.4.6 Préconisations

**P1 (cette feature n'est pas un bloquant pour l'ouverture mais elle a été promise au brief)**

1. **Module `/admin/visibility`** avec 3 onglets :
   - **SEO local** : intégration Google Search Console API (OAuth), tracking de 10 mots-clés locaux ("friperie Vernon", "vintage Vernon", "Frip & Co", "seconde main Eure"...), historique 90 jours, alerte si recul de >5 positions.
   - **Réseaux sociaux** : intégration Instagram Graph API + monitoring TikTok via search hashtag (avec rate-limit). Affichage des derniers posts, engagement rate, mentions de la btq.
   - **Avis** : Google Business Profile API → liste avis, moyenne, alerte si avis < 3 étoiles, suggestion de réponse via Claude.

2. **Calendrier éditorial RS** intégré : Claude Haiku 4.5 génère 4 propositions de posts par semaine (1 produit star, 1 valeur ESS, 1 témoignage cliente, 1 actu locale Vernon), Camille sélectionne et édite, programmation via Buffer/Later API ou export pour Meta Business Suite.

3. **IA "réponse aux avis"** : pour chaque nouvel avis Google, proposition automatique d'une réponse personnalisée par Claude (ton chaleureux, valeurs Frip & Co, signature Camille). Validation 1-clic.

#### 2.4.7 Ajustements UX

- **Mini-widget visibilité** sur le dashboard principal : "Position 'friperie Vernon' : #2 (▲1)" + badge alerte si avis négatif.
- **Mobile** : version SMS/email avec digest hebdo "Cette semaine : +3 mentions Insta, 2 nouveaux avis (1× 5★, 1× 4★), position SERP stable."

---

### 2.5 — CRM Client + carte de fidélité + historique de ventes (1.e)

#### 2.5.1 Statut documentation

Documenté dans `CLAUDE.md` :

- Lookup client par email : `GET /api/crm/clients/lookup?email=…`.
- Personal shopper public : `GET /api/crm/clients/personal-shopper?email=…`.
- Espace client site public : login email (sans mot de passe), carte fidélité Bronze/Silver/Gold, historique achats, Personal Shopper IA.
- Affichage points et toggle rachat en POS (1 pt = 0,10€, max 50% panier).
- Endpoints CRM `/api/crm/`.

#### 2.5.2 Pertinence du développement

**Forts :**

- Login email-only (magic link probable) = excellente UX pour la cible (50% des clientes ont 35-65 ans et oublient leurs mots de passe).
- 3 tiers Bronze/Silver/Gold = simple, lisible, classique mais efficace.
- Personal Shopper sur l'espace client = différenciant (cf. section 4 dédiée).

**Points à creuser :**

- **Pas de RGPD-by-design explicite** dans la doc : consentement, droit à l'oubli, export portable, durée de conservation. Indispensable légalement et déjà identifié dans tes audits passés (le module "audit RGPD IA" via persona juridique existe en API mais ce n'est pas le RGPD du CRM lui-même).
- Pas de **mécanique d'engagement** au-delà du cumul de points : pas de challenges, pas de "double points le mardi", pas de parrainage, pas de carte virtuelle Apple/Google Wallet.
- Pas de **segmentation marketing** documentée : qui sont les Gold inactives depuis 60 jours ?
- Pas de **canal de communication CRM** : email automation (Mailchimp/Brevo), SMS marketing, push web.

#### 2.5.3 Pratiques marché

| Capability | Vintiz | Square Loyalty | Shopify+SmileLoyalty | Sephora Beauty Insider |
|-----------|--------|----------------|----------------------|------------------------|
| Tiers Bronze/Silver/Gold | ✅ | ✅ | ✅ | ✅ (4 tiers) |
| Cumul points achats | ✅ | ✅ | ✅ | ✅ |
| Rachat points caisse | ✅ | ✅ | ✅ | ✅ |
| Carte virtuelle Wallet | ❌ | ✅ | ✅ | ✅ |
| Parrainage | ❌ | ✅ | ✅ | ✅ |
| Bonus points évènementiels | ❌ | ✅ | ✅ | ✅ |
| Triggers comportementaux | ❌ | Partiel | ✅ | ✅ |
| Birthday reward | ❌ | ✅ | ✅ | ✅ |
| Personal Shopper IA | ✅ unique ! | ❌ | ❌ | ✅ partiel |
| Emails automation | ❌ | Partiel | ✅ | ✅ |
| RGPD-by-design | ❓ | ✅ | ✅ | ✅ |

Vintiz a un **vrai point fort** sur le Personal Shopper IA. À garder et renforcer (section 4).

#### 2.5.4 Gaps

| Gap | Impact | Sévérité |
|-----|--------|----------|
| RGPD-by-design CRM (consentement, droit à l'oubli, export) | Bloquant légal | **Bloquante** |
| Carte virtuelle Apple/Google Wallet | UX perçue, friction | Moyenne |
| Parrainage cliente | Acquisition organique | Élevée |
| Bonus points évènementiels (anniversaire, jour de la semaine) | Engagement | Moyenne |
| Triggers email/SMS comportementaux | Réactivation Gold inactives | **Élevée** |
| Segmentation RFM | Targeting marketing | Moyenne |
| Email/SMS automation centralisée | Outil quotidien manager | Moyenne |

#### 2.5.5 Persona — Julie (P-CLI-FID)

> "Je suis Gold mais je l'avais oublié. La dernière fois que je suis venue, Sophie m'a dit 'tu as 12€ de bons d'achat'. Cool, mais j'aurais aimé un SMS avant. Et l'autre jour pour mon anniversaire, rien. Je vais chez Sezane parce qu'eux ils me souhaitent et m'offrent un cadeau."

> "Et la copine que je veux faire venir, je n'ai pas de moyen simple de l'inviter avec un avantage."

#### 2.5.6 Préconisations

**P0**

1. **RGPD-by-design** : consentement explicite à l'inscription, table `consents` versionnée, écran "Mes données" dans l'espace client (export JSON, suppression compte avec délai 30j de réversibilité), CGU + politique de confidentialité accessibles, mention "données conservées 5 ans après dernière transaction".

2. **Triggers comportementaux** (Brevo ou simple cron + SMTP/Twilio existant) :
   - J+1 après inscription : email de bienvenue avec valeurs Frip & Co.
   - J+30 sans visite (Silver/Gold) : email "On vous a réservé 5 pièces qui vous correspondent" → lien vers Personal Shopper.
   - Anniversaire : SMS "Joyeux anniversaire Julie ! 5€ offerts en boutique cette semaine".
   - J+60 sans visite (Gold) : appel manuel suggéré dans le dashboard.

3. **Parrainage** : code unique cliente + landing page dédiée + 5€ pour parrain et filleul à la 1ère visite filleul.

**P1**

4. **Apple Wallet / Google Wallet** : génération `.pkpass` côté API avec QR code points. <br>Export du solde de points et tier en temps réel.

5. **Segmentation marketing** : moteur RFM (Récence Fréquence Montant) côté `/admin/crm` avec listes dynamiques exportables vers Brevo/Mailchimp.

6. **Email automation centralisée** : intégration Brevo (gratuit jusqu'à 300 emails/jour, suffit pour Vernon), templates configurables par Camille.

**P2**

7. **Birthday reward** + bonus points évènementiels (mardi seconde main = points × 2, journée mode durable, etc.).

8. **Push notifications PWA** sur l'espace client (déjà PWA-compatible si Next.js bien configuré) pour annoncer arrivages et démarques.

#### 2.5.7 Ajustements UX

- **Espace client** : page d'accueil avec les 3 informations clés en grand : "Vous êtes Gold", "Solde : 23 points (= 2,30€)", "Prochain niveau : 12 visites de plus pour Platinum (à créer ?)". Hiérarchie visuelle forte.
- **POS** : quand Sophie tape l'email cliente, afficher en plus du nom + points : *"Gold inactive depuis 47 jours, derniers achats : robes mi-saison. Suggestions personnal shopper en stock : voir QR"*. Sophie peut lui en parler tout de suite.
- **Site vitrine** : CTA "Inviter une amie, gagnez 5€ chacune" en sticky footer pour les connectées.

---

## 3. Audit fonctionnel — Site vitrine (Périmètre 2)

### 3.1 — Site public (2.a)

#### 3.1.1 Statut documentation

`README.md` mentionne `apps/site/` (Next.js 14) comme "site vitrine public + espace client" sur port 3001. `CLAUDE.md` indique "Espace client (site public)" avec login email, carte fidélité, historique, Personal Shopper IA. Le mockup d'accueil est dans le repo (`Mockup page d'accueil Vintiz (1).pdf`).

**Le site vitrine "informations standards d'une boutique de centre ville" n'est pas explicitement détaillé** : pages adresse / horaires / accès / mentions légales / contact / présentation Frip & Co et Solidarité Textiles.

#### 3.1.2 Pertinence du développement

**Forts :**

- Next.js 14 App Router = SSR + SEO friendly nativement.
- Domaine séparé du backoffice = bonne pratique.
- Couplé à l'espace client = cohérent (le client peut basculer site → connexion → Personal Shopper sans changer d'app).

**Points à creuser :**

- **Schema.org / JSON-LD** pour `LocalBusiness` (cf. SEO local). À vérifier dans le code.
- **Open Graph + Twitter Cards** sur chaque page produit affichée pour partage RS.
- **Performance** : Next.js bien configuré peut atteindre 95+ Lighthouse — à vérifier.
- **Accessibilité (WCAG AA)** : non documentée.
- **Multi-langue** : le brief ne le demande pas explicitement, mais Vernon est touristique, anglais probable utile.

#### 3.1.3 Pratiques marché

Pour un site vitrine de btq centre-ville, les blocs attendus sont :

1. Hero avec photo emblématique + USP + CTA "Visiter la boutique" + horaires en gros.
2. Carrousel de 6-12 produits stars du moment.
3. Section "Nos valeurs" (ESS, circularité, Solidarité Textiles, insertion).
4. Section "Visiter la boutique" : carte Google + adresse + horaires détaillés + photos boutique.
5. Section "Carte de fidélité" : explication + CTA inscription.
6. Section "Personal Shopper" : explication + CTA inscription si carte fidélité.
7. Footer : mentions légales, RGPD, CGU, contact, RS.

#### 3.1.4 Gaps

| Gap | Impact | Sévérité |
|-----|--------|----------|
| Schema.org LocalBusiness | SEO local | **Élevée** |
| Open Graph par produit | Partage RS | Moyenne |
| WCAG AA accessibilité | Légal + inclusif | Moyenne |
| Page "Notre histoire / ESS" | Différenciation | Moyenne |
| Multi-langue FR/EN | Touristes Vernon | Faible |
| Newsletter signup | Acquisition email | Moyenne |

#### 3.1.5 Préconisations

**P0**

1. **Schema.org JSON-LD `LocalBusiness`** sur la home + `Product` sur chaque page produit.
2. **OpenGraph + Twitter Cards** sur toutes les pages.
3. **Lighthouse audit** complet : viser 90+ partout (Performance, Accessibilité, SEO, Best Practices).

**P1**

4. **Page "Notre histoire"** : Solidarité Textiles, mission ESS, insertion, parcours d'une pièce de la collecte à la btq. Excellent pour le SEO local et l'attachement à la marque.
5. **Newsletter signup** + double opt-in conforme RGPD, intégration Brevo.
6. **WCAG AA** : audit avec axe-core, corrections, commit dédié.

**P2**

7. **i18n FR/EN** via `next-intl`, traduction des pages clés.

#### 3.1.6 Ajustements UX

- **Hero adaptatif** : la photo de hero change selon la météo Vernon (soleil → photo extérieur boutique, pluie → intérieur cosy).
- **Sticky bar** : "Aujourd'hui ouvert jusqu'à 19h" en barre rose discrète en haut, masquée en mode connecté.
- **Bandeau ESS** discret (1 ligne) "Achat solidaire — 5% reversés à Solidarité Textiles" pour ancrer la mission.

---

### 3.2 — Démonstration de produits (2.b)

#### 3.2.1 Statut documentation

Pas de détail explicite dans `CLAUDE.md` sur la **sélection** de produits affichée publiquement (combien, quels critères, mise à jour, limitations).

Question critique : **est-ce un mini-catalogue e-commerce, ou juste un teaser non transactionnel ?** Le brief dit "Démonstration d'une sélection de produit" — j'interprète comme "teaser non transactionnel" : on montre des pièces pour donner envie de venir en btq, pas pour vendre en ligne. C'est cohérent avec le format btq physique mono-localisée.

#### 3.2.2 Pertinence du développement

Si c'est un teaser non transactionnel :

- Pas de panier, pas de paiement en ligne, pas de logistique. Bon choix structurel.
- Donne envie de visiter la btq.
- Bénéfice SEO (chaque produit = page indexée → long tail trafic).
- Protection contre l'achat en ligne par bot/réservation : pas applicable.

#### 3.2.3 Pratiques marché

Les btq seconde main qui ont un site vitrine non-transactionnel font :

- 30-100 produits stars en rotation hebdomadaire.
- Galerie photos pro de la pièce.
- Description courte avec mensurations.
- Indication "disponible en boutique" ou "réservée".
- Optionnel : "Réserver pour essayer" avec deadline 48h.

Le mécanisme **réservation** est très différenciant côté seconde main (Vinted-style sans achat) : la cliente Léa voit une pièce sur le site, clique "Je viens l'essayer demain", reçoit un SMS de confirmation, la pièce reste 48h dans une zone "Réservé" en btq.

#### 3.2.4 Gaps

| Gap | Impact | Sévérité |
|-----|--------|----------|
| Mécanisme de réservation 48h | Différenciation, conversion online→btq | **Élevée** |
| Filtres produits (taille, couleur, prix, catégorie) | UX standard | Moyenne |
| Wishlist cliente fidèle | Engagement | Moyenne |
| Notification arrivage | Différenciation | Moyenne |

#### 3.2.5 Persona — Léa (P-CLI-DEC)

> "J'ai vu sur l'Insta de Frip & Co une jolie veste en daim. Je vais sur le site, je clique, c'est marqué 'disponible en boutique'. Je suis à Évreux, je fais 30 minutes de route, j'arrive : la veste a été vendue à midi. Frustration max. Si j'avais pu la 'réserver' jusqu'à demain 18h pour m'assurer qu'elle est encore là quand j'arrive, je serais venue contente."

#### 3.2.6 Préconisations

**P1**

1. **Mécanisme de réservation 48h** : 
   - Bouton "Réserver pour essayer en boutique" sur fiche produit.
   - Limite 2 réservations actives par cliente fidèle (3 pour Gold).
   - SMS de confirmation + rappel J+1.
   - Côté btq : zone physique "Réservés" + écran POS qui affiche "Cette pièce est réservée par Léa Martin, expire dans 27h".
   - Si non récupérée : remise en rayon + notification cliente "Plus de chance la prochaine fois !".

2. **Filtres** classiques : catégorie, taille, couleur, prix, état (excellent/très bon/bon).

**P2**

3. **Wishlist cliente fidèle** : favoris persistants. À l'arrivage d'une pièce similaire (même catégorie + taille + couleur dominante), notification.

4. **Notification arrivage** : la cliente Gold s'abonne à "robes T36 noires" → email/push à chaque nouvel arrivage matchant. Signal de qualité fort.

#### 3.2.7 Ajustements UX

- **Tag "Réservée 27h"** visible sur la fiche produit du site, désactive le bouton.
- **Compteur "5 pièces vues à l'instant"** (si data réelle, sinon ne pas mettre — ne JAMAIS mentir).
- **Filtre "Nouveau cette semaine"** par défaut sur la home produit.

---

## 4. Audit approfondi — Personal Shopper IA (Périmètre 3)

> **Cette section est un deep-dive demandé par Julien.** C'est l'un des deux marqueurs de différenciation forts de Vintiz vs. concurrents (avec l'AI Booster).

### 4.1 Vision

Le Personal Shopper IA pour cliente fidèle a deux promesses :

1. **Historise les achats** — c'est la base, opérationnel dès qu'il y a une transaction CRM-liée.
2. **Propose des produits** *en stock à l'instant T*, basés sur l'historique d'achats de la cliente, pour transformer l'arrivage en btq en opportunité personnalisée.

Promesse implicite supplémentaire : **donner envie à la cliente de venir essayer sans frustration**, en l'assurant qu'il y a 3-5 pièces qui *vont lui plaire* (signal de qualité de l'expérience btq).

### 4.2 État actuel (lu dans la doc)

`CLAUDE.md` indique :

- Endpoint `GET /api/crm/clients/personal-shopper?email=…`.
- "Personal Shopper IA : sélection personnalisée basée sur l'historique" (espace client).

**Ce que la doc ne dit pas (à creuser dans le code) :**

- Quel modèle de recommandation : règles `if-then`, scoring statistique, embeddings sémantiques, LLM appelé en runtime, modèle entraîné maison ?
- Quelles features de recommandation : catégorie, taille, couleur, marque, style, prix moyen, saisonnalité, embeddings visuels ?
- Comment est gérée la **pertinence** : on suggère une robe taille 38 si la cliente n'a acheté que des T36 ? On suggère une marque jamais achetée mais visuellement similaire ?
- Comment est gérée la **diversité** : on suggère 5 robes ou 1 robe + 1 sac + 1 paire de chaussures ?

C'est l'angle mort le plus important du repo : **un Personal Shopper sans documentation explicite de son moteur est un Personal Shopper qui plafonne**.

### 4.3 Pratiques marché

Les moteurs de recommandation seconde main / fashion en 2026 utilisent :

| Approche | Description | Outils typiques |
|----------|-------------|-----------------|
| **Filtrage collaboratif** | "Les clientes qui ont acheté X ont aussi aimé Y" | Implicit (Spotify open-source), TensorFlow Recommenders |
| **Filtrage basé contenu** | Match sur attributs produit (catégorie, couleur, taille) | scikit-learn, règles SQL |
| **Embeddings visuels** | CNN extrait un vecteur image, similarité cosinus | CLIP (OpenAI), Pixyle, Algolia AI |
| **Hybrid (state-of-art)** | Combine collaboratif + contenu + visuel | Algolia Recommend, AWS Personalize |
| **LLM en runtime** | Claude/GPT lit profil cliente + catalogue, propose | Claude API + RAG vectoriel |
| **Conversationnel** | Stylist chatbot ("je cherche une robe d'été") | LangChain + Claude/GPT |

Pour Vintiz, l'approche réaliste à court terme + différenciante est un **hybride : filtrage par contenu + embeddings visuels + LLM pour la "proposition stylée" en langage naturel**. C'est faisable avec Claude Haiku 4.5 (déjà intégré) + un modèle d'embedding vision (CLIP open-source ou Anthropic vision-as-feature).

#### Comparaison fonctionnelle

| Capability | Vintiz (lu doc) | Pixyle (vintage) | Algolia Recommend | Refabric |
|-----------|-----------------|------------------|-------------------|----------|
| Reco basée historique | ✅ | ✅ | ✅ | ✅ |
| Reco visuelle (image-to-image) | ❓ | ✅ | ✅ | ✅ |
| Reco sémantique (texte → produits) | ❓ | ✅ | ✅ | ✅ |
| Diversification | ❓ | ✅ | ✅ | ✅ |
| Cold start (cliente sans historique) | ❓ | ✅ | Partiel | ✅ |
| Stylist chatbot | ❓ | ❌ | ❌ | ✅ |
| Synthèse stylée en langage naturel | ❓ | ❌ | ❌ | ✅ |
| Filtre stock real-time | ✅ implicite | Partiel | ✅ | ✅ |

### 4.4 Gaps

| Gap | Impact | Sévérité |
|-----|--------|----------|
| Documentation interne du moteur | Maintenabilité, évolution | **Élevée** |
| Embeddings visuels CLIP/Anthropic | Reco "visuellement proche" | **Élevée** |
| Cold start cliente sans historique | UX 1ère visite | **Élevée** |
| Diversification (catégorie, prix, marque) | Évite la monotonie | Moyenne |
| Synthèse en langage naturel | Différenciation forte | **Élevée** |
| Filtres taille/couleur explicites | Pertinence forte | Moyenne |
| Stylist chatbot | Engagement | Moyenne |

### 4.5 Persona — Julie (P-CLI-FID)

> "L'autre fois Vintiz m'a proposé 5 robes mais 4 sur 5 étaient en T38 alors que je fais du T36. Et la 5ème, en T36, c'était une robe à fleurs alors que je ne mets *jamais* de fleurs. Soit le système ne sait pas ce que je porte, soit il prend mes 'achats' au pied de la lettre — mais j'avais acheté la robe à fleurs pour ma sœur, pas pour moi."

> "Ce que j'aimerais ? Que Vintiz me dise '*Cette semaine, on a reçu 12 pièces qui te ressemblent. On t'en a sélectionné 4 : 2 hauts noirs en T36 (tu en as 6 dans ton placard et tu les portes), 1 jean droit (tu as racheté ce style 2 fois), 1 sac structuré (tu en as un similaire que tu portes tout l'été). Viens essayer mardi entre 10h et 19h.*'. Là je viens. Là je suis fan."

### 4.6 Architecture technique recommandée

Voici la structure proposée pour un Personal Shopper v2 robuste, exploitable par Claude Code.

#### 4.6.1 Schéma de données

Tables nouvelles ou enrichies :

```sql
-- Profil enrichi cliente
ALTER TABLE customers ADD COLUMN preferred_sizes JSONB;
ALTER TABLE customers ADD COLUMN preferred_colors JSONB;
ALTER TABLE customers ADD COLUMN avoided_categories JSONB;
ALTER TABLE customers ADD COLUMN style_keywords TEXT[]; -- "minimaliste", "vintage", "boho"
ALTER TABLE customers ADD COLUMN lifestyle_tags TEXT[]; -- "bureau", "weekend", "soirée"
ALTER TABLE customers ADD COLUMN budget_avg_per_visit NUMERIC;

-- Embeddings produit (vectoriel)
CREATE TABLE product_embeddings (
  product_id INT PRIMARY KEY REFERENCES products(id),
  visual_embedding VECTOR(512),  -- CLIP-like
  text_embedding VECTOR(512),    -- description sémantique
  computed_at TIMESTAMP
);

-- Embeddings cliente (centroïde pondéré de ses achats)
CREATE TABLE customer_taste_profiles (
  customer_id INT PRIMARY KEY REFERENCES customers(id),
  visual_centroid VECTOR(512),
  text_centroid VECTOR(512),
  computed_at TIMESTAMP,
  n_purchases_analyzed INT
);

-- Événements pour le futur entraînement
CREATE TABLE events (
  id BIGSERIAL PRIMARY KEY,
  occurred_at TIMESTAMP NOT NULL,
  customer_id INT REFERENCES customers(id),
  product_id INT REFERENCES products(id),
  event_type TEXT NOT NULL, -- viewed, tried, sold, refunded, recommended, dismissed
  metadata JSONB,
  session_id UUID
);
CREATE INDEX idx_events_customer_time ON events(customer_id, occurred_at DESC);
CREATE INDEX idx_events_product_time ON events(product_id, occurred_at DESC);
```

Suggestion : utiliser **PostgreSQL 16 + pgvector** (extension officielle, déjà supportée par Postgres 16 du Docker Compose actuel). Évite d'introduire une stack supplémentaire (Pinecone/Weaviate). Pgvector tient parfaitement sur des catalogues de quelques milliers de produits.

#### 4.6.2 Pipeline de recommandation (5 étapes)

```
[Trigger : cliente loggée OU email saisi à la caisse]
    ↓
1. Charger customer_taste_profile (centroïdes)
    ↓
2. Filtrer products WHERE statut = DISPLAYED AND taille IN preferred_sizes
    ↓
3. Calculer similarité cosinus visual + text avec centroïdes cliente
    ↓
4. Diversifier : prendre top 1 par catégorie (max 5 catégories)
    ↓
5. Demander à Claude Haiku 4.5 de rédiger 2-3 phrases stylées
   "Voici 4 pièces qui te correspondent : ..."
    ↓
6. Logger dans events (event_type = recommended)
```

#### 4.6.3 Cold start (cliente sans historique)

- Demander à l'inscription : 5 photos de tenues qu'elle aime (Pinterest-style picker).
- Calculer un visual_centroid initial à partir de ces 5 images.
- Compléter avec un quiz court : "Quel style ? Minimaliste / Vintage / Boho / Chic / Sport".
- Cold start UX **doit prendre moins de 2 minutes**.

### 4.7 Préconisations

**P0**

1. **Schéma DB** : créer `events`, `product_embeddings`, `customer_taste_profiles`, enrichir `customers` (script de migration Alembic).

2. **Pipeline d'embedding** :
   - Job batch quotidien qui calcule `product_embeddings` pour tout produit nouveau (Claude Vision API + un encoder texte de la description).
   - Job hebdo qui recalcule `customer_taste_profiles` pour tous les clients ayant eu activité.

3. **Documenter le moteur** dans `docs/PERSONAL_SHOPPER.md` (à créer si non existant) — schémas, prompts, seuils.

**P1**

4. **Cold start** : onboarding cliente avec quiz + 5 photos style.

5. **Stylist textuel par Claude** : prompt système (cf. section 6 du rapport) qui transforme `[liste de 4 produits]` en "Voici une sélection que je trouve toi : ..." avec ton chaleureux et personnalisé.

**P2**

6. **Stylist conversationnel** : chatbot sur l'espace client, "Je cherche une tenue pour un mariage en juin", recherche RAG vectorielle dans le stock.

7. **A/B testing** : exposer 50% des clientes au moteur "v1 (règles)" et 50% au "v2 (embeddings)" pendant 4 semaines, mesurer taux de visite + panier moyen.

### 4.8 Ajustements UX

- **Espace client - section "Pour vous cette semaine"** : 4 cards produits avec photo + court argumentaire stylé (généré par Claude). CTA "Je viens essayer ces pièces" qui propose un créneau.
- **POS - lookup cliente** : afficher sous le nom client les "3 pièces réservées sympa pour elle" pour que Sophie puisse en parler tout de suite.
- **Mobile** : push notification "5 nouvelles pièces sélectionnées rien que pour toi cette semaine — vues d'ici 24h ?".

---

## 5. Audit approfondi — AI Booster (Périmètre Boutique)

> **Deuxième deep-dive demandé par Julien.** L'AI Booster vise à transformer la btq en machine de vente intelligente : mapping (où placer chaque pièce), rating (à quel point une pièce va se vendre), pricing (à quel prix et quelle dynamique de démarque).

### 5.1 Vision

Trois sous-modules :

- **5.a Mapping btq** : optimiser l'emplacement de chaque vêtement, structurer la vitrine, retrouver une pièce.
- **5.b Rating produit** : score d'attrait (tendance saisonnière + tendance seconde main + tendance historique btq).
- **5.c Politique prix / promo / démarque** : pricing dynamique en fonction du rating et de l'ancienneté.

### 5.2 État actuel (lu dans la doc)

`CLAUDE.md` mentionne :

- 7 zones prédéfinies pour le plan boutique (98m²).
- Édition zone : nom, description, capacité, types de produits, couleur.
- Score automatique "6 composantes, automation 1er mercredi".
- Endpoints `/api/ai/...` pour analyse photo, checklist, tendances, persona marketing/juridique.
- "Moteur prédictif" mentionné avec doc séparée `docs/PREDICTIVE_ENGINE.md` (non accessible publiquement).

**Ce que la doc ne dit pas explicitement :**

- Comment les **6 composantes du score** sont calculées (formule, pondération, source de données par composante).
- Comment le score se traduit en **placement** (zone A vs B vs vitrine).
- Comment le score se traduit en **prix** (markdown engine, paliers, déclencheurs).
- Si le mapping est **dynamique** (mise à jour quotidienne ou hebdo) ou **statique** (zones figées).

### 5.3 Les 6 composantes du score — hypothèse à valider

D'après le brief utilisateur (rating = tendance saisonnière + tendance seconde main + tendance historique btq), je propose une décomposition explicite (Claude Code à valider/corriger contre l'existant) :

| # | Composante | Source de donnée | Pondération suggérée |
|---|-----------|------------------|----------------------|
| 1 | **Tendance saisonnière** | Saison courante × catégorie produit (manteau en hiver = +) | 20% |
| 2 | **Tendance seconde main** | Sources Vinted, Vestiaire Collective, Imparfaite (search trends marque/style) | 20% |
| 3 | **Tendance historique btq** | Sell-through rate des 90 derniers jours par catégorie/marque | 25% |
| 4 | **Qualité visuelle / état** | Score Vision sur photos (état apparent, qualité tissu) | 10% |
| 5 | **Désirabilité marque** | Note de la marque (Le Tanneur > Promod > Kiabi) | 15% |
| 6 | **Singularité (uniqueness)** | Si pièce vintage rare ou pièce courante | 10% |

Total = 100%. Score sortie : 0-100. Bucket : Hot ≥75, Warm 50-74, Slow 25-49, Cold <25.

### 5.4 Mapping boutique — pratiques marché

| Capability | Vintiz (lu doc) | LEAFIO AI | PlanoHero | Visulon | One Door |
|-----------|-----------------|-----------|-----------|---------|----------|
| Plan boutique 2D | ✅ 7 zones | ✅ | ✅ DXF | ✅ 3D | ✅ |
| Zones avec capacité | ✅ | ✅ | ✅ | ✅ | ✅ |
| Heatmap fréquentation | ❌ | ✅ | ✅ | ❌ | ✅ |
| Reco placement par AI | ❌ | ✅ | ✅ AI queries | ✅ | ✅ |
| Compliance photo (vérif déploiement) | ❌ | ✅ | ✅ | ❌ | ✅ |
| Vitrine spécifique | ❌ explicite | ✅ | ✅ | ✅ | ✅ |
| Mise à jour dynamique stock | ❓ | ✅ | ✅ | ❌ | ✅ |

Vintiz part avec un socle (7 zones) mais sans **moteur dynamique** : pas de calcul "cette robe Hot doit aller en zone vitrine ou tête de gondole", pas de heatmap (sans capteurs IoT, on peut simuler avec un comptage manuel hebdo ou via les ventes par zone).

### 5.5 Markdown engine (politique de prix) — pratiques marché

| Approche | Description | Exemple acteur |
|----------|-------------|----------------|
| **Tag couleur / semaine** | Étiquette rouge S+0, jaune S+4, verte S+8, bleue S+12 → -20%/-40%/-60% | Goodwill, ThriftCart, Rose POS |
| **Markdown progressif** | -10% J+30, -20% J+60, -40% J+90, retour tri J+120 | KORONA |
| **Markdown dynamique IA** | Algorithme qui ajuste prix en temps réel selon demande, stock, élasticité | Zalando, ABOUT YOU, Boohoo, 7Learnings |
| **Markdown hybride** | Règles de base + ajustement IA pour les pièces "limites" | Conscient + AI |

Pour Vintiz, **l'hybride est le plus réaliste** : règles simples lisibles par Sophie + couche IA pour optimiser.

Architecture suggérée :

```
[Score produit]   [Âge en btq]
       \            /
        →  Markdown engine  ←  [Stock zone disponible]
                ↓
      [Action quotidienne batch]
                ↓
   ┌────────────┼────────────┐
   ↓            ↓            ↓
[Maintien] [Démarque -X%] [Retour tri]
```

### 5.6 Gaps

| Gap | Impact | Sévérité |
|-----|--------|----------|
| Documentation explicite des 6 composantes | Maintenabilité | **Élevée** |
| Reco placement automatique par AI | Productivité Sophie | **Élevée** |
| Heatmap fréquentation (proxy via ventes par zone) | Optimisation merchandising | **Élevée** |
| Vitrine = sous-zone spéciale avec règles | Différenciation | Moyenne |
| Markdown engine déclaratif (config en base) | Adaptabilité Camille | **Élevée** |
| Tag couleur physique sur étiquette | Comprénension cliente | Moyenne |
| Compliance photo vitrine | Vérif planning | Faible |
| Vue mobile "Où est cette pièce ?" | Productivité Sophie | Moyenne |

### 5.7 Personas

#### Sophie (P-EMP-BTQ)

> "Une cliente me demande 'tu as encore ce trench beige que j'ai vu sur Insta ?'. Je sais pas. Je tape dans Vintiz, je vois qu'on l'a, mais où ? Si on me dit 'Zone B-Rack-Hommes-Mi-saison', j'y vais en 30 secondes. Si on me dit pas, je perds 5 minutes à chercher dans toute la btq."

> "Le mardi matin je dois changer la vitrine. J'aimerais un truc qui me dit '6 pièces à mettre en vitrine cette semaine, voici lesquelles : 2 robes Hot, 1 jean Warm, 2 sacs, 1 accessoire de saison'. Là je gagne 1h."

#### Camille (P-MAN-RET)

> "Je veux une politique de prix qui tienne dans une page : 'On démarque -20% à J+30 sauf marques top, -40% à J+60, on retourne au tri à J+90 sauf vintage rare'. Et je veux pouvoir ajuster ces seuils selon la saison sans demander à un développeur."

### 5.8 Préconisations

#### 5.8.1 Mapping btq (5.a)

**P0**

1. **Modèle données zones enrichi** :

```sql
ALTER TABLE zones ADD COLUMN is_window BOOLEAN DEFAULT FALSE; -- vitrine
ALTER TABLE zones ADD COLUMN visibility_score INT DEFAULT 50; -- 0-100, vitrine = 100
ALTER TABLE zones ADD COLUMN target_score_min INT; -- score min des produits qu'on y met
ALTER TABLE zones ADD COLUMN target_score_max INT;
ALTER TABLE zones ADD COLUMN seasonal_focus TEXT[]; -- ["printemps", "été"]
```

2. **Reco placement automatique** : à l'étiquetage d'un nouveau produit, l'API renvoie zone suggérée :
   - Si score Hot (≥75) ET stock vitrine pas saturé → zone vitrine.
   - Sinon zone correspondant à la catégorie/saison.

3. **Vue "Plan boutique"** dans `/admin/store-plan` : SVG du plan avec densité de produits par zone (couleur de remplissage), survol affiche le détail.

**P1**

4. **Heatmap proxy** : pour chaque zone, calculer le **taux de rotation** (pièces vendues sur la zone / pièces qui ont transité par la zone) sur 30 jours. Affichage en heatmap couleur.

5. **Recommandation vitrine hebdomadaire** : tous les lundis 6h, Claude Haiku 4.5 propose 6-8 pièces pour la vitrine de la semaine, basées sur (score + nouveauté + saisonnalité + diversité catégorie). Sophie valide d'un tap.

6. **Recherche "Où est cette pièce ?"** : scan code-barres ou recherche, affichage immédiat de la zone exacte + statut (en rayon / réservée / cabine / caisse).

**P2**

7. **Compliance vitrine** : photo hebdo de la vitrine après changement, Claude Vision compare au plan recommandé, score de conformité.

#### 5.8.2 Rating (5.b)

**P0**

1. **Documenter explicitement les 6 composantes** dans `docs/SCORING_ENGINE.md` (à créer ou mettre à jour). Pour chaque composante : source, formule, fenêtre temporelle, pondération.

2. **Table `scoring_config`** : pondérations stockées en base (pas en code), éditables par Camille via `/admin/settings/scoring`. Permet de tester "et si on met plus de poids sur la marque ?".

3. **Recalcul mensuel automatisé** : déjà mentionné "automation 1er mercredi" dans la doc → vérifier que c'est bien actif et logger les changements.

**P1**

4. **Tendance externe — ingestion** : job hebdo qui scrape (avec respect des CGU) Vinted / Vestiaire Collective / Imparfaite pour collecter les **search trends** par marque et catégorie. Alternative : utiliser Google Trends API.

5. **Tendance historique btq par cluster cliente** : enrichir le score avec "qui achète ça" (Bronze / Silver / Gold + RFM cluster).

#### 5.8.3 Pricing & markdown (5.c)

**P0**

1. **Markdown engine déclaratif** : table `markdown_rules` éditable par Camille :

```sql
CREATE TABLE markdown_rules (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  active BOOLEAN DEFAULT TRUE,
  conditions JSONB, -- ex: {"score_max": 50, "age_min_days": 30, "categories": ["robes"]}
  action JSONB,     -- ex: {"discount_pct": 20, "tag_color": "yellow"}
  priority INT DEFAULT 100,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_by INT REFERENCES users(id)
);
```

2. **Job batch quotidien** : à 5h du matin, parcours du stock, application des règles markdown, génération d'un rapport "82 pièces démarquées cette nuit, 3 envoyées en retour tri" → email Camille.

3. **Tag couleur sur étiquette** : génération d'étiquettes avec un coin de couleur correspondant au cycle de vie (vert = nouveau, jaune = J+30, orange = J+60, rouge = J+90 retour tri imminent). Lecture immédiate par Sophie et clientes.

**P1**

4. **Pricing IA pour pièces "limites"** : si une pièce a un score à la frontière de 2 buckets, demander à Claude Haiku 4.5 une décision motivée ("garder à 35€ encore 2 semaines car marque Le Tanneur en hausse sur Vinted, si invendue passer à 25€").

5. **Simulation impact** : Camille peut tester "si je passe à -30% au lieu de -20% à J+60, quel impact sur la marge ?". L'API simule sur les 12 derniers mois et donne une projection.

**P2**

6. **Pricing-aware étiquette** : prix barré + nouveau prix sur étiquette imprimée, mention de la durée restante avant prochaine démarque ("après le 15 mai : -40%"). Crée le sentiment d'urgence.

### 5.9 Ajustements UX

- **Dashboard "Booster"** dédié dans `/admin/booster` : 3 onglets Mapping / Rating / Pricing.
- **Vue Sophie iPad mobile** : "Tableau de bord du jour" avec :
  - Pièces Hot à mettre en avant (3 cards)
  - Pièces à démarquer aujourd'hui (5 cards avec étiquettes à imprimer)
  - Pièces à retourner au tri (2 cards avec génération bon de retour)
- **Notification matinale** : push iPad à l'ouverture "Bonjour Sophie ! Voici les 8 actions du jour".

---

## 6. Architecture data & ingénierie — fondations pour l'IA

> **Cette section adresse spécifiquement la demande "ingénierie du système de stockage data et scoring des produits".** C'est la fondation sans laquelle tout le reste plafonne.

### 6.1 Diagnostic

L'application Vintiz a aujourd'hui une base **transactionnelle classique** (PostgreSQL) qui sert le métier (produits, clients, transactions) mais qui n'est pas pensée pour l'IA et l'analytics avancés. Les principaux manques attendus :

- **Pas d'event store** : aucune trace fine des interactions (vue produit, essayage, mise au panier abandonné, recommandation présentée, recommandation cliquée).
- **Pas de schéma analytique séparé** : les KPIs reporting et les modèles tournent sur la même DB OLTP que les transactions caisse → contention de ressources.
- **Pas de feature store pour l'IA** : pas de table dédiée aux features dérivées (`product_embeddings`, `customer_taste_profiles`).
- **Pas de versioning des modèles** : si on change le scoring, comment compare-t-on les performances avant/après ?

### 6.2 Architecture cible (3 couches)

```
┌─────────────────────────────────────────────────────────────┐
│  COUCHE OLTP — PostgreSQL 16 (déjà en place)                │
│  Tables : products, customers, transactions, zones, ...     │
│  Volume : ~10k produits, ~2k clients, ~50k transactions/an  │
└─────────────────────────────────────────────────────────────┘
                            ↓ (CDC ou batch)
┌─────────────────────────────────────────────────────────────┐
│  COUCHE EVENTS — PostgreSQL même instance, schema séparé    │
│  Tables : events, sessions, recommendations_log             │
│  Volume : ~500k events/an                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓ (jobs Python)
┌─────────────────────────────────────────────────────────────┐
│  COUCHE FEATURES — pgvector + tables dérivées               │
│  Tables : product_embeddings, customer_taste_profiles,      │
│           market_trends_cache, scoring_history              │
│  Refresh : daily batch + on-event hot path                  │
└─────────────────────────────────────────────────────────────┘
```

Pour Vernon (1 boutique, ~10k produits), une seule instance PostgreSQL avec 3 schemas (`public`, `events`, `features`) suffit. Pas besoin de Big Query / Snowflake.

### 6.3 Schéma `events` proposé

```sql
CREATE SCHEMA events;

CREATE TABLE events.event_log (
  id BIGSERIAL PRIMARY KEY,
  occurred_at TIMESTAMPTZ NOT NULL,
  event_type TEXT NOT NULL,
  customer_id INT REFERENCES public.customers(id),
  product_id INT REFERENCES public.products(id),
  session_id UUID,
  source TEXT,               -- 'pos', 'site', 'admin', 'api'
  metadata JSONB,
  PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

-- Partitions mensuelles (auto-créées par job)
CREATE TABLE events.event_log_2026_04 PARTITION OF events.event_log
  FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE INDEX idx_events_customer ON events.event_log(customer_id, occurred_at DESC);
CREATE INDEX idx_events_product ON events.event_log(product_id, occurred_at DESC);
CREATE INDEX idx_events_type ON events.event_log(event_type, occurred_at DESC);
```

#### Liste des `event_type` à tracer (a minima)

| event_type | Source | Métadonnées clés |
|-----------|--------|------------------|
| `product.created` | admin/api | `intake_batch_id`, `created_by_user_id` |
| `product.viewed` | site, admin | `referrer`, `session_id` |
| `product.try_requested` | site (réservation 48h) | `expires_at` |
| `product.try_in_store` | pos (scan en cabine) | `cabin_id` |
| `product.sold` | pos | `transaction_id`, `discount_pct` |
| `product.refunded` | pos | `transaction_id`, `reason` |
| `product.donated` | admin | `reason`, `recipient` |
| `product.returned_to_sorting` | admin | `markdown_cycle`, `reason` |
| `product.markdown_applied` | batch | `from_price`, `to_price`, `rule_id` |
| `product.zone_changed` | admin | `from_zone_id`, `to_zone_id` |
| `customer.signed_up` | site | `source`, `referrer_id` (parrainage) |
| `customer.visited` | pos | `transaction_id` (NULL si visite sans achat) |
| `customer.recommendation_shown` | site, admin | `recommendation_set_id`, `algo_version` |
| `customer.recommendation_clicked` | site | `product_id`, `position_in_list` |
| `cashier.session_opened` | pos | `cash_initial`, `cashier_id` |
| `cashier.session_closed` | pos | `cash_counted`, `discrepancy`, `cashier_id` |

### 6.4 Pipeline IA "online vs offline"

```
[ONLINE — temps réel, latence < 200ms]
- Lookup customer → lookup taste_profile → similarité contre catalogue indexé
- Filtrage stock disponible
- Reformulation Claude Haiku (cache si même cliente <24h)

[OFFLINE — batch nocturne, latence < 60min]
- Recalcul taste_profile pour clients avec activité du jour
- Recalcul product_embeddings pour produits nouveaux
- Recalcul score 6 composantes (mensuel selon doc actuelle, à passer hebdo)
- Application markdown_rules
- Génération rapport hebdo (le lundi 6h)
```

### 6.5 Stockage des modèles & versioning

Pas besoin de MLflow tant qu'on est sur des règles + LLM en runtime. Mais **versionner** :

- Les **prompts système** (cf. section 7) → fichiers `.md` dans `apps/api/prompts/` versionnés Git.
- Les **pondérations** scoring → table `scoring_config` avec history (`scoring_config_history`).
- Les **règles** markdown → table `markdown_rules` avec history.
- Les **embeddings** → champ `algo_version` sur chaque ligne, permet recalcul incrémental.

### 6.6 Backups & RGPD

- **Backup PostgreSQL** : déjà mentionné dans `scripts/backup.sh`. Vérifier la rétention (90 jours minimum), le test de restauration mensuel, le chiffrement.
- **Anonymisation events** : pour clients ayant exercé droit à l'oubli, remplacer `customer_id` par NULL dans `events` (les agrégats restent valides, l'identité disparaît).
- **Conservation legale** : transactions caisse 6 ans (NF525), events business 3 ans, logs auth 1 an.

### 6.7 Préconisations consolidées

**P0**

1. **Créer le schéma `events`** + tables partitionnées + indexes (script Alembic).
2. **Instrumenter** les endpoints API + frontend pour émettre les events listés en 6.3.
3. **Créer le schéma `features`** + tables pgvector.
4. **Activer pgvector** sur PostgreSQL 16 du Docker (`CREATE EXTENSION vector;`).
5. **Job batch nocturne** (cron k8s ou cron Docker) pour recalculs.

**P1**

6. **Dashboard observabilité events** : `/admin/data-quality` qui montre volumes events/jour, anomalies (ex : 0 vue produit le 12 mars = bug ?), taux de couverture (X% des transactions ont bien généré un event).

7. **Documentation** `docs/DATA_ARCHITECTURE.md` (à créer si absent) avec diagrammes, schémas, dictionnaire des events.

---

## 7. Bibliothèque de prompts pour agents IA externes

> **Cette section adresse explicitement la demande "tu m'assistes sur la rédaction des prompts nécessaires au traitement avec pertinence des requêtes".**

### 7.1 Prompt système — Personal Shopper

**Usage :** appelé depuis `POST /api/crm/clients/{id}/recommendations` après le pipeline d'embedding/diversification.

**Modèle suggéré :** Claude Haiku 4.5 (rapide, peu coûteux pour ce besoin).

```python
SYSTEM_PROMPT_PERSONAL_SHOPPER = """
Tu es la Personal Shopper de Vintiz, une boutique seconde main premium à Vernon en Normandie. Ta mission : présenter à une cliente fidèle 3 à 5 pièces sélectionnées rien que pour elle parmi le stock actuel.

Ton ton est :
- Chaleureux mais professionnel (vouvoiement par défaut, tutoiement seulement si la cliente est en mode "amie" — voir métadonnées)
- Concret : tu cites les pièces avec leur nom, leur taille, leur prix
- Court : 4-6 phrases maximum, pas de blabla
- Personnalisé : tu références au moins 1 achat passé de la cliente pour montrer que tu la connais

Ne fais JAMAIS :
- De compliments génériques ("vous avez bon goût")
- De fausses promesses ("c'est sûr que ça vous ira")
- De recommandation hors stock ou de pièce déjà vendue
- De mention d'autres clientes ("Marie a acheté la même")

Format de sortie attendu (Markdown) :

> [Phrase d'accroche personnalisée référençant 1 achat passé]
> 
> [Liste de 3-5 pièces, format : **Nom** (taille) — Prix — *Pourquoi cette pièce pour elle, 1 phrase*]
> 
> [Phrase de clôture invitant à venir essayer, mention horaires si jour spécifique recommandé]
"""

USER_PROMPT_TEMPLATE = """
Cliente : {customer_first_name}, niveau {tier}, dernière visite il y a {days_since_last_visit} jours.

3 derniers achats (du plus récent au plus ancien) :
{last_purchases_list}

Style identifié : {style_keywords}
Tailles habituelles : {preferred_sizes}
Couleurs préférées : {preferred_colors}

Sélection de pièces en stock pour elle (ordre : score de pertinence décroissant) :
{candidate_products}

M�téo Vernon prévue cette semaine : {weather_summary}

Génère le message Personal Shopper.
"""
```

**Astuce** : pour économiser des tokens, ne passer que les 3 dernières transactions et 5 produits candidats, pas tout l'historique.

### 7.2 Prompt système — Recommandation vitrine hebdomadaire

**Usage :** cron lundi 6h, génère 6-8 propositions vitrine.

```python
SYSTEM_PROMPT_WINDOW_DISPLAY = """
Tu es directrice artistique de Vintiz Vernon. Chaque lundi tu proposes la vitrine de la semaine.

Tes contraintes :
- 6 à 8 pièces maximum (4 femme, 2 homme, 1-2 accessoires)
- Cohérence visuelle : palette couleur unifiée (max 3 couleurs dominantes)
- Cohérence saisonnière : produits adaptés à la météo Vernon des 7 prochains jours
- Diversité catégories : pas que des hauts, pas que des robes
- Privilégier pièces score Hot (≥75) ET pièces nouvelles (<7 jours en btq)
- Au moins 2 pièces "signature" (marques fortes ou pièces rares)

Format de sortie attendu (JSON strict) :

{
  "theme": "string court, ex: 'Pastels printaniers'",
  "color_palette": ["#hex1", "#hex2", "#hex3"],
  "items": [
    {
      "product_id": int,
      "position": "central" | "left" | "right" | "back",
      "rationale": "1 phrase pour Sophie qui va monter la vitrine"
    }
  ],
  "next_review_date": "YYYY-MM-DD"
}
"""
```

### 7.3 Prompt système — Audit pricing pièce limite

**Usage :** appelé pour les pièces dont le score est sur la frontière entre 2 buckets, pour lesquelles la règle déterministe ne suffit pas.

```python
SYSTEM_PROMPT_PRICING_DECISION = """
Tu es analyste pricing pour Vintiz seconde main. Une pièce vient d'atteindre 30 jours en btq sans être vendue. Tu dois recommander : MAINTENIR le prix, DÉMARQUER, ou RETOURNER AU TRI.

Tu prends en compte :
- Le score de la pièce et ses 6 composantes
- L'évolution des tendances seconde main de la marque sur les 30 derniers jours
- Le sell-through rate de la catégorie sur les 90 derniers jours
- La place disponible en btq (saturation des zones)
- La marque (top brands → on attend, brands génériques → on démarque vite)

Format de sortie attendu (JSON strict) :

{
  "decision": "MAINTAIN" | "DISCOUNT" | "RETURN",
  "discount_pct": int,  // 0 si MAINTAIN
  "rationale_short": "1 phrase pour Sophie",
  "rationale_long": "3 phrases pour Camille avec données chiffrées",
  "next_review_date": "YYYY-MM-DD"
}
"""
```

### 7.4 Prompt système — Génération posts RS

**Usage :** appelé hebdomadairement pour proposer 4 posts Insta/TikTok.

```python
SYSTEM_PROMPT_SOCIAL_POSTS = """
Tu es community manager de Frip & Co Vernon (Instagram + TikTok). Génère 4 propositions de posts pour la semaine.

Identité de marque :
- Boutique seconde main premium à Vernon (Eure, Normandie)
- Mission ESS : circularité, insertion par le travail
- Ton : chaleureux, accessible, proche, fier des valeurs sans être moralisateur
- Émojis : avec parcimonie, pas plus de 2 par post

Mix éditorial obligatoire (1 post par catégorie) :
1. PRODUIT STAR : 1 pièce du moment, photo centrée, prix visible, hook dans la 1ère ligne
2. VALEURS : 1 message ESS / circularité / insertion, sans culpabilisation
3. TÉMOIGNAGE : 1 cliente fictive ou anonymisée + sa pièce
4. ACTU LOCALE : 1 lien avec Vernon (marché, événement, saison)

Format de sortie attendu (JSON) :
{
  "posts": [
    {
      "category": "PRODUIT_STAR" | "VALEURS" | "TEMOIGNAGE" | "ACTU_LOCALE",
      "platform": "instagram" | "tiktok" | "both",
      "caption": "string",
      "hashtags": ["string"],
      "best_time": "HH:MM",
      "media_brief": "description de la photo/vidéo à produire"
    }
  ]
}
"""
```

### 7.5 Prompt système — Analyse photo produit (intake)

**Usage :** appelé sur `POST /api/inventory/products/from-photo` (à créer).

```python
SYSTEM_PROMPT_PHOTO_INTAKE = """
Tu analyses la photo d'un vêtement seconde main qui vient d'arriver en boutique. Ton rôle : pré-remplir la fiche produit pour gagner du temps à l'employée qui l'étiquette.

Tu dois identifier :
1. CATEGORIE : robe / haut / pull / jean / pantalon / jupe / veste / manteau / sac / chaussures / accessoire
2. COULEUR DOMINANTE : nom + code hex
3. COULEURS SECONDAIRES : 0 à 2
4. STYLE : minimaliste / vintage / boho / chic / sport / décontracté / soirée
5. SAISON CIBLE : printemps / été / automne / hiver / mi-saison
6. ETAT APPARENT : excellent / très bon / bon / moyen
7. MARQUE si visible (étiquette, logo)
8. MATIERE apparente
9. COUPE : slim / droit / oversize / cintré / fluide
10. SIGNES D'USURE visibles : aucune / légère / modérée / importante
11. SIGNALEMENT DEFAUT : tâche, trou, bouton manquant, fermeture cassée

Format de sortie : JSON strict, valeurs en français, lowercase.

Si la qualité de photo est insuffisante (flou, mauvais éclairage, vêtement non visible), renvoyer :
{ "error": "PHOTO_QUALITY_INSUFFICIENT", "suggestion": "string courte sur ce qu'il faut refaire" }
"""
```

**Astuce performance** : pour Vintiz, utiliser **Claude Haiku 4.5 vision** (rapide, peu coûteux) pour le intake batch et **Claude Opus 4.7** uniquement pour les pièces premium / vintage rares dont la qualité de description impacte le pricing.

### 7.6 Prompt système — Suggestion zone de mise en rayon

```python
SYSTEM_PROMPT_ZONE_SUGGESTION = """
Tu es responsable merchandising. Une pièce vient d'être étiquetée. Suggère sa zone de mise en rayon parmi les 7 zones de la btq.

Tu prends en compte :
- Catégorie de la pièce (les robes vont dans les zones "femme", pas "homme")
- Saison cible vs météo Vernon des 14 prochains jours
- Score Hot/Warm/Slow (Hot → vitrine si stock disponible)
- Saturation actuelle des zones (capacité × taux d'occupation)
- Couleur (cohérence avec les pièces déjà en zone, ne pas casser une harmonie)

Format de sortie : JSON
{
  "zone_id": int,
  "zone_name": "string",
  "rationale_short": "1 phrase pour Sophie",
  "alternative_zone_id": int,  // si zone principale saturée
  "should_go_to_window": boolean
}
"""
```

### 7.7 Notes générales sur les prompts

- **Toujours expliciter le format de sortie attendu** (JSON, Markdown, etc.) avec un exemple. Sans ça, parsing fragile.
- **Toujours typer les sorties** côté API : Pydantic models pour les retours JSON.
- **Toujours définir les cas d'erreur** (ici `PHOTO_QUALITY_INSUFFICIENT`) → l'API peut router proprement.
- **Toujours versionner les prompts** dans Git (`apps/api/prompts/v1/personal_shopper.md`) pour comparer et roller back.
- **Toujours mesurer** : logger en `events.event_log` chaque appel LLM avec `algo_version`, latence, tokens, success/failure.

---

## 8. Plan d'action priorisé pour Claude Code

> Cette section est rédigée pour être lue et exécutée par Claude Code dans le repo Vintiz. Chaque ticket est rédigé sous forme actionnable avec critères d'acceptation.

### 8.1 Méthodologie pour Claude Code

Pour chaque ticket :
1. **Lire d'abord le code existant** dans la zone concernée (l'audit a été fait sur la doc, pas sur le code complet — il y a probablement des choses déjà implémentées non documentées).
2. **Mettre à jour `CLAUDE.md`** si la fonctionnalité existe déjà mais n'est pas documentée.
3. **Implémenter** uniquement si la fonctionnalité manque réellement.
4. **Tester** : les seeds existants (`scripts/seed_data.py`) doivent rester verts après chaque ticket.
5. **Créer une PR par phase** (pas par ticket — sinon trop de PR).

### 8.2 Phase 1 — Fondations data + corrections P0 (3-4 semaines)

#### Ticket P1-001 : Conformité NF525 (BLOCKER LÉGAL)

- Vérifier dans le code l'existence d'un journal d'événements inaltérable pour les transactions caisse.
- Si absent : implémenter chaînage SHA-256 des transactions (`prev_hash + transaction_payload`).
- Implémenter exports légaux (XML conforme spec DGFiP) + scellement annuel.
- Rédiger l'attestation éditeur Vintiz (template fourni par avocat fiscaliste).
- Ajouter section dédiée dans `CLAUDE.md` + `docs/COMPLIANCE_NF525.md`.

**Critères d'acceptation** : un `pytest` test_nf525.py vérifie que toute modification d'une transaction passée invalide la chaîne.

#### Ticket P1-002 : Multi-utilisateur + PIN cashier

- Table `users` avec champ `cashier_pin` (4 chiffres, hash bcrypt).
- Écran de login PIN au POS (à l'ouverture de session caisse).
- Toutes les transactions et events portent `cashier_id`.
- Rapport Z par cashier (qui était à la caisse, écart attribué).

#### Ticket P1-003 : Schéma `events` + instrumentation

- Migration Alembic créant `schema events` + table partitionnée mensuelle.
- Helper `app.events.emit(event_type, **kwargs)` avec async insert.
- Instrumenter au minimum : `product.sold`, `product.viewed`, `customer.visited`, `customer.recommendation_shown/clicked`, `cashier.session_opened/closed`.
- Job de création automatique des partitions futures (cron mensuel).

**Critères d'acceptation** : après une session test, la table `events.event_log` contient les events attendus.

#### Ticket P1-004 : pgvector + tables features

- `CREATE EXTENSION vector;` dans la DB (vérifier que l'image Postgres 16 supporte — sinon passer à `pgvector/pgvector:pg16`).
- Migration Alembic créant `schema features`.
- Table `features.product_embeddings` (vector(512) visual + vector(512) text).
- Table `features.customer_taste_profiles` (vector(512) × 2).
- Index HNSW sur les colonnes vectorielles.

#### Ticket P1-005 : Mode offline POS

- Queue locale IndexedDB côté Next.js admin (`apps/web`).
- Stockage des transactions en attente si API inaccessible.
- Rejeu automatique à la reconnexion.
- Indicateur visuel statut connexion (pastille verte/orange/rouge).

#### Ticket P1-006 : Cycle de vie produit explicite

- Enum SQL `product_status` avec : `RECEIVED`, `SORTED`, `TAGGED`, `DISPLAYED`, `SOLD`, `DONATED`, `RETURNED_TO_SORTING`.
- Champs : `received_at`, `displayed_at`, `markdown_history` (JSONB), `current_markdown_pct`.
- Endpoint pour transitions : `POST /api/inventory/products/{id}/transition`.
- Vue Kanban dans `/admin/inventory/kanban`.

#### Ticket P1-007 : RGPD-by-design CRM

- Écran `/account/data` espace client : voir mes données, exporter (JSON), supprimer (avec délai 30j).
- Table `consents` versionnée.
- Process de suppression : anonymisation `customer_id → NULL` dans `events`, hard-delete dans `customers`.
- CGU + politique de confidentialité (Markdown servi par Next.js).

### 8.3 Phase 2 — Personal Shopper v2 + Booster Mapping (4-6 semaines)

#### Ticket P2-001 : Pipeline embedding produits

- Service Python `app.ai.embeddings` avec :
  - `compute_visual_embedding(product_id)` → appel Claude Vision pour description structurée + encoder texte.
  - `compute_text_embedding(product_id)` → encoder sur la description.
- Job batch quotidien `recompute_embeddings.py` qui traite les nouveaux produits.
- Stocké dans `features.product_embeddings`.

#### Ticket P2-002 : Pipeline taste profile cliente

- Service `app.ai.taste_profile` qui :
  - Lit les 20 derniers achats d'une cliente.
  - Calcule centroïde pondéré des embeddings produits achetés.
  - Stocké dans `features.customer_taste_profiles`.
- Job hebdo qui recalcule pour clients actifs.

#### Ticket P2-003 : Endpoint Personal Shopper v2

- `GET /api/crm/clients/{id}/personal-shopper-v2` avec :
  - Filtre stock disponible + taille cliente.
  - Similarité cosinus pgvector.
  - Diversification (max 1 par catégorie).
  - Appel Claude Haiku 4.5 avec le prompt de section 7.1.
  - Retour `{ message: string, products: [...], recommendation_set_id: uuid }`.
- Logger dans `events.event_log`.

#### Ticket P2-004 : Cold start onboarding

- Écran inscription espace client : 5 photos style à liker (Pinterest-style) + quiz 3 questions style.
- Calcul d'un visual_centroid initial.
- UX < 2 minutes.

#### Ticket P2-005 : Vue plan boutique

- Page `/admin/store-plan` : SVG du plan de la btq (98m², 7 zones).
- Densité de produits par zone (couleur de remplissage).
- Survol zone → détail (capacité, occupation, score moyen produits).

#### Ticket P2-006 : Reco placement automatique

- À la transition `TAGGED → DISPLAYED`, appel Claude avec prompt 7.6.
- Suggestion zone affichée à Sophie, validation 1-tap.

#### Ticket P2-007 : Recommandation vitrine hebdomadaire

- Cron lundi 6h : prompt 7.2 → 6-8 propositions JSON.
- Notification Sophie iPad à l'ouverture btq.
- Validation 1-tap, bon de mise en rayon imprimable.

#### Ticket P2-008 : Recherche "Où est cette pièce ?"

- Composant POS : scan code-barres ou recherche → affichage zone exacte + statut.
- Audio feedback (bip différent selon "trouvé" vs "vendu").

### 8.4 Phase 3 — Markdown engine + SEO/RS (3 semaines)

#### Ticket P3-001 : Markdown engine déclaratif

- Tables `markdown_rules` + `markdown_rules_history`.
- Écran `/admin/settings/markdown` pour CRUD règles.
- Job batch nocturne qui applique.
- Rapport email Camille le matin.

#### Ticket P3-002 : Tag couleur étiquette

- Génération PNG étiquette avec coin coloré (vert/jaune/orange/rouge).
- Configuration des couleurs liée aux règles markdown.

#### Ticket P3-003 : Module visibilité (SEO + RS)

- Page `/admin/visibility` 3 onglets.
- OAuth Google Search Console + API tracking 10 mots-clés.
- Instagram Graph API + recherche hashtag #fripandco.
- Google Business Profile API : avis + suggestion réponse Claude.

#### Ticket P3-004 : Calendrier éditorial RS

- Page `/admin/social/calendar`.
- Génération hebdo via prompt 7.4.
- Validation/édition par Camille, export Meta Business Suite.

### 8.5 Phase 4 — KPIs avancés + UX polish (2-3 semaines)

#### Ticket P4-001 : KPIs retail standard

- Sell-through rate, GMROI, DOH, AIT, CA/m²/mois.
- Comparateurs S-1, M-1, A-1.
- Heatmap horaire jours × heures.

#### Ticket P4-002 : Reporting ESS dédié

- Page `/admin/ess-report`.
- Onglets mensuel/trimestriel/annuel.
- Export PDF format codir Solidarité Textiles.

#### Ticket P4-003 : Email automation Brevo

- Intégration API Brevo.
- Triggers : bienvenue, J+30 inactif, anniversaire, J+60 Gold inactif.
- Templates éditables `/admin/crm/email-templates`.

#### Ticket P4-004 : Apple/Google Wallet

- Génération `.pkpass` côté API.
- QR code points + tier dans la carte virtuelle.
- Mise à jour push à chaque transaction.

#### Ticket P4-005 : Réservation 48h

- Bouton fiche produit site vitrine.
- Workflow validation, expiration auto, notif SMS.
- Zone "Réservés" en btq (étiquette visuelle).

#### Ticket P4-006 : Mobile-first dashboard

- Refonte `/admin` mobile-first.
- Cards swipables, push notifications stratégiques.

---

## 9. Annexes

### 9.1 Liste des KPIs à instrumenter (priorité)

| KPI | Formule | Fréquence | Priorité |
|-----|---------|-----------|----------|
| CA journalier | Σ transactions du jour | temps réel | P0 |
| Panier moyen | CA / nb transactions | temps réel | P0 |
| Sell-through rate | unités vendues / unités reçues sur période | quotidien | P0 |
| Days on Hand | âge moyen stock | quotidien | P0 |
| GMROI | (CA - coût acq) / valeur stock moyen | mensuel | P1 |
| Conversion rate | nb transactions / nb visiteurs | quotidien | P1 (nécessite compteur) |
| AIT | nb pièces / nb tickets | quotidien | P1 |
| CA / m² / mois | CA mensuel / 98m² | mensuel | P1 |
| Top/Bottom 10 catégories | par STR | hebdo | P1 |
| LTV cliente | Σ achats vie cliente | mensuel | P2 |
| Churn Gold | Gold sans visite > 90j / total Gold | mensuel | P2 |
| Taux de réemploi | (vendues + données) / reçues | trimestriel | P0 (ESS) |
| CA reversé Solidarité Textiles | % CA selon convention | trimestriel | P0 (ESS) |

### 9.2 Stack outils tiers recommandés

| Besoin | Outil suggéré | Coût ordre de grandeur |
|--------|---------------|------------------------|
| Email transactionnel + automation | Brevo (ex Sendinblue) | Gratuit jusqu'à 300/jour |
| SMS | Twilio (déjà en place) | ~0,07€/SMS FR |
| Storage images produits | Scaleway Object Storage | ~0,01€/GB/mois |
| CDN images | Bunny CDN ou Scaleway CDN | ~0,01€/GB |
| Monitoring application | Sentry self-hosted ou Sentry Saas | 0€ ou 26$/mois |
| Backups DB | Scaleway Backup Service | inclus |
| Tracking SEO | Google Search Console API | Gratuit |
| Insights RS | Instagram Graph API | Gratuit |
| Avis Google | Google Business Profile API | Gratuit |
| Vector search | pgvector (déjà PG16) | 0€ |
| LLM inference | Anthropic API (Haiku 4.5 + Opus 4.7 ponctuel) | Variable, estimé < 50€/mois pour Vernon |
| Trends Vinted/Vestiaire | Scraping doux maison ou Apify | ~30-50€/mois si Apify |

### 9.3 Schéma simplifié — vue d'ensemble Vintiz post-audit

```
                ┌──────────────────────────────────────────┐
                │           SITE VITRINE PUBLIC            │
                │    (apps/site, Next.js 14, port 3001)    │
                │                                          │
                │  ▪ Vitrine : qui sommes-nous, accès      │
                │  ▪ Catalogue teaser (réservation 48h)    │
                │  ▪ Espace client (carte fid, perso shop) │
                │  ▪ Newsletter, parrainage                │
                └──────────────────┬───────────────────────┘
                                   │
                ┌──────────────────▼───────────────────────┐
                │              API FASTAPI                 │
                │     (apps/api, Python 3.11, port 8000)   │
                │                                          │
                │  /auth /inventory /pos /crm /ai          │
                │  /admin /reports /visibility (NEW)       │
                │  /events (NEW)                           │
                └──┬─────────────────────────────────┬─────┘
                   │                                 │
       ┌───────────▼────────┐                    ┌───▼───────────────┐
       │  POSTGRESQL 16     │                    │  CLAUDE API       │
       │  + pgvector        │                    │  Haiku 4.5 +      │
       │                    │                    │  Opus 4.7 ponctuel│
       │  Schemas:          │                    │  Vision           │
       │  ▪ public (OLTP)   │                    └───────────────────┘
       │  ▪ events (NEW)    │
       │  ▪ features (NEW)  │
       └────────────────────┘
                   ▲
                   │
       ┌───────────┴────────────────────────────────┐
       │      ADMIN UI (apps/web, Next.js 14, :3000)│
       │                                            │
       │  POS tactile iPad (Inateck + SumUp)        │
       │  Inventaire (Kanban, embeddings)           │
       │  CRM (segmentation RFM)                    │
       │  Booster (mapping, scoring, markdown)      │
       │  Reports (KPIs retail + ESS)               │
       │  Visibility SEO/RS (NEW)                   │
       │  Settings (rules markdown, scoring weights)│
       └────────────────────────────────────────────┘

      ┌───────────────────────────────────────────┐
      │  EXTERNES                                 │
      │                                           │
      │  ▪ SumUp Solo (CB)                        │
      │  ▪ AirPrint imprimante 80mm               │
      │  ▪ Tiroir-caisse RJ11                     │
      │  ▪ Twilio (SMS)                           │
      │  ▪ Brevo (email auto, NEW)                │
      │  ▪ OpenWeatherMap (météo Vernon)          │
      │  ▪ Google Search Console / GBP            │
      │  ▪ Instagram Graph API                    │
      └───────────────────────────────────────────┘
```

### 9.4 Checklist "Avant ouverture publique Frip & Co Vernon"

À cocher par Camille avant le D-Day :

- [ ] **Conformité NF525** : attestation éditeur signée + tests OK
- [ ] **Multi-utilisateur PIN** : Sophie, Léa et autres employées ont leur PIN
- [ ] **Mode offline POS** : test coupure réseau réussi
- [ ] **SumUp Solo** : compte production activé, frais validés
- [ ] **Hardware POS testé** : douchette + AirPrint + tiroir RJ11 + iPad
- [ ] **Backup PostgreSQL** : test de restauration mensuel OK
- [ ] **RGPD** : CGU + politique conf publiées + écran droits client OK
- [ ] **Site vitrine** : Schema.org LocalBusiness + Lighthouse 90+
- [ ] **Personal Shopper v2** : 5 clientes Gold beta-testeuses validées
- [ ] **Markdown engine** : règles initiales chargées et testées
- [ ] **Reporting ESS** : convention Solidarité Textiles intégrée
- [ ] **Email automation** : welcome + J+30 + anniversaire actifs
- [ ] **Plan boutique 7 zones** : étiquettes physiques posées
- [ ] **Étiquetage en lot** : stock initial étiqueté (>500 pièces)

---

## 10. Comment lire ce rapport — guide pratique

### 10.1 Pour Julien

- **Lire** : Sommaire exécutif (§0), Personas (§1.1), Personal Shopper (§4), AI Booster (§5), Plan d'action (§8).
- **Décider** : ordre de priorité des phases en fonction de la date d'ouverture cible Vernon.
- **Valider** : la décomposition des 6 composantes du score (§5.3) — corriger si l'existant est différent.
- **Approuver** : les coûts mensuels estimés pour outils tiers (§9.2).

### 10.2 Pour Claude Code

- **Lire** : §1 (méthodologie), §6 (architecture data), §7 (prompts), §8 (plan d'action) intégralement.
- **Vérifier le code existant** avant chaque ticket — l'audit s'est fait sur la doc, pas le code complet.
- **Mettre à jour `CLAUDE.md`** au fur et à mesure pour qu'il reflète l'état réel.
- **Créer un fichier par module** : `docs/PERSONAL_SHOPPER.md`, `docs/AI_BOOSTER.md`, `docs/SCORING_ENGINE.md`, `docs/MARKDOWN_ENGINE.md`, `docs/DATA_ARCHITECTURE.md`, `docs/COMPLIANCE_NF525.md`.
- **Une PR par phase**, sous-tickets dans des commits dédiés.

### 10.3 Pour les agents IA externes

- Tous les prompts système sont dans la §7. Ils doivent vivre dans `apps/api/prompts/v1/` versionnés Git.
- Tout appel LLM doit être loggé dans `events.event_log` avec `algo_version`, latence, tokens.
- Tout appel LLM doit avoir une **fallback déterministe** (au cas où l'API Anthropic est down). Cf. mode "simulation" SumUp pour le pattern.

---

## Conclusion

Vintiz a un **socle technique solide et différenciant** :

- POS hardware-aware (Inateck + AirPrint + SumUp Solo) rare dans l'écosystème seconde main.
- IA déjà intégrée (Claude Vision + Haiku 4.5) avec mode simulation propre.
- Personal Shopper et AI Booster comme axes de différenciation forts vs. ThriftCart/Ricochet/Rose POS.

Les **3 priorités absolues** pour passer de "MVP techniquement bon" à "produit qui fait grandir Frip & Co Vernon" :

1. **Couche événementielle (events store + features)** — sans ça, l'IA plafonne.
2. **Personal Shopper v2 documenté** (embeddings + cold start + Claude rédaction) — c'est le marqueur de différenciation cliente.
3. **Markdown engine déclaratif** — Camille doit pouvoir piloter sa politique prix sans demander à un développeur.

Avec 3-4 semaines de Phase 1 puis 4-6 semaines de Phase 2, Vintiz peut **ouvrir Vernon avec un produit qui n'existe nulle part ailleurs en seconde main premium FR** : la btq physique avec Personal Shopper IA personnalisé live.

---

**Fin du rapport — 26 avril 2026**
**Préparé par : Claude (Anthropic) pour Julien Gondé**
**Version : 1.0 — révisable**
**Distribution : Julien Gondé, Claude Code, équipe Frip & Co Vernon (sur autorisation)**
