# Audit Brand Review & Marketing — Vintiz

> **Auteur** : Claude (audit externe complémentaire)
> **Date** : 2026-05-08
> **Périmètre** :
> 1. Audit du positionnement marketing et commercial Vintiz Vernon
> 2. Lecture du déploiement de la btq dans le retail seconde main FR
> 3. Plan d'action marketing pour différencier la boutique
> 4. Force du **Personal Shopper IA** dans la seconde main
> **Méthode** : synthèse repo (charte v3 Sauge Néo, prompts Claude, plans Phase 1-4) + reprise persona/concurrents Audit 3 + framework positioning canvas
> **Fait avec** : `AUDIT_VINTIZ_2026.md`, `PHASE_1_CLOTURE.md`, `PLAN_ACTION_2026.md`, `docs/DESIGN_SYSTEM.md`, `docs/UX_DESIGN.md`, `docs/MANUEL_BOUTIQUE.md`, `docs/PREDICTIVE_ENGINE.md`, prompts `personal_shopper.md` + `social_posts.md`, audits 1-3 livrés

---

## Synthèse exécutive

Vintiz possède une **fondation brand solide** (identité Sauge Néo v3 cohérente, ton éditorial testé via prompts Claude versionnés, ancrage ESS authentique avec Solidarité Textiles). Le produit logiciel est mature opérationnellement (POS NF525, fidélité tier, IA Booster, Personal Shopper v1).

**Mais 5 trous marketing critiques** empêchent une mise sur orbite commerciale efficace :

1. **Site live en mode « coming soon »** depuis avril 2026 — zéro narrative publique, zéro page `/a-propos`, zéro page `/personal-shopper`, zéro audience organique préemptée avant ouverture
2. **Réseaux sociaux silencieux** — prompts générateurs de posts (`social_posts.md`) versionnés et prêts mais **aucun post live diffusé**, audience organique = 0
3. **Personal Shopper IA non utilisé comme arme marketing** — c'est l'**unique** différenciateur sur le marché FR 2nde main au 05/2026 (Younzee = software-only sans stock, Vestiaire Collective = pas conversationnel) et il reste invisible publiquement
4. **Narrative ESS / impact muette publiquement** — Solidarité Textiles citée uniquement en pied de page `/confidentialite`, alors que c'est un levier majeur de différenciation vs Vinted / Imparfaite / Once Again
5. **Zone Giverny / 600 000 visiteurs CSP+/an non préemptée** — aucun partenariat tourisme, aucune offre English-friendly, aucune narrative « day trip from Paris »

**Effort plan d'action 12 mois** : ~30-40 j-marketing répartis sur 4 vagues (Pré-ouverture J-90 → J0 / Ouverture J0-J+30 / Croissance J+30-J+180 / Déploiement régional J+180-J+365). Budget activation externe estimé : **8-15 k€** la première année (création contenu, presse locale, événements, partenariats touristiques).

---

## Partie 1 — Audit du positionnement actuel

### 1.1 Identité de marque — état des lieux

| Élément | État actuel | Statut |
|---|---|---|
| **Nom** | Vintiz (portmanteau « vintage + vitrine » / aspirant style Vestiaire Collective) | ✓ |
| **Ancien nom** | Frip & Co — **interdit** dans les communications (`prompts/v1/social_posts.md:11-12`) | ✓ règle posée |
| **Baseline** | « Votre nouvelle destination Slow Fashion premium » (`apps/site/src/app/page.tsx:62-65`) | ✓ |
| **Sous-baseline** | « Des pièces uniques sélectionnées avec soin. Marques recherchées, qualité irréprochable, prix justes. » | ✓ |
| **Mission affichée** | « Boutique de vêtements de seconde main premium à Vernon, Normandie. Marques sélectionnées (Sandro, Maje, Isabel Marant…), pièces uniques, mode responsable » | ✓ mais peu visible (meta uniquement) |
| **Charte v3 « Sauge Néo »** (avril 2026) | Palette off-white `#F6F5F1`, teal `#0B7A6A` (CTA), magenta `#E84E8B` (célébrations only), or tier `#8E7B57` | ✓ très cohérent |
| **Typographie** | Fraunces (display, magazine indé), Manrope (body), JetBrains Mono (codes) | ✓ distinctif |
| **Logos** | Monogramme VZ teal `logo-teal.png`, magenta pour fonds sombres `logo-rose.png` (à régénérer en v3) | ⚠ logo-rose obsolète |
| **Adresse** | 6 rue Saint-Jacques, 27200 Vernon — Normandie | ✓ |

**Forces brand structurelles** :
- Charte v3 distinctive et premium (Fraunces + Sauge Néo = signature visuelle reconnaissable)
- Ton éditorial **testé et versionné** dans les prompts Claude (`personal_shopper.md`, `social_posts.md`)
- Mission claire : « seconde main premium » (pas de glissement vers le luxe pur ni le mainstream)

**Faiblesses identifiées** :
- Logo magenta v3 à régénérer (encore en `#FFC5DF` v2 — `docs/DESIGN_SYSTEM.md:126`)
- Baseline « Slow Fashion premium » pertinente mais **peu activée** : le site n'a pas de page qui développe ce positionnement
- Pas d'identité sonore ni d'identité photo cohérente documentée (pas de moodboard public, pas de guide photo brand)

