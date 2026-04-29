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
