# Audit Ground-Truth Vintiz — vérification code vs audits V1+V2

> **Date** : 26 avril 2026
> **Méthode** : exploration directe de `apps/api/app/`, `apps/web/src/`, `apps/site/src/`.
> **Objectif** : marquer chaque ticket des audits V1+V2 comme **DÉJÀ FAIT / À ENRICHIR / À IMPLÉMENTER**.

---

## Synthèse exécutive

L'application est **plus mature que ne le laissait penser le V1**, et le V2 avait raison de corriger : ~60 % des fonctionnalités attendues existent déjà sous une forme exploitable, mais ~40 % manquent ou sont partielles. Surtout :

- **NF525** : chaînage SHA-256 des transactions **déjà en place** dans `services/fiscal.py` + `models/pos.py` (`hash_chain`). Reste l'export XML DGFiP.
- **Scoring 6 composantes** : **opérationnel**, cron `1er mercredi 6h` actif via APScheduler. Le "bug" V2 sur la formule *5 est à reconfirmer (la multiplication finale est mathématiquement correcte si chaque composante normalise sur 0-20).
- **Services IA** : `ai_vision.py` (10 attributs), `ai_mapping.py`, `ai_trend.py`, `ai_pricing.py` **tous présents et fonctionnels**.
- **Plan boutique SVG drag/resize** : **déjà fait** dans `apps/web/src/app/zones/page.tsx`. Le ticket P2-005 (V1) et P2-014 (V2) sont à reclasser.
- **Split payment côté modèle** : **déjà 1-N** (`Transaction.payments`). Reste seulement la modal UI dédiée.
- **Hardware** : `sato_service.py` (étiquettes SBPL TCP:9100) + `escpos_service.py` (ticket + kick tiroir) **prêts**.

Mais **bloquants confirmés** :

- ❌ **AuditLog** existe en modèle mais **aucun listener SQLAlchemy** ne l'alimente.
- ❌ **Endpoint refund** absent (l'enum existe, l'endpoint non).
- ❌ **Multi-photos produit** : `photo_url` unique.
- ❌ **PIN cashier** : multi-users OK mais sans `pin_hash` ni `cashier_id` sur Transaction.
- ❌ **avoir_credit** absent.
- ❌ **pgvector / embeddings** absents.
- ❌ **Markdown engine** : aucune table `markdown_rules`, aucun cron de démarque.
- ❌ **Bouton "Imprimer étiquette" UI** : non branché à `sato_service.py`.

---

## Tableau de révision ticket par ticket

### Phase 1 — P0 bloquants ouverture Vernon

| ID | Sujet original | Statut réel | Action révisée | Effort |
|---|---|---|---|---|
| P1-001 | Conformité NF525 | 🟡 PARTIEL | Chaînage SHA-256 ✅ déjà en place. **Reste** : export XML DGFiP + attestation éditeur signée + tests `test_nf525.py` | Réduit à 3-5j |
| P1-002 | Multi-utilisateur + PIN cashier | 🟡 PARTIEL | Multi-users + rôles ✅. **Reste** : champ `pin_hash` sur User, écran login PIN au POS, `cashier_id` sur Transaction, rapport Z par cashier | 5j |
| P1-007 | RGPD-by-design CRM | 🟡 PARTIEL | Lookup public ✅. **Reste** : table `consents`, écran `/account/data` (export JSON, suppression 30j), CGU+politique conf, anonymisation events | 5-7j |
| P1-009 | Split payment | 🟡 PARTIEL | **Modèle déjà 1-N** (`Transaction.payments`) ✅ et UI inline gère array. **Reste** : modal POS dédié (rendu monnaie partiel + ticket multi-lignes) | Réduit à 2-3j |
| P1-010 | Flux retour / avoir POS | ❌ ABSENT | Enum `TransactionType.refund` ✅ mais pas d'endpoint. **À créer** : `POST /api/pos/transactions/{id}/refund`, remise stock, `avoir_credit` sur Client, ticket retour 80mm | 5-7j |
| P2-009 | BUG formule pondération scoring | ⚠ À RECONFIRMER | Formule actuelle = somme pondérée × 5 final (passage 20→100). Mathématiquement correct si chaque composante ∈ [0,20]. **Action Phase 0bis** : faire un test unitaire `test_scoring_formula.py` qui vérifie qu'une note 100/100 sur toutes composantes donne bien 100, et qu'une variation de pondération donne le résultat attendu | 1-2j |
| P2-010 | Connecter `category_trend` au calcul réel | 🟡 PARTIEL | `ai_trend.py` **existe et calcule velocity/freshness/season/price/display** mais le scoring utilise une valeur statique 50.0. **Reste** : appeler `ai_trend.compute()` dans `scoring_service.py` avec cache (Redis ou table `category_trend_cache` 24h) | 3-4j |
| P1-008 | Multi-photos produit | ❌ ABSENT | `photo_url` unique. **À créer** : table `ProductPhoto(product_id, url, order, is_primary, ai_analyzed_at, ai_confidence)`, migration, carousel UI fiche produit, upload multi | 5-7j |

