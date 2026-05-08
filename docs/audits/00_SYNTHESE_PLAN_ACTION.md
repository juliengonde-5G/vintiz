# Synthèse audits Vintiz & Plan d'action en 3 phases

> **Auteur** : Claude (synthèse des 4 audits livrés)
> **Date** : 2026-05-08
> **Contexte** : ouverture boutique Vernon visée **septembre 2026** (≈ J0 = 2026-09-01, à confirmer avec Julien)
> **Date du jour** : 2026-05-08 → **J-115 environ avant ouverture**
> **Périmètre** : consolidation des 4 audits livrés en `docs/audits/`

---

## Synthèse exécutive

Les 4 audits convergent sur le même diagnostic : **Vintiz est mature techniquement, prêt commercialement, mais en retard d'activation publique**. Le code, l'IA, le POS et la conformité sont à 80-90 % en place. Le site, les réseaux, la narrative et le SEO sont à 30 %.

**Le seul vrai risque entre maintenant et l'ouverture** : ne pas activer les 4-5 chantiers P0 conformité + SEO + marketing dans les 115 prochains jours.

### Les 4 forces consolidées

1. **Stack technique B+** — monorepo FastAPI + Next.js mature, NF525 implémenté (chaîne SHA-256 + Z reports verrouillés + export DGFiP), RGPD complet (export Article 20, droit à l'oubli, DPO), 35 migrations Alembic propres
2. **Personal Shopper IA propriétaire** — unique sur le marché FR 2nde main au 05/2026 (Younzee = software-only sans stock, Vestiaire Collective = pas conversationnel)
3. **Identité Sauge Néo v3** — charte distinctive cohérente (palette teal #0B7A6A, Fraunces typeface, ton éditorial versionné dans les prompts Claude)
4. **Position de marché claire** — premium curé 50-300 €, achat ferme uniquement, régime normal TVA (B2B-friendly), zone Giverny vide concurrentiellement

### Les 4 trous critiques à boucher avant ouverture

1. **Conformité** — attestation NF525 non signée, régime normal TVA non auditable dans le code (`tva_rate` absent), plafond espèces 1000 € non validé, profilage Personal Shopper sans consent explicite, AIPD absente
2. **SEO** — `/account` indexable, NAP incomplet (pas de tél, pas d'email, pas de page `/contact`), aucune page publique `/personal-shopper`
3. **Marketing** — site en coming soon depuis avril 2026, réseaux muets malgré prompts Claude prêts, zéro audience préemptée
4. **Tech debt** — 2 god-modules ralentissent la vélocité (`apps/web/src/app/pos/page.tsx` 2314 L, `apps/api/app/api/admin/router.py` 1779 L), 3 services critiques sans tests dédiés

### Les 3 deadlines à respecter

| Date | Échéance | Sujet |
|---|---|---|
| **2026-08-02** | AI Act art. 50 applicable | disclaimer permanent UI Personal Shopper + marquage machine-readable des sorties IA |
| **2026-08-31** | Fin tolérance NF525 | régime cible : certificat accrédité OU attestation éditeur conforme |
| **~2026-09-01** | Ouverture boutique Vernon | tous les P0 conformité, SEO, marketing pré-ouverture doivent être faits |

---

## Plan d'action en 3 phases

### Phase 1 — Mise en conformité & préparation à l'ouverture (mai → août 2026, ~115 jours)

**Objectif** : tout ce qui doit être prêt avant ouverture. Aucun report possible sur les sujets conformité.

**Effort total** : ~50-60 jours-personnes (parallélisables sur 4 mois)

**Budget externe estimé** : 5-9 k€ (revue avocat ~1 k€ + photos pro 10-15 pièces ~1,5 k€ + kits presse/influenceurs ~1,5-3 k€ + presse locale ~1 k€ + traduction/setup divers ~1 k€)

#### 1.1 Conformité (P0 critiques avant ouverture)

| # | Action | Effort | Owner | Deadline |
|---|---|---|---|---|
| C1 | **Signer attestation éditeur NF525** (modèle prêt `docs/COMPLIANCE_NF525.md`) | 1 j | Julien | mai |
| C2 | **TVA régime normal** : ajouter `tva_rate` sur `Product` + `TransactionItem`, créer `app/services/tva_service.py` `compute_line_totals()`, footer ticket HT/TVA/TTC + N° TVA intracom | 1-2 sem | EC + dev | juin |
| C3 | **Validateur plafond espèces 1000 €** : `app/services/cash_payment_validator.py` + intégration POS + audit log override | 1 sem | dev | juin |
| C4 | **Écran consentement explicite Personal Shopper** + endpoint init-consent + re-prompt membres existants + section confidentialité enrichie | 1-2 sem | UX + dev | juin |
| C5 | **AIPD via outil PIA CNIL** (finalité, base légale, données, durées, risques) | 1 sem | DPO + Julien | juillet |
| C6 | **Revue avocat** : CGV + politique confidentialité + mentions légales | ½ j externe | avocat | mai-juin |
| C7 | **Hashage email/phone dans `audit.py:_redact()`** | 3-5 j | dev | juin-juillet |
| C8 | **Redaction `_redact_sumup_error()`** avant persistance logs | 1 j | dev | juin-juillet |
| C9 | **Disclaimer permanent UI shopper + marquage sorties IA** (AI Act art. 50) | 2 j | UX + dev | **avant 2026-08-02** |

#### 1.2 SEO (P0 débloquants avant ouverture)

| # | Action | Effort | Owner | Deadline |
|---|---|---|---|---|
| S1 | **Créer `/contact`** + ajouter `telephone` + `email` + `contactPoint` dans JSON-LD `ClothingStore` | ½ j | dev | mai |
| S2 | **`/account` et `/account/*` en `noindex`** + `Disallow: /account` dans `app/robots.ts` | 1 h | dev | mai |
| S3 | **Créer `/personal-shopper`** (page vitrine publique 400-600 mots, H1 keyword, JSON-LD `Service`) | 1 j | dev + copy | mai-juin |
| S4 | **Raccourcir meta description home à ~155 char** + refondre H1 pour inclure « Vintiz » + « Vernon » | 1 h | dev | mai |
| S5 | **Créer Google Business Profile** + valider Google Search Console + ajouter lien GBP au `sameAs` | ½ j | Julien + dev | mai |
| S6 | **Créer `/a-propos`** (qui est Vintiz, ESS, Solidarité Textiles, narrative impact) | 1 j | copy + dev | juin |
| S7 | **Créer `/produits`** vitrine 10-15 pièces avec JSON-LD `Product` (photos pro requises) | 2 j | dev + photo | juillet |
| S8 | **Image OG dédiée 1200×630** (façade ou ambiance) + `og:image` `twitter:image` | ½ j | designer + dev | juin |
| S9 | **Filtrer sitemap** : exclure pages `noindex` + vraies dates `lastmod` + nettoyer canonical doublonné | ½ j | dev | juin |
| S10 | **+200 mots éditoriaux home** (« Pourquoi Vintiz à Vernon ») | ½ j | copy + dev | juin |
| S11 | **Page 404 personnalisée** (`app/not-found.tsx` brandée Sauge Néo) | ½ j | dev | juin |
| S12 | **Apple Touch Icon + manifest.json PWA** | ½ j | dev | juillet |

#### 1.3 Tech debt (Vague 1 quick wins + amorces refactor)

| # | Action | Effort | Owner | Deadline |
|---|---|---|---|---|
| T1 | **Quick wins** : déplacer `import logging` en haut de `pos.py`, ajouter `logger.warning/error` dans `merchandising.py`, doc rotation `SECRET_KEY` dans `DEPLOIEMENT.md` | ½ j | dev | mai |
| T2 | **Centraliser prompts IA** dans `apps/api/app/core/prompts.py` + registry version | 1 j | dev | juillet |
| T3 | **Test régression** `test_chain_integrity_after_db_tampering()` dans `test_nf525_chain.py` | 1 j | dev | juillet |
| T4 | **3 tests services critiques** : `test_merchandising_score.py`, `test_wallet_pass.py`, `test_sumup_polling.py` | 1,5 j | dev | juillet |

#### 1.4 Marketing pré-ouverture

| # | Action | Effort | Owner | Deadline |
|---|---|---|---|---|
| M1 | **Démarrer programme posts sociaux Claude** (4 posts/sem via prompt versionné `social_posts.md`) Insta + FB + TikTok | démarrage : ½ j ; récurrent : 2-3 h/sem | freelance ou Julien | démarrer mai |
| M2 | **Lancer waitlist newsletter** avec teasing « Vintiz ouvre en septembre — 50 pts cadeau pour les 100 premières inscriptions » | ½ j | dev + copy | mai |
| M3 | **Pitcher presse locale** Vernon Direct + Paris-Normandie + Media Normandie (interview Julien fondateur) | 2-3 j | Julien | juin |
| M4 | **Préparer kit influenceurs micro Normandie** (10-15 cibles 5k-50k followers) | 2 j | Julien + designer | juillet |
| M5 | **Préparer pack « Premier shopping Vintiz »** (welcome offer 10 % + accès PS anticipé) | 1 j | dev + copy | août |
| M6 | **Approcher Office Tourisme Vernon + Fondation Monet Giverny** — accord de principe | 2-3 j | Julien | juin-juillet |
| M7 | **Photos pro 10-15 pièces vitrine** (cohérence Sauge Néo, modèles si possible) | 2 j shoot + post-prod | photographe externe | juillet |
| M8 | **Renforcer compte Insta** : bio, lien, highlights (« notre histoire », « Personal Shopper », « Solidarité Textiles ») | 1 j | freelance ou Julien | mai |

#### KPIs cibles fin de Phase 1 (J0)

| KPI | Cible |
|---|---|
| Inscriptions waitlist newsletter | 300-500 |
| Followers Insta | 500-1 000 |
| Followers TikTok | 200-500 |
| Articles presse locale | 2-3 |
| GBP créé + validé GSC | ✓ |
| Pages `/contact`, `/a-propos`, `/personal-shopper`, `/produits` live | ✓ |
| Conformité P0 close | ✓ tous |
| Score SEO estimé | ≥ 85/100 |
| Site EN-ready | partiellement (page accueil/PS facultatif) |

---

### Phase 2 — Ouverture & consolidation (septembre → décembre 2026, ~4 mois)

**Objectif** : ouvrir, générer du trafic, premiers achats, premiers avis Google, premiers cas clientes Personal Shopper.

**Effort total** : ~30-40 jours-personnes répartis sur 4 mois

**Budget externe estimé** : 5-8 k€ (vernissage 1-2 k€ + RP nationale 1-2 k€ + photos saisonnières 1-2 k€ + ateliers boutique 1 k€ + premiers tests Insta/Pinterest ads 1-2 k€)

#### 2.1 Ouverture commerciale (J0 → J+30)

| # | Action | Effort | Deadline |
|---|---|---|---|
| O1 | **Inauguration boutique** (vernissage 50 pers, presse locale, micro-influenceurs) | 1 j | semaine ouverture |
| O2 | **Activer Wallet pass Apple/Google** (signing pluggé) | 2 j | J0 |
| O3 | **Activer email anniversaire (P4-008) + nouvelles arrivées hebdo (P4-009)** | 1 j | J0 |
| O4 | **Activer Personal Shopper IA publiquement** avec écran consent (déjà C4) | déjà fait | J0 |
| O5 | **POS imprime QR avis Google** sur ticket (fonction simple) | ½ j | J0 |
| O6 | **Activer Vinted Pro** (vitrine secondaire 30-50 pièces) | 1 j initial + récurrent | J+15 |
| O7 | **Promo soft « 1er achat = adhésion offerte »** (mode 3 du flag fidélité) | ½ j | J0 |
| O8 | **Pitcher presse mode nationale** (FashionNetwork, FashionUnited, Le Figaro Madame, ELLE) — angle « Personal Shopper IA + 2nde main + ESS Normandie » | 3-4 j | J+15 → J+30 |
| O9 | **Lancer 1ère capsule mensuelle « Les pépites de Vernon »** (10 pièces curées + narrative) | 2 j | J+15 |

#### 2.2 SEO Phase 2

| # | Action | Effort | Deadline |
|---|---|---|---|
| S13 | **Restreindre JSON-LD `ClothingStore` à la home**, mettre `Organization` ailleurs | ½ j | octobre |
| S14 | **Ajouter `aggregateRating`** dans JSON-LD dès 5+ avis Google | 1 h | dès atteint |
| S15 | **Audit fonts woff2 préchargées** (sub-set, lazy familles secondaires) | ½ j | octobre |

#### 2.3 Tech debt Vague 2 (refactor moyens)

| # | Action | Effort | Deadline |
|---|---|---|---|
| T5 | **Splitter `apps/api/app/api/admin/router.py`** en sous-modules (`admin/users.py`, `admin/offers.py`, `admin/zones.py`, `admin/sumup_terminals.py`, `admin/receipt_templates.py`, `admin/scoring.py`) | 2 j | octobre |
| T6 | **Extraire `<POSCart>`, `<POSPaymentModal>`, `<POSLoyaltyPanel>`** + hooks `usePOSCart()`, `usePOSPayment()` depuis `apps/web/src/app/pos/page.tsx` | 2 j | novembre |
| T7 | **Banner cookies vérifié visible** + accessible | 1 j | octobre |

#### 2.4 Conformité Phase 2 résiduelle

| # | Action | Effort | Deadline |
|---|---|---|---|
| C10 | **Procédure intervention humaine PS** documentée + audit log de chaque reco | 2 j | octobre |
| C11 | **Module reporting espèces > 10 000 €/mois** (anticipation COSI TRACFIN) | 2 j | octobre |
| C12 | **TTL + cleanup cron embeddings** + suppression dans `hard_delete()` | 3 j | novembre |
| C13 | **Diagramme de flux carte PCI-DSS** validé par SumUp + soumission **SAQ B-IT signé** | 1 j | décembre (annuel) |

#### 2.5 Marketing croissance (J+30 → J+90)

| # | Action | Effort | Récurrence |
|---|---|---|---|
| M9 | **Capsules mensuelles thématiques** (Halloween, Noël, Saint-Valentin) | 2 j/mois | mensuel |
| M10 | **Blog `/journal`** — 1 article SEO longue traîne par mois | 1-2 j/article | mensuel |
| M11 | **Email J+30 / J+90 / J+180** post-1er achat (réactivation) | 2 j initial | flow auto |
| M12 | **Programme parrainage** : Julie parraine Léa → 50 pts chacune | 2 j | J+60 |
| M13 | **Ouvrir comptes Pinterest + LinkedIn** | 1 j initial + récurrent | J+30 |
| M14 | **Atelier mensuel en boutique** : « composer son dressing slow fashion » | 1 j prép | mensuel |
| M15 | **2 cas clientes Personal Shopper** (testimonials + photos) | 3-5 j | J+60 et J+90 |

#### KPIs cibles fin de Phase 2 (J+120)

| KPI | Cible |
|---|---|
| Cartes fidélité créées | 200-400 |
| Avis Google (note ≥ 4,5/5) | 40-80 |
| Membres ayant activé PS | 50 % des membres |
| CTR sur recos PS | > 20 % |
| Sell-through stock 90 j | > 60 % |
| Followers Insta | 1 500-3 000 |
| Newsletter abonnés | 800-1 500 |
| Articles blog publiés | 3-4 |
| Articles presse mode | 1-2 |
| Tech debt P2 | 50 % done |

---

### Phase 3 — Croissance & déploiement régional (janvier → septembre 2027, ~9 mois)

**Objectif** : asseoir l'audience, capter le tourisme international Giverny, décider du 2e point de vente, scaler la marque.

**Effort total** : ~50-80 jours-personnes répartis sur 9 mois

**Budget externe estimé** : 8-15 k€ (traduction EN ~2 k€ + photos saisonnières 2 k€ + événement annuel 3-5 k€ + ads ciblés 2-4 k€) — hors recrutement Community Manager (~25-35 k€/an chargé si validé) ; hors ouverture 2e PdV (40-100 k€ si décidée fin 2027)

#### 3.1 Tourisme & international (janvier → mars 2027)

| # | Action | Effort |
|---|---|---|
| TI1 | **Version EN du site** (`/`, `/personal-shopper`, `/contact`, `/a-propos`, `/produits` minimum) | 5-7 j |
| TI2 | **Partenariats hôtels Vernon-Giverny** (Hôtel d'Évreux, Domaine de Sens, Manoir des Impressionnistes) — corners Vintiz / sélection éditoriale | 5-10 j sur 6 mois |
| TI3 | **Flyers « Day trip Vernon-Giverny »** distribués hôtels + OT | 2 j |
| TI4 | **Sélection « Made in France iconic »** mise en avant pour touristes (Sandro / Maje / Sézane / Polène / Le Tanneur) | 1-2 j |
| TI5 | **Trip Advisor** + Google Maps photos premium boutique | 1 j |
| TI6 | **Détaxe touristes hors UE** validée avec EC (Vintiz est en régime normal TVA → éligible) | 1-2 j |
| TI7 | **Co-marketing boutique Giverny** (galerie d'art, salon de thé) — passport touriste 10 % chez chaque partenaire | 2-3 j |

#### 3.2 SEO Phase 3

| # | Action | Effort |
|---|---|---|
| S16 | **Catégories SEO dynamiques stock-driven** (« robe Sandro occasion », « manteau Sézane seconde main ») | 3-5 j |
| S17 | **5 articles blog longue traîne** complémentaires (suite des 4 démarrés en Phase 2) | 5-10 j sur 6 mois |
| S18 | **Backlinks** : Vernon Direct, Media Normandie, OT Vernon, FashionNetwork, FashionUnited | 5 j sur 6 mois |
| S19 | **Position SEO « friperie Vernon » / « seconde main Vernon »** : top 3 visé | mesure mensuelle |
| S20 | **Position SEO « personal shopper IA »** : top 5-10 visé | mesure mensuelle |

#### 3.3 Tech debt Vague 3 (structurel)

| # | Action | Effort |
|---|---|---|
| T8 | **Splitter `apps/web/src/app/settings/page.tsx`** en pages tab-routées (`/settings/sumup`, `/settings/email`, `/settings/hardware`) | 2 j |
| T9 | **Refactor `apps/api/app/api/pos/router.py`** en sous-routers (`pos_transactions.py`, `pos_payments.py`, `pos_drawer.py`) | 2 j |
| T10 | **Storybook composants partagés** (`design-package/`) consommé par web + site | 2-3 j |
| T11 | **Migration SumUp polling → WebSocket** si bottleneck observé | 3 j conditionnel |

#### 3.4 Conformité Phase 3

| # | Action | Effort |
|---|---|---|
| C14 | **Décision NF525 long terme** : rester sur attestation éditeur OU lancer certification accréditée (12-25 k€, 6-9 mois) | décision stratégique |
| C15 | **SAQ B-IT annuel** signé à SumUp | 1 j (récurrent) |

#### 3.5 Brand & déploiement (avril → septembre 2027)

| # | Action | Effort |
|---|---|---|
| B1 | **Étude faisabilité 2e point de vente** (Rouen ou Évreux) — analyse trafic, sourcing, équipe | 5-10 j |
| B2 | **Si validé : ouverture 2e boutique** « Vintiz Rouen » ou « Vintiz Évreux » | 3-6 mois |
| B3 | **Renforcer partenariat Le Relais** (point de collecte Vintiz boutique) | 2-3 j |
| B4 | **Premier rapport d'impact ESS** publié (kg revalorisés, % flux SoTex vendu, CA reversé) | 3-5 j |
| B5 | **Recrutement Community Manager / Content Creator** dédié (si croissance le permet) | recrutement |
| B6 | **Offre Personal Shopper Premium** payante (accès illimité, sessions live, cadeau anniversaire) | 5-7 j |
| B7 | **Premier événement annuel « Les Talents de Vintiz »** (clientes ambassadrices, presse, influenceurs) | 5-7 j |
| B8 | **Insta Shopping + TikTok Shop** (catalogue shoppable mobile) | 3-5 j |

#### KPIs cibles fin de Phase 3 (J+365)

| KPI | Cible |
|---|---|
| Membres fidélité | 1 200-2 000 |
| Membres Gold | 80-150 |
| Taux de réachat 6 mois | > 50 % |
| Net Promoter Score | > 50 |
| Avis Google cumulés | 200-400 (note ≥ 4,5) |
| Followers Insta | 8 000-15 000 |
| Newsletter abonnés | 4 000-7 000 |
| Trafic organique mensuel | 8 000-15 000 visiteurs |
| Position SEO « friperie Vernon » | top 3 |
| Position SEO « personal shopper IA » | top 5-10 |
| Mentions presse cumulées | 15-25 |
| Backlinks domaines référents | 30-50 |
| Rapport ESS annuel | 1 publié |
| 2e PdV | go/no-go tranchée |

---

## Synthèse des dépendances critiques

### Chemin critique (ne peut pas glisser)

```
mai 2026 (J-115)                           sept 2026 (J0)         août 2027 (J+365)
   │                                            │                       │
   ▼                                            ▼                       ▼
   ├── C1 Attestation NF525 ──────────┐         │                       │
   ├── C2 TVA tva_rate ────────────┐  │         │                       │
   ├── C3 Plafond espèces ─────────┤  │         │                       │
   ├── C4 Consent PS explicite ────┤  │         │                       │
   ├── C5 AIPD ────────────────────┤  ──────────► OUVERTURE BOUTIQUE     │
   ├── C6 Avocat ───────────────────┤  │         │                       │
   ├── S1 /contact ────────────────┤  │         │                       │
   ├── S2 /account noindex ────────┤  │         │                       │
   ├── S3 /personal-shopper ───────┤  │         │                       │
   ├── S5 GBP + GSC ───────────────┤  │         │                       │
   ├── M1 Posts sociaux Claude ────┤  │         │                       │
   ├── M2 Waitlist newsletter ─────┤  │         │                       │
   └── C9 AI Act art. 50 ──────────────► 2026-08-02 deadline             │
                                       │         │                       │
                                       │         ├── O1-O9 Ouverture     │
                                       │         ├── M9-M15 Croissance   │
                                       │         └── T5-T7 Refactor mid  │
                                       │                  │              │
                                       │                  └──────────────►
                                       │                                  │
                                       │                  TI1-TI7 Tourisme│
                                       │                  S16-S20 SEO++   │
                                       │                  T8-T11 Tech V3  │
                                       │                  B1-B8 Déploi.  ─►
```

### Dépendances inter-actions

- **C9 (AI Act art. 50)** dépend de **C4 (consent PS)** — il faut que le PS soit publiquement utilisé pour avoir un disclaimer pertinent
- **S5 (GBP)** dépend de **S1 (`/contact`)** — Google exige NAP cohérent entre site et fiche
- **O1 (vernissage)** dépend de **M3 (presse locale)** + **M4 (kit influenceurs)** — pour avoir du monde
- **B1 (étude 2e PdV)** dépend des KPIs Phase 2 (sell-through, marge, NPS) — ne lancer que si économie unitaire validée

---

## Tableau de bord consolidé

### Par sévérité

| Sévérité | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| **Critique (bloquant ouverture)** | C1, C2, C3, C4, C5, S1, S2, S3, S5, C9 (deadline AI Act 02/08) | — | — |
| **Élevée (devrait être fait)** | C6, C7, C8, S4, S6, S7, S8, S9, S10, S11, M1, M2, M3 | O1-O9, S13, T5, T6, C10, C11, M9, M10 | TI1-TI7, S16, S17, S18 |
| **Moyenne** | T1, T2, T3, T4, S12, M4-M8 | C12, C13, S14, S15, T7, M11-M15 | T8-T11, B1-B8, S19, S20 |
| **Stratégique** | — | — | C14 (décision certif NF525) |

### Par owner

| Owner | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| **Julien (fondateur)** | C1, C5, C6, M3, M4, M6, M7, M8, S5 | O1, O8 | B1, B2, B5, B7, C14 |
| **Dev backend** | C2, C3, C4, C7, C8, T2, T3, T4 | T5, C10, C11, C12, C13 | T9, T10, T11 |
| **Dev frontend** | S1, S2, S3, S4, S6, S7, S8, S9, S10, S11, S12, T1 | T6, T7, S13, S14, S15 | T8, B6, B8 |
| **Designer / copy** | S6, S7, S8, S10, M1, M2, M5 | M9, M10, O9 | TI4, S17 |
| **DPO / juridique** | C5, C9 | — | — |
| **Externe (avocat, photographe, presse, OT)** | C6, M3, M4, M7 | O1, O8 | B7, TI2 |
| **Comptable / EC** | C2 (validation taux), TI6 (détaxe) | — | — |

### Effort consolidé

| Phase | Durée | Effort dev | Effort marketing | Budget externe |
|---|---|---|---|---|
| **Phase 1 — Pré-ouverture** | mai-août 2026 (~115 j) | 25-35 j | 15-20 j | 5-9 k€ |
| **Phase 2 — Ouverture & consolidation** | sept-déc 2026 (~120 j) | 15-20 j | 15-20 j | 5-8 k€ |
| **Phase 3 — Croissance & déploiement** | jan-sept 2027 (~270 j) | 25-40 j | 25-40 j | 8-15 k€ (hors 2e PdV) |
| **Total année 1+** | 17 mois | **65-95 j** | **55-80 j** | **18-32 k€** |

---

## Top 10 actions à démarrer cette semaine

Si tu ne devais retenir que 10 actions à démarrer dans les 7 prochains jours, voici la liste consolidée :

| # | Action | Pourquoi maintenant | Effort cette semaine |
|---|---|---|---|
| 1 | **Signer attestation éditeur NF525** (modèle prêt) | Bloquant ouverture, risque 7 500 € | 1 j |
| 2 | **Demander rdv expert-comptable** sur régime TVA + détaxe touristes | Bloquant C2, lead time EC | 1 h |
| 3 | **Mettre `/account` en `noindex`** + `Disallow: /account` dans `robots.ts` | Action S2, 1 h, débloque KO-01 | 1 h |
| 4 | **Créer Google Business Profile + GSC** | Lead time validation Google ~7-14 j | ½ j |
| 5 | **Démarrer programme posts sociaux Claude** (4 posts/sem) | Audience ne se construit pas en 1 mois | ½ j setup |
| 6 | **Activer la waitlist newsletter** avec teasing | Captation J-115 → J0 | ½ j |
| 7 | **Pitcher Vernon Direct + Paris-Normandie** | Lead time presse locale 4-8 sem | 2-3 h |
| 8 | **Approcher Office Tourisme Vernon + Fondation Monet** | Lead time partenariat 8-12 sem | 2-3 h |
| 9 | **Quick wins tech debt** : `import logging` `pos.py`, logs `merchandising.py`, doc `SECRET_KEY` | 30 min, observabilité immédiate | ½ j |
| 10 | **Demander devis avocat** pour revue CGV / confidentialité / mentions légales | Lead time avocat 2-4 sem | 1 h |

→ **Effort total cette semaine** : ~3-4 jours-personnes répartis. Faisable.

---

## Annexe A — Liens vers les 4 audits sources

- [01_TECH_DEBT.md](./01_TECH_DEBT.md) — état du code, plan refactor 3 vagues (380 lignes)
- [02_CONFORMITE_FINANCIERE_JURIDIQUE.md](./02_CONFORMITE_FINANCIERE_JURIDIQUE.md) — NF525, TVA régime normal, espèces, RGPD/AIPD, AI Act, comparaison concurrents POS (700+ lignes)
- [03_SEO_POSITIONNEMENT.md](./03_SEO_POSITIONNEMENT.md) — SEO technique, concurrents zone Vernon+30min + national, mots-clés, architecture site (700 lignes)
- [04_BRAND_REVIEW_MARKETING.md](./04_BRAND_REVIEW_MARKETING.md) — positionnement, value proposition, plan marketing 12 mois, force du Personal Shopper (750 lignes)

## Annexe B — Décisions structurantes Vintiz (référentiel)

Ces 2 choix structurants ont été pris pendant les audits et sont à respecter dans toute analyse future :

1. **Régime normal de TVA à 20 %** (pas le régime de la marge sur biens d'occasion)
2. **Achat ferme uniquement** (pas de dépôt-vente)

Ces choix sont consignés dans la mémoire projet `vintiz_business_model.md` et déterminent : la com', le code POS, les keywords SEO, le positionnement marketing.