### 1.2 Mission, vision, valeurs

**Mission** (extraite de la copie site + audit existant) :
> Rendre la mode premium accessible à toutes les Sophie, Julie et Léa de Vernon et alentours, en sélectionnant des pièces uniques de marques premium en seconde main, avec un service personnalisé via IA conversationnelle, dans une démarche d'économie circulaire ancrée localement.

**Vision** (à formaliser) :
> Devenir d'ici 2028 le **réseau de référence FR** sur le segment « 2nde main premium curée + Personal Shopper IA », avec 3-5 boutiques sur l'axe Normandie / Île-de-France ouest et une présence digitale forte ciblant les clients touristiques Vernon-Giverny.

**Valeurs implicites observables** :
- **Curation rigoureuse** (pas de friperie en vrac)
- **Slow fashion responsable** (sans moralisme — règle explicite `social_posts.md:16`)
- **Ancrage local** (Vernon, Normandie, Solidarité Textiles)
- **Tech au service de l'humain** (IA Booster pour le manager, Personal Shopper pour la cliente — pas de tech gadget)
- **Premium accessible** (50-300 €, pas le luxe pur)

### 1.3 Cibles

D'après `AUDIT_VINTIZ_2026.md §1.1`, 5 personas :

| Code | Persona | Cible primaire ? |
|---|---|---|
| **P-CLI-FID** | Julie, 38 ans, Vernon, Gold, 2×/mois, panier 65 € | ✓ **cœur de cible client** |
| **P-CLI-DEC** | Léa, 25 ans, Évreux, Bronze récente, Insta-driven | ✓ **cible acquisition** |
| P-EMP-BTQ | Sophie, employée boutique 45 ans | utilisatrice interne |
| P-MAN-RET | Camille, manager retail | utilisatrice interne |
| P-COM-DIR | Direction Solidarité Textiles | partenaire ESS |

**Lecture brand** : seules **Julie et Léa** sont des cibles marketing. Le reste relève du marketing RH ou du brand B2B.

### 1.4 Ton éditorial

| Dimension | Règle | Source |
|---|---|---|
| Adresse public | **Vouvoiement** systématique | `apps/site` newsletter form |
| Adresse interne (back-office) | **Tutoiement** | `docs/UX_DESIGN.md:359-378` |
| Adresse Personal Shopper | « tu » ou « vous » selon métadonnées cliente | `prompts/v1/personal_shopper.md:11-12` |
| Émojis | **Avec parcimonie** (max 2/post social) | `prompts/v1/social_posts.md` |
| Jargon tech | Banni en public | UX_DESIGN.md |
| Erreurs UX | Actionnables (« Vérifiez la connexion ») pas codes | UX_DESIGN.md |
| Moralisme ESS | **Banni** — fier sans donner de leçon | `social_posts.md:16` |

**Vocabulaire récurrent à pousser dans toute la com'** :
- « pépites » / « pièces uniques »
- « slow fashion premium »
- « sélectionnées avec soin »
- « marques recherchées »
- « personal shopper IA »

**À éviter** :
- « Powered by AI » (cosmétique)
- « Bonne affaire » (trop low-cost)
- « Vide-dressing » / « dépôt-vente » (Vintiz fait achat ferme — voir audit business model)
- Toute mention de l'ancien nom « Frip & Co »
- Moralisation ESG / climat anxiogène

### 1.5 Touchpoints existants

| Touchpoint | État | Audience activable |
|---|---|---|
| Site `vintiz.fr` | Coming soon, 5 pages publiques (4 légales + home) | aucune sans `/a-propos`, `/personal-shopper`, `/produits` |
| Newsletter | RGPD double opt-in fonctionnel, formulaire home | inscriptions précoces possibles dès J-90 |
| Carte fidélité | Bronze/Silver/Gold, 1 €=1 pt, wallet pass payload prêt (signing en attente) | activable au lancement boutique |
| Personal Shopper IA | v1 (rules) backend + v2 (embeddings + Claude Haiku) en Phase 2 | **non activé publiquement** |
| POS Companion | Suggestions cross-sell + alertes RFM côté caissière | activé en interne uniquement |
| Email transactionnel | Brevo API prête (anniversaire P4-008, nouvelles arrivées hebdo P4-009) | activable au lancement |
| Wallet pass Apple/Google | Payload prêt, signing à plugger | activable au lancement |
| Réseaux Insta / FB / TikTok | Comptes annoncés `@vintiz.fr` dans `sameAs` JSON-LD, **0 post live** | à allumer J-90 |
| Posts auto-générés Claude | Prompt `social_posts.md` versionné (4 posts/sem : produit star, valeurs, témoignage, actu locale) | **prêt mais inactif** |
| Avis / mentions Google | Endpoints API prêts (`/api/seo/mentions`, `/api/seo/reviews`) avec brouillon réponse Claude | activable post-ouverture |
| Page Google Business Profile | Non créée | bloquant SEO local |
| Office Tourisme Vernon | Pas de partenariat actif | activable J-60 |
| Fondation Monet Giverny | Pas de partenariat actif | activable J0 |
| Hôtels Vernon-Giverny | Pas de partenariat actif | activable J+30 |
| Presse locale (Vernon Direct, Media Normandie) | Aucune relation | activable J-30 |
| Presse spécialisée mode (FashionUnited, FashionNetwork) | Aucune relation | activable J0 |

