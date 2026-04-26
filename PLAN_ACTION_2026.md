# Plan d'action Vintiz — Évolutions 2026

> **Source** : consolidation des audits `AUDIT_VINTIZ_2026.md` (V1) et `AUDIT_VINTIZ_DELTA_V2.md` (triangulation).
> **Branche** : `claude/audit-action-plan-GHnWJ`
> **Date** : 26 avril 2026
> **Cible** : ouverture qualifiée Frip & Co Vernon — septembre 2026.

---

## Synthèse

- V1 = vision (event store, pgvector, Personal Shopper v2, NF525, 6 prompts système, 5 personas).
- V2 = corrections après triangulation avec 3 audits parallèles ayant lu le code : plusieurs modules supposés absents existent déjà (SEO complet, `ai_vision.py`, `ai_mapping.py`, `fiscal.py`, coords zones en %), mais 3 bugs scoring + multi-photos + split payment + retours sont confirmés manquants.
- Approche : **Phase 0 ground-truth d'abord**, puis P0 → P4 selon le tableau ci-dessous.

---

## Phase 0 — Audit ground-truth du code (3-5 jours)

Avant toute implémentation, vérifier dans `apps/api/app/` ce qui existe vraiment vs ce que les audits supposent. Livrable : `AUDIT_GROUND_TRUTH.md` qui marque chaque ticket "à implémenter / à enrichir / déjà fait".

| # | Point à vérifier | Fichier cible attendu |
|---|---|---|
| 1 | Conformité NF525 — chaînage SHA-256 réel ? | `services/fiscal.py` |
| 2 | Cron scoring "1er mercredi" — actif ? | scheduler + `services/scoring_service.py` |
| 3 | `ai_vision.py` — quels attributs réellement extraits ? | `services/ai_vision.py` |
| 4 | `ai_mapping.py` — recos zone branchées en UI ? | `services/ai_mapping.py` |
| 5 | Module SEO — couverture endpoints ? | `routes/seo.py` |
| 6 | Bouton "Imprimer étiquette" — branché ? | `apps/web` + `sato_service.py` |
| 7 | Modèle Product — `photo_url` unique ou multi-photos ? | `models/product.py` |
| 8 | Flux retour/avoir — endpoint refund existant ? | `routes/pos.py` |
| 9 | `audit.py` — quels mouvements tracés ? | `services/audit.py` |
| 10 | Multi-utilisateur cashier + PIN ? | `models/user.py` |
| 11 | Schema events / pgvector déjà en place ? | migrations Alembic |
| 12 | Markdown engine (`markdown_rules` table) ? | `models/` + cron |

---

## Phase 1 — P0 bloquants ouverture Vernon ✅ CLÔTURÉE (26 avril 2026)

> **Statut** : tous les tickets backend + UI sont livrés. Détail complet dans
> [`PHASE_1_CLOTURE.md`](./PHASE_1_CLOTURE.md). Seules deux actions humaines
> restent (signature attestation NF525 §4 + test cycle complet D-30).

| ID | Sujet | Source | Type | État |
|---|---|---|---|:---:|
| P1-001 | Conformité NF525 (chaînage SHA-256, export DGFiP, attestation éditeur) | V1 | Légal bloquant | ✅ |
| P1-002 | Multi-utilisateur + PIN cashier sur POS | V1 | Légal/audit | ✅ |
| P1-007 | RGPD-by-design CRM (consentement, droit oubli, export JSON) | V1 | Légal bloquant | ✅ |
| P1-008 | Multi-photos produit (modèle `ProductPhoto` + carousel + upload binaire) | V2 | Fonctionnel | ✅ |
| P1-009 | Split payment (mixte espèces+CB+chèque+avoir) | V2 | Fonctionnel | ✅ |
| P1-010 | Flux retour / avoir POS + ticket retour 80mm | V2 | Fonctionnel | ✅ |
| P1-013 | Auto-population AuditLog via SQLAlchemy event listeners | V2 | Légal/audit | ✅ |
| P1-014 | `cashier_id` traceable sur Transaction / CashDrawer / ZReport | V2 | Légal/audit | ✅ |
| P1-015 | Export XML/JSON DGFiP (clôt P1-001) | V1 | Légal bloquant | ✅ |
| P1-016 | `Client.avoir_credit` + ledger `AvoirTransaction` | V2 | Fonctionnel | ✅ |
| P2-009 | **BUG** scoring : confirmé faux positif (formule mathématiquement correcte) | V2 | Correction | ✅ Fermé |
| P2-010 | **BUG** `category_trend` statique → reporté Phase 2 (avec ai_trend) | V2 | Correction | ⏭ Ph. 2 |