### Phase 2 — Fondations data + différenciation IA

| ID | Sujet original | Statut réel | Action révisée | Effort |
|---|---|---|---|---|
| P1-003 | Schéma `events` + instrumentation | ❌ ABSENT | **À créer** : schema `events`, table `event_log` partitionnée mensuel, helper `app.events.emit()`, instrumentation 16 event_types | 5-7j |
| P1-004 | pgvector + tables features | ❌ ABSENT | **À créer** : `CREATE EXTENSION vector;`, schema `features`, tables `product_embeddings` + `customer_taste_profiles`, index HNSW | 3-5j |
| P1-005 | Mode offline POS | ❌ ABSENT | **À créer** : Service Worker Next.js, IndexedDB queue, replay à la reconnexion, indicateur connectivité | 7-10j |
| P1-006 | Cycle de vie produit explicite | 🟡 PARTIEL | Statuts actuels : `stock`, `display`, `sold`, `returned`. **Reste** : ajouter `RECEIVED`, `SORTED`, `TAGGED`, `DONATED`, `RETURNED_TO_SORTING`, champs `received_at`/`displayed_at`/`markdown_history`, endpoint transition, vue Kanban (qui est aussi P? listé "kanban inventaire" = absent) | 7-10j |
| P2-015 | Modèle `Batch` réception cartons | ❌ ABSENT | **À créer** : table `Batch(date_reception, nb_articles, origine, opérateur)`, relation 1-N Product, écran "Réception carton" avec scan en masse | 5j |
| P3-007 | Logique retour automatique centre de tri | ❌ ABSENT | **À créer** : cron quotidien qui repère produits >X jours en `DISPLAYED` avec score Cold → transition automatique `RETURNED_TO_SORTING` + bon de retour PDF | 3j |
| P2-001 | Pipeline embeddings produits | ❌ ABSENT | **À créer** : `app.ai.embeddings.compute_visual_embedding/compute_text_embedding`, job batch quotidien | 5j |
| P2-002 | Pipeline taste profile cliente | ❌ ABSENT | **À créer** : `app.ai.taste_profile`, centroïde pondéré 20 derniers achats, job hebdo | 4j |
| P2-003 | Endpoint Personal Shopper v2 | 🟡 PARTIEL | Endpoint actuel basé historique. **À enrichir** : similarité cosinus pgvector + diversification + Claude Haiku, retour `recommendation_set_id` | 5j |
| P2-004 | Cold start onboarding | ❌ ABSENT | **À créer** : écran inscription 5 photos style + quiz 3 questions, calcul visual_centroid initial | 4-5j |
| P2-005 | Vue plan boutique SVG | ✅ **DÉJÀ FAIT** | `apps/web/src/app/zones/page.tsx` SVG interactif drag-resize. **Reclasser** : ticket résiduel = ajouter heatmap couleur par taux rotation 30j | Réduit à 1-2j |
| P2-014 | Drag-and-drop sur plan boutique | ✅ **DÉJÀ FAIT** | Idem ci-dessus. **À supprimer du plan** | 0j |
| P2-006 | Reco placement automatique zone | 🟡 PARTIEL | `ai_mapping.py` existe et `generate_arrangement_recommendations()` opérationnel, mais **pas branché** au flux d'étiquetage. **Reste** : appel à la transition `TAGGED → DISPLAYED`, validation 1-tap dans UI étiquetage | 2-3j |
| P2-007 | Recommandation vitrine hebdomadaire | ❌ ABSENT | **À créer** : cron lundi 6h via prompt §7.2, notif iPad Sophie, validation 1-tap | 3j |
| P2-008 | Recherche "Où est cette pièce ?" | ❌ ABSENT | **À créer** : composant POS scan/recherche → affichage zone + statut, audio feedback | 2j |

