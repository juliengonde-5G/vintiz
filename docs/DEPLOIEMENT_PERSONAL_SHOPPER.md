# Déploiement — Personal Shopper

Module IA gated qui propose à chaque cliente une sélection personnalisée
en boutique, basée sur son historique d'achat et son profil de goûts.

**Objectif business** : faire venir en boutique. Pas de vente en ligne —
le PS est une vitrine personnalisée qui pousse à se déplacer à Vernon.

## Prérequis techniques

| Item | État | Détails |
|---|---|---|
| Embeddings catalogue | ✅ | `services/embeddings.py` — recompute via `/api/admin/embeddings/recompute` |
| Profil de goût client (taste_profile) | ✅ | `customer_taste_profiles` table |
| Cold-start onboarding | ✅ | 3 questions au moment de l'inscription |
| Endpoint live | ✅ | `/api/crm/account/personal-shopper/live` |
| Recherche sémantique texte libre | ✅ | `/api/crm/account/personal-shopper/search` (Claude Haiku + cache Redis 24 h) |
| Gating fidélité | ✅ | Refus 403 si `loyalty_account` inactive |
| Gating consent profilage | ✅ | Refus 403 si `Consent.profiling != true` |
| Toggle activation public | ✅ | `/api/crm/account/personal-shopper/toggle` |
| Frontend `/account/shopper` | ✅ | Composant complet avec opt-in |
| Alertes tendance email | ✅ | Cron `trend_alerts.py`, daily 11:00 |

## Étapes de mise en route

### 1. Préparer le catalogue (J-3)

```bash
# Recalcul des embeddings catalogue (Anthropic key requise)
curl -X POST "https://api.vintiz.fr/api/admin/embeddings/recompute" \
  -H "Authorization: Bearer $MANAGER_JWT"
```