---

## Phase 2 — Fondations data + différenciation IA (4-6 semaines)

Sans la couche événementielle, le Personal Shopper et le Booster IA plafonnent.

| ID | Sujet | Source |
|---|---|---|
| P1-003 | Schéma `events` PG partitionné mensuel + instrumentation 16 event_types | V1 |
| P1-004 | pgvector + tables `features.product_embeddings` et `features.customer_taste_profiles` | V1 |
| P1-005 | Mode offline POS (Service Worker + IndexedDB + replay) | V1 |
| P1-006 | Cycle de vie produit explicite (RECEIVED → SORTED → TAGGED → DISPLAYED → SOLD/DONATED/RETURNED_TO_SORTING) | V1 |
| P2-015 | Modèle `Batch` réception cartons centre de tri | V2 |
| P3-007 | Logique retour automatique centre de tri (cron + scoring) | V2 |
| P2-001 | Pipeline embeddings produits (Claude Vision + encoder texte) | V1 |
| P2-002 | Pipeline `customer_taste_profiles` (centroïde pondéré) | V1 |
| P2-003 | Endpoint Personal Shopper v2 (similarité cosinus + diversification + Claude Haiku) | V1 |
| P2-004 | Cold start onboarding (5 photos style + quiz < 2 min) | V1 |
| P2-005 | Vue plan boutique SVG `/admin/store-plan` | V1 |
| P2-006 | Reco placement automatique zone à l'étiquetage | V1 |
| P2-007 | Recommandation vitrine hebdomadaire (cron lundi 6h) | V1 |
| P2-008 | Recherche "Où est cette pièce ?" (scan → zone exacte) | V1 |

---

## Phase 3 — Enrichissement Booster + visibilité (3-4 semaines)

| ID | Sujet | Source |
|---|---|---|
| P3-001 | Markdown engine déclaratif (table `markdown_rules` + UI Camille + cron nocturne) | V1 |
| P3-002 | Tag couleur sur étiquette (vert/jaune/orange/rouge selon cycle de vie) | V1 |
| P2-011 | Enrichir score photos (confiance Vision + nombre de photos) | V2 |
| P2-012 | Modèle `BrandTier` en DB + UI admin marques (vs liste hardcodée) | V2 |
| P2-013 | Enrichir `ai_vision.py` avec taxonomie styles/occasion/pattern + détection défauts | V2 |
| P3-003 | Module visibilité = enrichissement du SEO existant (mentions Insta/TikTok, génération posts IA, GBP avis) | V2 |
| P3-004 | Calendrier éditorial RS (4 posts/semaine via prompt §7.4) | V1 |
| P3-005 | Persistance historique SEO (`SEOSnapshot`) + graphe d'évolution | V2 |
| P3-006 | Import CSV inventaire en masse | V2 |
| P3-008 | Historique mouvements stock (event listener SQLAlchemy) | V2 |

---

## Phase 4 — KPIs avancés + UX polish (2-3 semaines)

| ID | Sujet | Source |
|---|---|---|
| P4-001 | KPIs retail standards (sell-through, GMROI, DOH, AIT, CA/m²/mois) | V1 |
| ~~P4-002~~ | ~~Reporting ESS dédié~~ — **OBSOLETE** (audit 2026-05 §2.1.c) : page UI retirée, calcul backend conservé pour exports ad-hoc | V1 |
| P4-003 | Email automation Brevo (welcome, J+30 inactif, anniversaire, J+60 Gold inactif) | V1 |
| P4-004 | Apple/Google Wallet (`.pkpass` + push solde points) | V1 |
| P4-005 | Réservation 48h site vitrine + zone "Réservés" en btq | V1 |
| P4-006 | Mobile-first dashboard manager | V1 |
| P4-007 | Segmentation RFM clients (job mensuel) | V2 |
| P4-008 | Offre anniversaire automatique (cron quotidien) | V2 |
| P4-009 | Notification "Nouvelles arrivées" hebdo (si email_optin) | V2 |
| P4-010 | Badge "Boost IA" caisse pour produits Hot | V2 |
| P2-014 | Drag-and-drop sur plan boutique SVG | V2 |
| P1-011 | Lier bouton "Imprimer étiquette" à `sato_service.py` (si confirmé non branché) | V2 |