### Phase 3 — Enrichissement Booster + visibilité

| ID | Sujet original | Statut réel | Action révisée | Effort |
|---|---|---|---|---|
| P3-001 | Markdown engine déclaratif | ❌ ABSENT | `ai_pricing.py` propose des markdowns mais **pas de table `markdown_rules` ni de cron auto**. **À créer** : tables `markdown_rules` + `markdown_rules_history`, écran `/admin/settings/markdown`, job batch nocturne, rapport email Camille | 7-10j |
| P3-002 | Tag couleur étiquette | ❌ ABSENT | **À créer** : génération PNG étiquette avec coin coloré, config liée aux règles markdown | 2j |
| P2-011 | Enrichir score photos | 🟡 À CONFIRMER | Score actuel binaire 0/20. **À créer** : nouvelle fonction qui combine `ai_vision.confidence` + count(photos) | 2j |
| P2-012 | Modèle `BrandTier` en DB | ❌ ABSENT | Marques hardcodées dans `scoring_service.py` ET `ai_pricing.py`. **À créer** : table `BrandTier(brand_name, tier_score, category_focus, last_updated)`, migration depuis hardcoded, UI admin | 4-5j |
| P2-013 | Enrichir `ai_vision.py` | 🟡 PARTIEL | 10 attributs déjà extraits ✅. **À enrichir** : ajouter `style_tags` (taxonomie 13), `occasion` (5), `pattern` (6), `defauts_detectes` | 3j |
| P3-003 | Module visibilité | 🟡 PARTIEL | `/api/seo/status` existe (lecture). **À enrichir** : mentions Insta/TikTok via Graph API, génération posts IA, GBP avis + suggestion réponse Claude, OAuth Search Console | 7-10j |
| P3-004 | Calendrier éditorial RS | ❌ ABSENT | **À créer** : page `/admin/social/calendar`, génération hebdo via prompt §7.4, export Meta Business Suite | 4j |
| P3-005 | Persistance historique SEO | ❌ ABSENT | **À créer** : table `SEOSnapshot` + cron quotidien + graphe d'évolution dans UI | 3j |
| P3-006 | Import CSV inventaire | ❌ ABSENT | **À créer** : endpoint upload CSV + mapping champs + dry-run + validation | 3-4j |
| P3-008 | Historique mouvements stock | ❌ ABSENT | Modèle `AuditLog` ✅ existe mais **non alimenté** (aucun event listener SQLAlchemy). **À créer** : `@event.listens_for` sur Product/Transaction pour insertion auto dans AuditLog | 3-4j |

### Phase 4 — KPIs avancés + UX polish

| ID | Sujet original | Statut réel | Action révisée | Effort |
|---|---|---|---|---|
| P4-001 | KPIs retail standards | 🟡 PARTIEL | KPIs basiques (CA, panier moyen) ✅ via `routes/reports`. **À ajouter** : sell-through, GMROI, DOH, AIT, CA/m², comparateurs S-1/M-1/A-1, heatmap horaire | 5-7j |
| P4-002 | Reporting ESS dédié | ❌ ABSENT | **À créer** : page `/admin/ess-report`, export PDF format codir Solidarité Textiles | 4j |
| P4-003 | Email automation Brevo | ❌ ABSENT | SMTP standard ✅. **À créer** : intégration Brevo, templates, triggers (welcome, J+30, anniversaire, J+60 Gold inactif) | 5-7j |
| P4-004 | Apple/Google Wallet | ❌ ABSENT | **À créer** : génération `.pkpass` + push solde points | 4-5j |
| P4-005 | Réservation 48h site vitrine | ❌ ABSENT | **À créer** : bouton fiche produit site + workflow + zone "Réservés" en btq + notif SMS | 5-7j |
| P4-006 | Mobile-first dashboard | ✅ **DÉJÀ EN PARTIE** | `apps/web/src/app/dashboard/page.tsx` responsive Tailwind. **À enrichir** : cards swipables, push notifs stratégiques | 2-3j |
| P4-007 | Segmentation RFM clients | ❌ ABSENT | **À créer** : job mensuel + UI `/admin/crm/segments` | 3j |
| P4-008 | Offre anniversaire automatique | ❌ ABSENT | **À créer** : cron quotidien + génération bon -5€ + envoi SMS | 1-2j |
| P4-009 | Notification "Nouvelles arrivées" hebdo | ❌ ABSENT | **À créer** : opt-in profil + cron hebdo email | 2j |
| P4-010 | Badge "Boost IA" caisse | ❌ ABSENT | **À créer** : badge UI POS sur produits Hot | 1j |
| P1-011 | Lier bouton "Imprimer étiquette" UI | ❌ CONFIRMÉ | Bouton inexistant côté UI, drivers prêts. **À créer** : bouton sur fiche produit → POST endpoint qui appelle `sato_service` | 1-2j |