Le job tourne ~30 s pour 500 produits. À relancer après chaque arrivage
massif (lot d'arrivage > 50 produits).

### 2. Recueillir les premiers opt-ins (J)

Sur l'espace client `/account/shopper`, le toggle « Activer le Personal
Shopper » :
1. Pose le `consent.profiling = true` côté client.
2. Active le module pour cette cliente uniquement.
3. Trace une entrée audit `consent_given`.

**Seuil minimum recommandé avant communication large** : 50 clientes
opt-in (suffisant pour valider le tunnel sans saturer les serveurs IA).

### 3. Configurer la clé Anthropic (J)

Variable d'env `ANTHROPIC_API_KEY` posée en prod. Sans elle, le PS bascule
en *recommandations basées sur règles* (taste profile + RFM) — utilisable
mais moins pertinent que la version LLM-augmentée.

### 4. Activer le cron alertes tendance (J)

Le cron `trend_alerts` tourne chaque jour à 11:00 sur le scheduler
APScheduler de l'API. Vérifier dans les logs après 1 jour :

```bash
ssh vps "cd /opt/vintiz && docker compose logs api | grep trend_alerts"
# Attendu : "trend_alerts: scanned X products, matched Y clients, sent Z emails"
```

### 5. Communication clients (J+7)

Quand 50 opt-ins sont passés (étape 2) :
- Email transactionnel ciblé via Brevo : « Découvrez votre Personal Shopper »
- Story Instagram « 3 clientes ont déjà essayé » (UGC consenti)
- Affichage dans `/account` (bannière si non opt-in)

## KPIs à suivre

| KPI | Cible | Source |
|---|---|---|
| Taux d'opt-in PS | > 30 % des fidèles | `Consent.profiling = true` count |
| Taux de click sur reco PS | > 20 % | events_log `personal_shopper_click` |
| Conversion visite boutique (J+7 après PS) | > 15 % | RFM segment shift |
| Recherches texte libre / membre / mois | > 2 | endpoint logs |
| Latence p95 reco live | < 2 s | logs FastAPI |
| Latence p95 search Claude | < 4 s | logs `personal_shopper_search` |

## Procédure de désactivation rapide

Si la qualité des recos décroche :
1. Désactiver le toggle pour TOUS les opt-ins en mettant
   `consent.profiling = false` (script SQL admin).
2. Le frontend bascule alors automatiquement sur l'écran d'opt-in
   réinitialisé (gating 403 → page « Activer le Personal Shopper »).
3. Vider le cache Redis : `docker compose exec redis redis-cli FLUSHALL`.
4. Pour bloquer le module entièrement, retirer `ANTHROPIC_API_KEY` —
   le PS bascule en mode dégradé (règles seulement).

## Architecture résumée

```
Client opt-in → Consent.profiling = true
                      ↓
            POST /personal-shopper/toggle
                      ↓
       /personal-shopper/live (gated)
                      ↓
         personal_shopper.py
         ├── taste_profile (cold-start + achats)
         ├── embeddings (similarité cosine)
         └── RFM weighting
                      ↓
              Top 8 produits stock
                      ↓
            Affichage /account/shopper

Cron trend_alerts (11:00) :
  trend_score > 70 + match taste_profile
  → email Brevo (frequency cap 7 j)
```

## Annexes

- `services/personal_shopper.py` — recommandation engine (règles + embeddings).
- `services/personal_shopper_search.py` — extraction de filtres LLM
  (« t-shirt blanc taille M » → `{type:tshirt, color:white, size:M}`).
- `services/trend_alerts.py` — cron quotidien 11:00.
- `services/embeddings.py` — calcul embeddings produits / clientes.

---

## Vague V1 — Activation & Web (PS 360)

Réf. audit `Vintiz_Audit_Personal_Shopper_360.md` §5, §7.1, §8, roadmap §10.
V1 = rendre le dispositif « live » côté client. **Non-cassant.** Migration
additive `0051` (deux colonnes nullable sur `clients`).

### Livré dans le code

| Item | Où | Détail |
|---|---|---|
| **Onboarding en couches** | `services/onboarding.py`, `/api/crm/account/onboarding`, `apps/site/.../account/onboarding/page.tsx` | L1 genre + tranche d'âge déclaratifs (obligatoire) ; L2 cold-start visuel (`/api/crm/onboarding/visual-candidates` → likes mean-poolés en `visual_centroid` réel) ; L3 styles/occasions/budget **+ marques** (facultatif). |
| **Colonnes déclaratives** | migration `0051`, `models/client.py` | `clients.gender_profile` (femme/homme/mixte) + `clients.age_band` (`<25/25-34/35-44/45-54/55+`). Les signaux *calculés* (saison, prix, affinité tendance) restent en V2. |
| **État vide assumé** | `services/personal_shopper.py:_cold_start`, `apps/site/.../account/shopper/page.tsx` | Plus de dump « dernières arrivées » génériques : profil vide / aucun match → message « Rien de neuf pour vous aujourd'hui — on vous écrit dès qu'une pièce arrive » + CTA affiner le profil. |
| **Photoroom sur les cartes** | `/api/crm/curation/current`, `personal_shopper.recommend` | `photo_url` = `storefront_photo_url` (détourée, fond charte) avec repli sur la photo brute. |
| **Adhésion gratuite** | `services/loyalty_config.py` | Mode par défaut déjà `free` — aucune action (vérifier `PUT /api/admin/loyalty/config` si modifié). |

### À faire côté OPS (hors code)

Ces items de la vague V1 ne sont pas du ressort du code applicatif :

1. **Google Business Profile + réseaux sociaux** : créer/activer GBP (NAP
   complet : tél, email, horaires), Instagram (bio + lien + highlights
   « Personal Shopper »), brancher GSC. Cf. audit §5.1 + `docs/audits/03_SEO_POSITIONNEMENT.md`.
2. **Wallet pass — signing** : poser les secrets de signature Apple
   (`WALLET_TEAM_IDENTIFIER`, certificat `.p12`) et Google
   (`WALLET_GOOGLE_ISSUER_ID`). Le payload est prêt (`services/wallet.py`),
   seule la signature est « à plugger côté ops ».
3. **Scripts caisse (éléments de langage salariés)** — à afficher au comptoir :
   - *Accroche fidélité + consentement* : « Vous repassez par Vernon ? Notre
     carte vous prévient dès qu'une pièce qui vous ressemble arrive — c'est
     gratuit et vous gardez la main sur vos préférences. Je vous l'active ? »
     (puis email de confirmation de consentement automatique.)
   - *Pépites pour vous* : « J'ai trois pièces rentrées cette semaine qui
     collent à ce que vous aimez — je vous les montre ? »
   - *Cadeau* : « C'est pour vous ou pour offrir ? » (le flag cadeau lui-même
     arrive en **V2**.)
   - *Ton* : vouvoiement ; **jamais** « bonne affaire », « powered by AI »,
     « dépôt-vente », ni moralisme ESS.

### Décision produit — pas de réservation (tranché)

Le positionnement « suggestion only, pas de réservation/blocage en ligne —
générateur de visites » (audit §5.2, §7.4) est **acté**. Toute mention de
réservation ou de mise de côté produit a été retirée du site public : pages
`/personal-shopper` (FR + EN), `/produits` + fiches produit, capsules,
formulaire de contact, pages EN et un article du journal. Les CTA renvoient
désormais vers une **vérification de disponibilité + venue en boutique**
(« Demander à la voir », « Écrivez-nous pour vérifier sa disponibilité »),
jamais une réservation 24-48 h. La promesse mise en avant devient « on vous
prévient dès qu'une pièce qui vous ressemble arrive ».