---

## Tickets bibliothèque de prompts (Phase 2-3)

À créer dans `apps/api/prompts/v1/` (versionnés Git) :

| Fichier | Usage |
|---|---|
| `personal_shopper.md` | Endpoint reco cliente (V1 §7.1) |
| `personal_shopper_sms.md` | Variante SMS/WhatsApp (V2 §6.2) |
| `window_display.md` | Reco vitrine hebdo (V1 §7.2) |
| `pricing_decision.md` | Audit pricing pièce limite (V1 §7.3) |
| `social_posts.md` | 4 posts RS/semaine (V1 §7.4) |
| `photo_intake.md` | Analyse photo intake — enrichi taxonomie V2 (V1 §7.5 + V2 §6.1) |
| `zone_suggestion.md` | Suggestion zone mise en rayon (V1 §7.6) |

Chaque appel LLM doit :
- Logger dans `events.event_log` avec `algo_version`, latence, tokens.
- Avoir un fallback déterministe (modèle "simulation SumUp" en pattern).

---

## Effort estimé

| Phase | Durée | Échéance recommandée |
|---|---|---|
| Phase 0 — Ground-truth | 3-5 jours | Semaine du 4 mai 2026 |
| Phase 1 — P0 bloquants | 5-6 semaines | Mai-juin 2026 |
| Phase 2 — Fondations IA | 4-6 semaines | Juin-juillet 2026 |
| Phase 3 — Booster + visibilité | 3-4 semaines | Septembre 2026 |
| Phase 4 — KPIs + polish | 2-3 semaines | Octobre 2026 |
| **Total** | **14-19 semaines** | **Ouverture qualifiée septembre 2026** |

---

## Méthodologie d'exécution

Pour chaque ticket :

1. **Lire d'abord le code existant** dans la zone concernée (les audits l'ont rappelé : la doc retarde sur le code).
2. **Mettre à jour `CLAUDE.md`** si la fonctionnalité existe déjà mais n'est pas documentée.
3. **Implémenter** uniquement si la fonctionnalité manque réellement.
4. **Tester** : `scripts/seed_data.py` doit rester vert après chaque ticket.
5. **Une PR par phase**, sous-tickets en commits dédiés.

À D-30 jours de l'ouverture : session de revue dédiée — cycle complet d'usage simulé (Sophie ouvre la caisse, traite 20 transactions de tous types incluant retours et split payment, ferme la caisse, génère le rapport ESS du jour). Si ce cycle passe sans intervention humaine, le produit est prêt.

---

## Documents associés à produire

| Fichier | Statut | Quand |
|---|---|---|
| `AUDIT_GROUND_TRUTH.md` | À produire | Phase 0 |
| `docs/COMPLIANCE_NF525.md` | À produire | Ticket P1-001 |
| `docs/PERSONAL_SHOPPER.md` | À produire | Phase 2 |
| `docs/AI_BOOSTER.md` | À produire | Phase 2 |
| `docs/SCORING_ENGINE.md` | À produire ou enrichir | Tickets P2-009 → P2-013 |
| `docs/MARKDOWN_ENGINE.md` | À produire | Ticket P3-001 |
| `docs/DATA_ARCHITECTURE.md` | À produire | Tickets P1-003, P1-004 |

---

## Checklist "Avant ouverture publique Frip & Co Vernon"

- [ ] Conformité NF525 : attestation éditeur signée + tests OK
- [ ] Multi-utilisateur PIN : Sophie, Léa et autres employées ont leur PIN
- [ ] Mode offline POS : test coupure réseau réussi
- [ ] SumUp Solo : compte production activé, frais validés
- [ ] Hardware POS testé : douchette + AirPrint + tiroir RJ11 + iPad
- [ ] Backup PostgreSQL : test de restauration mensuel OK
- [ ] RGPD : CGU + politique conf publiées + écran droits client OK
- [ ] Site vitrine : Schema.org LocalBusiness + Lighthouse 90+
- [ ] Personal Shopper v2 : 5 clientes Gold beta-testeuses validées
- [ ] Markdown engine : règles initiales chargées et testées
- [ ] Reporting ESS : convention Solidarité Textiles intégrée
- [ ] Email automation : welcome + J+30 + anniversaire actifs
- [ ] Plan boutique 7 zones : étiquettes physiques posées
- [ ] Étiquetage en lot : stock initial étiqueté (>500 pièces)
- [ ] Split payment + retours : cycle de vente complet validé en simulation