→ **Constat** : tout le **socle technique est prêt**, mais **aucun canal n'est activé** publiquement. C'est purement un sujet d'exécution marketing.

---

## Partie 2 — Lecture du marché 2nde main FR (mai 2026)

### 2.1 Données macro

- **74 % des Français** achètent de la 2nde main en 2026 (baromètre iligo)
- **78 % en revendent** régulièrement
- **1 article sur 4 vendu en France** = soit 2nde main, soit ultra fast fashion (CMCM 2026)
- Le segment 2nde main mode entre dans une **phase de stabilisation post-explosion** : la croissance ralentit, la qualité de l'offre devient critique pour gagner des parts
- **37 %** des acheteurs 2nde main citent l'écologie comme motivation, **20 %** craignent de se faire tromper sur la qualité ou l'authenticité
- Vinted a passé les **24,4 M visites/mois FR** en mars 2026

### 2.2 Segmentation marché 2nde main FR

| Segment | Acteurs | Modèle | Marge brute typique |
|---|---|---|---|
| **C2C marketplace mass** | Vinted, Vinted Pro | commission | très faible côté plateforme |
| **C2C luxe** | Vestiaire Collective | commission + frais auth | 50 %+ |
| **Marketplace curée premium** | Imparfaite | commission + capsules | élevée |
| **Friperie / dépôt-vente régional** | Hiboutik clients (friperies indé), Once Again, Anaïs luxury vintage Vernon | achat ferme ou dépôt | 40-60 % |
| **Solidaire / ESS** | Emmaüs, Croix-Rouge, Le Relais (Ding Fring) | don + insertion | hors profit |
| **Achat ferme premium curé + tech** | **Vintiz** | achat ferme + IA | 50-65 % cible |
| **Personal Shopper IA software** | Younzee | abonnement | n/a (early stage) |

### 2.3 Tendances structurantes