---

## Tickets nouveaux issus du ground-truth

| ID | Sujet | Justification | Phase |
|---|---|---|---|
| P0-001 | Test unitaire `test_scoring_formula.py` | Reconfirmer / infirmer le bug V2 sur la formule *5 avant de la "corriger" | Phase 0 |
| P1-013 | Activer alimentation `AuditLog` (event listeners SQLAlchemy) | Le modèle existe mais reste vide — bloquant pour traçabilité légale | Phase 1 |
| P1-014 | Ajouter `cashier_id` sur Transaction | Lié à P1-002 (PIN cashier), traçabilité fond Z | Phase 1 |
| P1-015 | Endpoint export XML DGFiP | Compléter NF525 (chaînage déjà OK) | Phase 1 |
| P1-016 | Champ `avoir_credit` sur Client + table `Avoir` | Lié à P1-010 (flux retour) | Phase 1 |
| P2-016 | Vue Kanban inventaire `/admin/inventory/kanban` | Lié à P1-006 (cycle de vie) — la vue est absente côté UI | Phase 2 |
| P2-017 | Cache `category_trend` (table ou Redis) | Évite recalcul sur chaque scoring (lié à P2-010) | Phase 2 |

## Tickets supprimés (déjà faits)

| ID | Raison |
|---|---|
| P2-014 | Drag-and-drop plan boutique : `apps/web/src/app/zones/page.tsx` le fait déjà |

---

## Effort révisé

| Phase | Effort V2 | Effort post-ground-truth | Variation |
|---|---|---|---|
| Phase 0 + 0bis | 3-5j | 5-7j (+ tests scoring) | +2j |
| Phase 1 (P0 bloquants) | 5-6 sem | **4-5 sem** (NF525 + split payment réduits, mais +cashier_id, +avoir, +AuditLog) | -1 sem |
| Phase 2 (Fondations IA) | 4-6 sem | 4-6 sem (P2-005 et P2-014 supprimés mais P2-016 ajouté) | inchangé |
| Phase 3 (Booster + visibilité) | 3-4 sem | 3-4 sem | inchangé |
| Phase 4 (KPIs + polish) | 2-3 sem | 2-3 sem | inchangé |
| **Total** | **14-19 sem** | **13-18 sem** | **-1 sem** |

---

## Recommandation pour la suite

Démarrer par **Phase 0bis = 1-2 jours** :

1. **Écrire `test_scoring_formula.py`** pour confirmer/infirmer le bug V2 sur la formule *5 (cf. P0-001).
2. **Écrire `test_nf525_chain.py`** pour valider que toute modification d'une transaction passée invalide la chaîne SHA-256.

Si ces deux tests passent → P2-009 (refactor scoring) devient inutile ; on enchaîne directement Phase 1 dans cet ordre suggéré :

1. **P1-002 + P1-014** : PIN cashier + cashier_id (1 sprint, base pour audit légal).
2. **P1-013** : event listeners AuditLog (court, débloque traçabilité).
3. **P1-007** : RGPD CRM (consents + export + suppression).
4. **P1-010 + P1-016** : flux refund + avoir_credit (parallélisable avec P1-007).
5. **P1-009** : modal split payment UI (court, modèle déjà OK).
6. **P1-015** : export XML DGFiP (clôture P1-001).
7. **P1-008** : multi-photos.
8. **P2-010 + P2-017** : connecter `ai_trend.py` au scoring + cache.

À la fin de Phase 1, toutes les conditions d'ouverture publique légale sont réunies.