1. **Curation > Marketplace** — Vestiaire Collective lui-même pivote vers la « curatorial economy » (stylistes, KOLs, IA d'authentification), validation thèse Vintiz
2. **Personal Shopper IA conversationnel** = **émergence en France** au 05/2026 — Younzee est le seul acteur FR identifié, software-only sur du neuf. **Le marché est ouvert pour un acteur stock 2nde main**
3. **Premium accessible (50-300 €)** = créneau insuffisamment couvert — Vinted = trop bas, Vestiaire = trop luxe, Imparfaite = ok mais marketplace pure (pas de boutique physique)
4. **Liaison physique + digital + ESS** = différenciation forte vs marketplaces pures
5. **Boutiques avec capsules mensuelles** (modèle Imparfaite « les pépites du mois ») fonctionnent bien — Vintiz peut adapter en « Les pépites de Vernon »
6. **Régional + tourisme premium** = filon non exploité — Vintiz + Giverny touristique = niche unique
7. **Patatam liquidé janv. 2024** = **leçon** : sans unit economics solides ni curation forte, la 2nde main premium ne tient pas

### 2.4 Enseignements pour Vintiz (action items déjà actés Audit 3)

- Valider le segment **« premium curé + IA + ancrage local »** = créneau libre
- Capter les keywords **Personal Shopper IA / Vernon / Giverny** avant saturation
- Construire un **modèle omnichannel** (boutique + e-com + Vinted Pro vitrine + corners hôtels)
- Activer le **partenariat Le Relais** (point de collecte) pour narrative ESS mesurable

---

## Partie 3 — Proposition de positionnement (value proposition canvas)

### 3.1 Pour Julie (P-CLI-FID, cliente fidèle Gold, Vernon, 38 ans)

**Jobs à régler** :
- Renouveler sa garde-robe sans culpabilité
- Trouver des pièces de marque sans payer le neuf
- Avoir un conseil stylistique personnalisé
- Récupérer rapidement et facilement

**Frustrations actuelles (concurrents)** :
- Vinted : trop de tri, qualité aléatoire, pas de conseil
- Vestiaire Collective : prix luxe, pas d'ancrage local
- Friperies Vernon : pas premium
- Anaïs luxury vintage Vernon : Chanel-only, peu digital

**Promesse Vintiz à Julie** :
> « Vintiz, c'est ta sélection Sandro / Maje / Sézane / Ba&sh / Polène / IRO authentifiée à 5 minutes de chez toi, avec une IA Personal Shopper qui apprend tes goûts au fil de tes visites. Réservation 24-48h, retrait en boutique, points fidélité, wallet pass Apple. »

**Preuves** :
- Stock physique réel et visible (boutique + photos site)
- Personal Shopper IA conversationnel (pas une simple liste d'algos)
- Ancrage Vernon (proximité, retrait facile)
- Tier Gold avec avantages tangibles

### 3.2 Pour Léa (P-CLI-DEC, cliente découverte, Évreux, 25 ans, Insta)

**Jobs à régler** :
- Trouver des pièces uniques shootables pour Insta/TikTok
- Découvrir des marques abordables (50-300 €)
- Vivre une expérience boutique différenciante
- Acheter dans un endroit avec un récit (vs Vinted impersonnel)

**Frustrations actuelles** :
- Vinted : pièces vues partout, pas de prestige social
- Friperies Évreux : mainstream, pas Insta-friendly
- Pas d'expérience curée à 30 min de chez elle

**Promesse Vintiz à Léa** :
> « Vintiz, c'est l'adresse pépite à 30 min d'Évreux, dans la même journée que Giverny, où tu trouves la robe Sandro qui ne sera pas sur Vinted, photographiée comme dans un magazine, recommandée par une IA qui comprend ton style. »

**Preuves** :
- Photos premium produits sur site (à produire — gap)
- Capsules mensuelles « Les pépites de Vernon »
- Insta feed cohérent
- Personal Shopper IA accessible dès la première visite (pas réservé Gold)

### 3.3 Énoncé de positionnement consolidé

> **Pour les femmes de 25-55 ans en Normandie et Île-de-France ouest qui veulent renouveler leur garde-robe avec des pièces de marque premium sans culpabilité, Vintiz est la seule boutique seconde main premium curée à Vernon qui combine sélection Sandro / Maje / Sézane / IRO authentifiée, Personal Shopper IA conversationnel et ancrage ESS via Solidarité Textiles — parce que la slow fashion mérite un service personnalisé, pas un marketplace impersonnel.**

### 3.4 Marketing mix 4P

| P | État actuel | Recommandation |
|---|---|---|
| **Produit** | Stock 2nde main premium, achat ferme, scoring 6 composantes, multi-photos, fidélité tier | Capsules mensuelles thématiques (« 10 pépites Sézane mai 2026 »), grids 2 colonnes mobile, vidéos try-on TikTok |
| **Prix** | Régime normal TVA 20 %, fourchette 50-300 € (premium accessible), pas de markdown engine actif | Prioriser Phase 3 markdown engine (J+30/60/90 décote auto) ; pricing dynamique stock-driven ; positionnement « toutes pièces -50 à -70 % du neuf » |
| **Place** | 1 boutique Vernon 6 rue Saint-Jacques (ouverture sept-2026 visée), site `vintiz.fr` coming soon, présence Insta/FB/TikTok déclarée mais inactive | Ajouter Vinted Pro (vitrine 2nde canal), corners hôtels Giverny / concept stores Rouen, partenariat Office Tourisme Vernon |
| **Promotion** | Charte v3 prête, prompts Claude posts/PS prêts, **0 activation publique** | Plan de lancement 12 mois (Partie 5), activer presse locale + presse mode + influenceurs micro Normandie |

---

## Partie 4 — Force du Personal Shopper dans la 2nde main

> Cette partie répond directement au brief : « plan d'action marketing pour marquer les différences de la boutique et notamment la force du personal shopper dans la 2nde main ».

### 4.1 Pourquoi le Personal Shopper est l'arme marketing #1 de Vintiz

| Concurrent | Stock 2nde main | IA conversationnelle | Boutique physique | Ancrage régional |
|---|---|---|---|---|
| Vinted | ✓ mass | ❌ algos basiques | ❌ | ❌ |
| Vestiaire Collective | ✓ luxe | ⚠ authentification + reco | ❌ | ❌ |
| Imparfaite | ✓ premium | ❌ | ❌ | ❌ |
| Once Again | ✓ mainstream | ❌ | ✓ Orléans/Compiègne | ✓ régional |
| Younzee | ❌ neuf | ✓ avatar 3D | ❌ | ❌ |
| Anaïs luxury Vernon | ✓ Chanel | ❌ | ✓ Vernon | ✓ Vernon |
| **Vintiz** | ✓ **premium curé** | ✓ **Claude Haiku conversationnel** | ✓ **Vernon** | ✓ **Normandie + Giverny** |

→ **Vintiz est seul à cocher les 4 cases**. C'est la base d'un positionnement **« First mover »** sur le marché FR.

### 4.2 Story du Personal Shopper Vintiz

**Promesse** :
> « Notre Personal Shopper IA Vintiz, c'est comme avoir une copine styliste qui connaît votre dressing, votre budget, et qui a fouillé toute la boutique pour vous, en 30 secondes, à toute heure. »

**Preuves opérationnelles** :
- Claude Haiku 4.5 (Anthropic, hébergement UE-Irlande, anti-réutilisation training data)
- Embeddings pgvector du catalogue (similarité visuelle, sémantique texte libre)
- Croisement : historique achats + préférences + clics + contexte (saison, météo Vernon)
- Recommandation **narrative** : 4-6 phrases explicatives, pas une grille
- Boucle de feedback continue (clic → ré-injection)
- Réservation 24-48h, retrait boutique
- Disponibilité 24/7, pas de file d'attente

**Différence vs un personal shopper humain** :
- 24/7
- Apprend de chaque clic
- Pas de jugement social
- Aussi bon à 23h qu'à 14h
- Connaît tout le stock à la seconde près
- Ne pousse pas à la vente — recommande sur consentement explicite (RGPD-by-design)

**Différence vs une IA mode classique (Younzee, Vestiaire)** :
- Adossé à un **stock physique réel** que la cliente peut voir/essayer
- Conversation, pas dressing virtuel 3D abstrait
- Local + retrait boutique (vs 100 % digital)
- Intégré à un programme de fidélité tangible (wallet pass)

### 4.3 Activation marketing du Personal Shopper

**Tactique 1 — Page vitrine `/personal-shopper`** (P0, audit SEO Action #3)

Voir spec détaillée audit 3 §6.2. Objectifs :
- Capter les keywords « personal shopper Vernon/Normandie » + « personal shopper IA » (faible concurrence, fort intent)
- Storytelling pédagogique : comment ça marche, ce qu'on analyse, pourquoi c'est différent
- CTA inscription espace client

**Tactique 2 — Démonstration vidéo TikTok / Reels Insta**

3 formats à itérer :
- « Mon personal shopper IA me trouve une tenue en 30 sec » (1 caissière + 1 cliente, vidéo verticale 30s)
- « Behind the scenes : comment l'IA Vintiz comprend votre style » (talking head Julien + visuels prompt)
- « Test : on lui demande l'impossible » (cas extrême — robe pour mariage à Giverny avec budget 80 €)

**Tactique 3 — Case studies clientes**

Une fois 3 mois post-ouverture, publier 2-3 testimonials clientes :
- Témoignage écrit + photos avant/après
- Format Insta carrousel + post blog
- Avec consentement RGPD (pas d'identification sans accord)

**Tactique 4 — Article presse mode**

Pitcher à FashionNetwork, FashionUnited, Le Figaro Madame, ELLE, L'Express :
- Angle : « la première IA conversationnelle française adossée à une boutique 2nde main premium »
- Différenciation Younzee (pas de stock) + Vestiaire (pas conversationnel) + Vinted (pas premium)
- Liaison ESS : « tech au service du local et du circulaire »

**Tactique 5 — Présence salons / events**

Cibles 2026-2027 :
- **Who's Next** (Paris, septembre/janvier) — salon mode pro, panel sur la 2nde main + IA
- **Salon de la Mode Éthique** (printemps) — angle ESS
- **Forum d'innovation Tech & Mode** (Paris, automne)
- **Événements Office Tourisme Vernon** (Giverny en lumière, Bouquet Normand)

**Tactique 6 — Pédagogie vocabulaire**

Construire un mini-glossaire :
- Personal Shopper IA = ?
- Embeddings = ?
- RGPD-by-design = ?

À placer dans `/personal-shopper` + FAQ + posts Insta « Question du jour ».

### 4.4 Risques à anticiper sur le Personal Shopper

| Risque | Mitigation |
|---|---|
| **Hype IA / scepticisme** (« encore une IA gadget ») | Démonstrations live, pas de promesses irréalistes, parler bénéfice cliente plutôt que tech |
| **Fail public** (recommandation absurde) | Test interne 4 semaines avant launch ; intervention humaine documentée (audit 2 partie 4) |
| **AI Act art. 50** (transparence chatbot, applicable 02/08/2026) | Disclaimer permanent UI shopper (audit 2 P2 #14) |
| **Concurrence Younzee qui pivot vers du stock** | First mover advantage — aller vite, communiquer fort dès J-30 |
| **Vestiaire Collective qui ouvre du conversationnel** | Vintiz reste local + premium accessible, hors leur cible luxe |

---

## Partie 5 — Plan d'action marketing 12 mois

### 5.1 Vague J-90 → J-30 (juin → juillet 2026) — Pré-ouverture

**Objectifs** : préempter l'audience locale + digitale avant ouverture, créer la « waitlist Vintiz ».

| # | Action | Effort | Livrable |
|---|---|---|---|
| M1 | Activer pages publiques manquantes : `/contact`, `/a-propos`, `/personal-shopper`, `/produits` (vitrine 10-15 pièces) | L | 4 pages live indexées |
| M2 | Activer fiche Google Business Profile + valider Google Search Console | M | GBP + GSC OK |
| M3 | Démarrer programme posts sociaux Claude (4 posts/semaine via prompt versionné) — Insta + FB + TikTok | M récurrent | 12+ posts/mois |
| M4 | Lancer waitlist newsletter avec teasing (« Vintiz ouvre en septembre — réservez votre première visite + 50 pts cadeau ») | M | 200-500 inscriptions cible |
| M5 | Pitcher presse locale Vernon (Vernon Direct, Paris-Normandie, Media Normandie) — interview Julien Gondé fondateur | M | 2-3 articles |
| M6 | Préparer kit influenceurs micro Normandie (10-15 cibles 5k-50k followers Insta/TikTok) — produits gratuits + brief | L | 5-10 partenariats J0 |
| M7 | Préparer pack « Premier shopping Vintiz » (welcome offer 10 % + accès Personal Shopper anticipé) | S | offre activable J0 |
| M8 | Approcher Office Tourisme Vernon + Fondation Monet Giverny — partenariat de visibilité | M | accord de principe J-15 |

**Budget externe** : ~3-5 k€ (presse, kits influenceurs, photos pro 10-15 pièces)

### 5.2 Vague J0 → J+30 (septembre → octobre 2026) — Ouverture

**Objectifs** : générer du trafic, premiers achats, premiers avis Google, premiers posts UGC.

| # | Action | Effort | KPI cible |
|---|---|---|---|
| M9 | Inauguration boutique : événement physique (vernissage 50 personnes, presse locale, influenceurs micro) | L | 1 inauguration + 30 photos exploitables |
| M10 | Activer email anniversaire (P4-008) + nouvelles arrivées hebdo (P4-009) | S | 2 flows live |
| M11 | Activer carte fidélité + wallet pass Apple/Google (signing pluggé) | M | 100 cartes émises J+30 |
| M12 | Activer Personal Shopper IA publiquement (avec écran consent explicite — voir audit 2 P0 #4) | déjà en P0 conformité | 30 % membres actifs PS |
| M13 | Pitcher presse mode nationale (FashionNetwork, FashionUnited, Le Figaro Madame) — angle « Personal Shopper IA + 2nde main + ESS Normandie » | M | 1-2 articles nationaux |
| M14 | Lancer 1ère capsule mensuelle « Les pépites de Vernon — septembre 2026 » (10 pièces curées avec narrative) | M récurrent | mensuel |
| M15 | Demander avis Google après chaque transaction (POS imprime QR avec lien) | S récurrent | 30+ avis fin J+30 |
| M16 | Activer Vinted Pro (vitrine secondaire, 30-50 pièces) | M | présence sans cannibalisation |
| M17 | Promo soft « 1er achat = adhésion offerte » (mode 3 du flag fidélité gratuit/payant/offert) | S | 60 % conversion 1ère visite → carte |

**Budget externe** : ~2-3 k€ (vernissage, photos, RP)

### 5.3 Vague J+30 → J+180 (octobre 2026 → mars 2027) — Croissance

**Objectifs** : asseoir l'audience, capter le tourisme Giverny, développer le trafic mobile.

| # | Action | Effort | KPI cible |
|---|---|---|---|
| M18 | Blog `/journal` — 1 article longue traîne SEO par mois (sujets audit 3 §5.3 #21-25) | M récurrent | 6 articles fin mars |
| M19 | Partenariats hôtels Vernon-Giverny (Hôtel d'Évreux, Domaine de Sens, Manoir des Impressionnistes…) — corner Vintiz mini-sélection | L | 2-3 corners actifs |
| M20 | Capsules mensuelles thématiques (Halloween, Noël, Saint-Valentin, Printemps) | M récurrent | 6 capsules |
| M21 | Email J+30 / J+90 / J+180 post-1er achat (réactivation) | M | activation flow |
| M22 | Lancer programme parrainage : Julie parraine Léa → 50 pts chacune | M | 10-15 % nouvelles inscriptions via parrainage |
| M23 | Ouvrir comptes Pinterest + LinkedIn (B2B / pros mode) — Pinterest fort impact 2nde main premium | M | 200+ followers Pinterest J+90 |
| M24 | Tester Insta Shopping + TikTok Shop (à valider selon dispo FR) | M | catalogue shoppable mobile |
| M25 | Atelier en boutique : « comment composer son dressing slow fashion » (1 par mois) | M récurrent | 10-15 participantes/atelier |
| M26 | Cas clientes (2 testimonials Personal Shopper + photos avant/après) | M | 2 cases studies live |
| M27 | Ajouter version EN du site (i18n minimale : home, /personal-shopper, /contact) pour tourisme international Giverny | L | EN version J+120 |

**Budget externe** : ~3-5 k€ (photos saisonnières, ateliers, traduction EN, Pinterest ads test)

### 5.4 Vague J+180 → J+365 (avril → septembre 2027) — Déploiement régional

**Objectifs** : tester un 2e point de vente, scaler la marque, devenir référence régionale.

| # | Action | Effort |
|---|---|---|
| M28 | Étude faisabilité 2e point de vente (Rouen ou Évreux) — analyse trafic, sourcing, équipe | XL |
| M29 | Si validé, ouverture 2e boutique avec cobranding « Vintiz Rouen » | XL |
| M30 | Renforcer partenariat Le Relais (point de collecte Vintiz boutique) — narrative ESS chiffrée |  M |
| M31 | Premier rapport d'impact ESS publié (kg revalorisés, % flux Solidarité Textiles vendu, CA reversé) | M |
| M32 | Embaucher 1 Community Manager / Content Creator dédié si croissance le permet | XL |
| M33 | Développer offre « Personal Shopper Premium » payante (accès illimité, sessions live, cadeau anniversaire) | M |
| M34 | Premier événement annuel « Les Talents de Vintiz » (clientes ambassadrices, presse mode, influenceurs) | XL |

**Budget externe** : variable selon ouverture 2e PdV (40-100 k€ si oui)

---

## Partie 6 — Activation locale Vernon ↔ Giverny

> Cette zone est la **vraie pépite** du positionnement Vintiz selon l'audit 3 (zone blanche premium 2nde main + 600 000 visiteurs CSP+/an Giverny).

### 6.1 Cartographie de l'écosystème local

| Acteur | Type | Action Vintiz |
|---|---|---|
| Office Tourisme Vernon | Touristique | partenariat de visibilité (flyers, listing, événements) |
| Fondation Claude Monet Giverny | Touristique premium | corner shop ? co-marketing « Vintiz visit + Giverny visit » |
| Hôtels Vernon (Hôtel d'Évreux, Manoir des Impressionnistes…) | Hospitality | corners Vintiz / sélection éditoriale + offre client hôtel |
| Restaurants pricey Vernon-Giverny | Hospitality | flyers / displays |
| Commerce voisin rue Saint-Jacques | Local | cross-promotion « passport Vernon premium » |
| Solidarité Textiles | ESS partenaire | narrative impact mensuelle |
| Le Relais (Ding Fring) | ESS | point de collecte Vintiz |
| Croix-Rouge Vernon-Gaillon | ESS | redonner pièces Vintiz non vendables |
| Vernon Normandie Tourisme | Touristique | inscription annuaire + presse régionale |
| Mairie de Vernon — service commerce | Local | participation à « Vernon en fête », « Marché de Noël » |

### 6.2 Tactiques d'activation tourisme premium

| # | Action |
|---|---|
| T1 | Page `/personal-shopper` en EN dès J+120 (tourisme international Giverny) |
| T2 | Sélection « **Made in France iconic**, second-hand » mise en avant pour touristes (Sandro / Maje / Sézane / Polène / Le Tanneur — marques iconiques FR) |
| T3 | Flyers « Day trip Vernon-Giverny » distribués dans hôtels / OT (matin Giverny, après-midi Vintiz, soir restaurant Vernon) |
| T4 | Compte Pinterest visuel — fort impact pour CSP+ international préparant un voyage Normandie |
| T5 | Co-marketing avec une boutique Giverny (galerie d'art, salon de thé, boutique Monet) — passport touriste avec 10 % chez chaque partenaire |
| T6 | Présence Trip Advisor / Google Maps avec photos premium boutique |
| T7 | English-friendly POS : tutoriel cashier pour adresser une touriste anglophone (vocabulaire de base + sticker drapeau) |
| T8 | Détaxe pour touristes hors UE (Vintiz peut-elle bénéficier ? à valider avec EC — spécificité régime normal TVA = oui possible) |

### 6.3 Tactiques d'activation locale Eure / Normandie

| # | Action |
|---|---|
| L1 | Insertion presse locale Vernon Direct + Paris-Normandie + Media Normandie (3 articles cibles 6 premiers mois) |
| L2 | Partenariat avec lycées hôteliers / mode régionaux (alternance, stages) |
| L3 | Inclusion dans annuaires : Pages Jaunes, alternativi.fr, Vernon Direct, Office Tourisme Vernon |
| L4 | Soutien d'associations locales (Vernon Festival, événements caritatifs) — sponsoring matériel pieces vintage cadeaux |
| L5 | Newsletter locale focus Eure (ouvertures, événements, pépites de la semaine) |

---

## Partie 7 — Mesure & KPIs marketing

### 7.1 KPIs pré-ouverture (J-90 → J0)

| KPI | Cible J0 |
|---|---|
| Inscriptions newsletter waitlist | 300-500 |
| Followers Insta | 500-1 000 |
| Followers TikTok | 200-500 |
| Followers Facebook | 200-300 |
| Articles presse locale | 2-3 |
| Articles presse régionale | 1-2 |
| Trafic site `vintiz.fr` (J-30 → J0) | 5 000-10 000 visites cumulées |
| Backlinks externes | 5-10 (presse + annuaires) |

### 7.2 KPIs ouverture (J0 → J+30)

| KPI | Cible J+30 |
|---|---|
| Cartes fidélité créées | 80-150 |
| Avis Google (note ≥ 4,5/5) | 25-50 |
| Inscrits Personal Shopper IA (consent explicite) | 50 % des membres |
| Visiteurs uniques boutique | 600-1 200 |
| Conversions visite → 1er achat | 25-35 % |
| Panier moyen | 65-90 € (vs 65 € persona Julie) |
| Posts Insta engagement rate | > 5 % |
| Articles presse mode nationale | 1 |

### 7.3 KPIs croissance (J+30 → J+180)

| KPI | Cible J+180 |
|---|---|
| Cartes fidélité actives | 500-800 |
| Membres Gold | 50-80 |
| Taux d'utilisation Personal Shopper (membres consent) | 40-60 % |
| Click-through rate sur recos PS | > 20 % (vs cible PLAN_ACTION_2026 §P5-001) |
| Sell-through stock 90 jours | > 60 % (vs cible Phase 4 P4-001) |
| Avis Google cumulés (note ≥ 4,5) | 100-200 |
| Followers Insta | 3 000-5 000 |
| Newsletter abonnés | 1 500-2 500 |
| Articles blog `/journal` publiés | 6 |
| Trafic organique mensuel | 3 000-6 000 visiteurs |

### 7.4 KPIs déploiement (J+180 → J+365)

| KPI | Cible J+365 |
|---|---|
| Membres fidélité | 1 200-2 000 |
| CA boutique annuel (1 PdV) | indicateur business à valider avec Julien |
| Taux de réachat 6 mois | > 50 % |
| Net Promoter Score | > 50 |
| Rapport d'impact ESS | 1 publié (kg revalorisés, % flux SoTex, CA reversé) |
| Mentions presse cumulées | 15-25 |
| Backlinks domaines référents | 30-50 |
| Position SEO « friperie Vernon » / « seconde main Vernon » | top 3 |
| Position SEO « personal shopper IA » | top 5-10 |
| 2e PdV (décision go/no-go) | tranchée fin J+365 |

### 7.5 Outils de mesure

| Outil | Usage |
|---|---|
| GA4 (déjà installé `G-6F4339T75H`) | trafic site, conversion, parcours |
| Google Search Console | requêtes SEO, position keywords, backlinks |
| Google Business Profile Insights | visibilité maps, appels, demandes itinéraire |
| Brevo (email transactionnel + newsletter) | open rate, CTR, conversion |
| Insta Insights / Meta Business Suite | engagement, audience, posts |
| TikTok Pro analytics | vues, complétion, partages |
| `/api/seo/snapshots` (interne) | snapshot SEO mensuel persisté |
| `/api/admin/predictive/audience` (interne) | snapshot dominant tastes loyal_active |
| Reporting interne `apps/web/src/app/reports/` | KPIs retail (sell-through, AIT, GMROI, CA/m²/mois) |

---

## Partie 8 — Synthèse stratégique

### 8.1 Les 3 piliers du positionnement Vintiz

1. **Premium curé local** — sélection rigoureuse marques aspirantes accessibles (50-300 €), ancrage Vernon-Normandie, pas de glissement vers le mainstream (anti-Vinted) ni vers le luxe pur (anti-Vestiaire)

2. **Personal Shopper IA conversationnel adossé au stock** — première offre française combinant IA conversationnelle + stock 2nde main premium + boutique physique. À transformer en arme marketing par la pédagogie, la démo vidéo et les case studies clientes

3. **ESS narrativée** — partenariat Solidarité Textiles + Le Relais + impact mesuré (kg revalorisés, % flux centre de tri vendu, emplois insertion) — narrative authentique sans moralisme, levier puissant vs marketplaces impersonnelles

### 8.2 Les 3 risques à neutraliser dès maintenant

1. **Activer le digital avant l'ouverture** : aujourd'hui le site est figé en coming soon, les réseaux muets — perte de 90 jours d'audience préemptable. Action M1-M8 (vague J-90 → J-30) à lancer **dès cette semaine**

2. **Faire du Personal Shopper un produit concret et démontrable** : aujourd'hui il est en backend, invisible publiquement. Risque qu'il reste un « gadget IA » non-différenciant. Action M12 + M13 + tactiques 4.3 à activer dès J0

3. **Verrouiller l'angle Giverny touristique avant qu'un concurrent ne s'y intéresse** : la zone est blanche, mais ne le restera pas. Action M19 (corners hôtels) + M27 (EN version site) + tactiques 6.2 à amorcer J0-J+120

### 8.3 Budget marketing externe estimé première année

| Vague | Postes | Budget |
|---|---|---|
| Pré-ouverture (J-90→J0) | photos pro 10-15 pièces, kit presse, kit influenceurs micro, GBP setup | 3-5 k€ |
| Ouverture (J0→J+30) | vernissage, RP nationale, impression flyers tourisme | 2-3 k€ |
| Croissance (J+30→J+180) | photos saisonnières, ateliers boutique, traduction EN, Pinterest test ads | 3-5 k€ |
| Déploiement (J+180→J+365) | rapport ESS, événement annuel, premiers ads payés (Insta/Pinterest local) | 5-10 k€ |
| **Total année 1** | | **13-23 k€** |

À ajuster selon recrutement éventuel d'un Community Manager dédié (J+90 si croissance le permet, ~25-35 k€ annuel chargé).

### 8.4 Décision marketing #1 à prendre cette semaine

> **Démarrer la production de contenu social** dès cette semaine, en activant le prompt `social_posts.md` versionné, à raison de **4 posts/sem (Insta + reels + TikTok)** générés via Claude puis humanisés par toi ou un freelance, avec un calendrier éditorial de 90 jours pré-ouverture (J-90 → J0).

Sans cette activation, le positionnement décrit dans cet audit reste sur le papier. Avec, Vintiz arrive à l'ouverture avec **300-500 inscriptions waitlist + 500-1 000 followers Insta + 2-3 articles presse locale** au minimum — ce qui transforme la première semaine d'ouverture en succès commercial mesurable.

---

## Annexe A — Calendrier éditorial type (par semaine)

Inspiré du prompt `prompts/v1/social_posts.md` versionné :

| Jour | Plateforme | Format | Sujet (rotation 4 sem) |
|---|---|---|---|
| Lundi | Insta + FB | Carrousel produit | PRODUIT_STAR : pépite de la semaine, 4-5 photos, prix, marque, pourquoi |
| Mercredi | Insta Reel + TikTok | Vidéo 30s | VALEURS : behind the scenes, sourcing, ESS, Solidarité Textiles |
| Vendredi | Insta + FB | Carrousel ou single | TÉMOIGNAGE : cliente ou Personal Shopper case study |
| Dimanche | Insta Story + FB | Story éphémère | ACTU_LOCALE : Vernon, Giverny, événement local, météo, saison |

**Volume cible J-90 → J0** : 4 posts × 12 semaines = ~48 posts pré-ouverture. À planifier en lots de 12 (1 mois) avec un freelance content/photo si besoin.

---

## Annexe B — Liens vers les autres audits

- [01_TECH_DEBT.md](./01_TECH_DEBT.md) — état du code, plan refactor 3 vagues
- [02_CONFORMITE_FINANCIERE_JURIDIQUE.md](./02_CONFORMITE_FINANCIERE_JURIDIQUE.md) — NF525, TVA régime normal, espèces, RGPD/AIPD, AI Act
- [03_SEO_POSITIONNEMENT.md](./03_SEO_POSITIONNEMENT.md) — SEO technique, concurrents zone Vernon+30min + national, mots-clés, architecture site
- [04_BRAND_REVIEW_MARKETING.md](./04_BRAND_REVIEW_MARKETING.md) — ce document
