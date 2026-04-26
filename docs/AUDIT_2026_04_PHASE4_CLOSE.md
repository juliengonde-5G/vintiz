# Phase 4 — Closing notes (avril 2026)

> Suite de `AUDIT_2026_04.md`. Cette note formalise la livraison de la Phase 4
> et liste explicitement ce qui reste en suivi.

## Vue d'ensemble

Le plan d'action V1 + V2 (couvrant 4 phases pour l'ouverture de septembre 2026)
est désormais entièrement mergé sur `main`. Voici la cartographie ticket → PR :

### Phase 1 — Blockers P0 (déjà closes en avril)
Voir le rapport AUDIT_2026_04.md.

### Phase 2 — IA foundations (déjà closes en avril)
Voir le rapport AUDIT_2026_04.md.

### Phase 3 — Pricing / scoring / visibility (déjà closes en avril)
Voir le rapport AUDIT_2026_04.md.

### Phase 4 — Business growth

| Ticket | Sujet | PR | Status |
|---|---|---|---|
| P4-001 | KPIs retail (sell-through, GMROI, AIT, CA/m²/mois…) | #25 | ✅ |
| P4-002 | Rapport ESS (réemploi, tonnage, CA reversé) | #25 | ✅ |
| P4-007 | Segmentation RFM mensuelle | #25 | ✅ |
| P4-003 | Email gateway Brevo (+ refactor SMTP inline) | #27 | ✅ |
| P4-004 | Wallet pass payload (Apple + Google) | #27 | ✅ partiel — signing TODO |
| P4-008 | Email anniversaire + coupon -10% 7j | #27 | ✅ |
| P4-009 | Email nouveautés hebdo (vendredi 10:00) | #27 | ✅ |
| P4-005 | Réservation 48h (modèle + service + UI + cron) | #29 | ✅ |
| P4-006 | Mobile dashboard (sticky KPI bar) | #29 | ✅ |
| P4-010 | Badge IA POS (vélocité, stale, marque, score, hold) | #29 | ✅ |
| —      | Coupon + reservation redemption au POS | #30 | ✅ |
| Hotfix | Migration 0014 cast `brand_tier_level` | #28 | ✅ |

## État des suites

| Mesure | Avant Phase 4 | Après |
|---|---|---|
| Tests pytest | 280 | **362** |
| Migrations Alembic | 15 | **18** |
| Endpoints API | ~85 | **~110** |
| Pages admin web | 12 | **13** (+/reservations) |
| Composants UI réutilisés | — | RetailKpisCard, EssReportCard, RfmSegmentsCard, WalletCard |

## Crons actifs (timezone Europe/Paris)

| ID | Schedule | Source |
|---|---|---|
| `monthly_scoring` | 1er mercredi 06:00 | trend score |
| `daily_rgpd_purge` | 03:00 | RGPD |
| `daily_embedding_refresh` | 04:00 | personal shopper |
| `nightly_markdown_engine` | 01:00 | markdown rules |
| `daily_return_to_sorting` | 02:00 | retour tri |
| `weekly_window_display` | lundi 06:00 | vitrine |
| `weekly_social_posts` | lundi 07:00 | posts Insta/TikTok |
| `daily_seo_snapshot` | 05:00 | SEO snapshot |
| **`monthly_rfm_segmentation`** | **1er du mois 04:00** | **P4-007** |
| **`daily_anniversary_emails`** | **09:00** | **P4-008** |
| **`weekly_new_arrivals_emails`** | **vendredi 10:00** | **P4-009** |
| **`hourly_reservation_expiry`** | **hh:15** | **P4-005** |

## Variables d'environnement à poser sur le VPS

```env
# Email transactional (P4-003) — sans clé, fallback simulation
BREVO_API_KEY=xkeysib-...
EMAIL_FROM_ADDRESS=noreply@vintiz.fr
EMAIL_FROM_NAME=Vintiz Vernon

# Apple Wallet (P4-004) — payload prêt, signing TODO
WALLET_PASS_TYPE_IDENTIFIER=pass.fr.vintiz.loyalty
WALLET_TEAM_IDENTIFIER=             # ABCDE12345

# Google Wallet (P4-004) — payload prêt, signing TODO
WALLET_GOOGLE_ISSUER_ID=            # 19 chiffres
WALLET_GOOGLE_CLASS_SUFFIX=vintiz_loyalty
```

## Limitations laissées en suivi (post-MVP)

1. **Wallet `.pkpass` Apple signing** — payload `apple` complet (storeCard,
   barcodes, couleurs Vintiz). Manque : cert p12 + WWDR + script de packaging
   ZIP. À résoudre avant de remplacer la "preview card" sur `/account/data`
   par un vrai bouton *Add to Apple Wallet*.

2. **Wallet Google JWT signing** — payload `google` (LoyaltyObject) complet.
   Manque : Service Account JSON + JWT signing (RS256) côté backend. Endpoint
   `GET /api/crm/account/wallet/google.jwt` à créer.

3. **Reservation auto-cancel offline POS** — si la cliente ne vient pas dans
   les 48h, le cron `hourly_reservation_expiry` flippe en `expired`. Pas
   d'email de rappel envoyé (TODO : J-12h reminder).

4. **Coupon stacking rules** — actuellement le coupon stack avec le loyalty
   discount linéairement. Si les codes promo deviennent fréquents, il faudra
   choisir : exclusivité ou cap (-30 % max).

5. **Pagination autocomplete cliente** sur `/reservations` (limite à 50 dans
   `/api/crm/clients?search=`).

6. **Personal Shopper sur le digest hebdo** — fallback générique fonctionne
   mais on n'évalue pas la qualité du re-rank Claude vs aléatoire. Mesurer
   l'open-rate / CTR en prod sur 4 semaines.

## Validation prod (à effectuer après déploiement)

- [ ] `alembic upgrade head` passe les migrations 0014 → 0018 sans erreur
- [ ] `GET /health` répond 200 sur `https://api.vintiz.fr`
- [ ] Logs APScheduler au boot listent les 12 crons (4 nouveaux Phase 4)
- [ ] Smoke test `/api/reports/retail-kpis?period_days=30` retourne 200 sur DB seedée
- [ ] Smoke test `/api/reservations` retourne `[]` sur DB neuve
- [ ] Création manuelle d'une réservation depuis `/reservations` puis encaissement au POS — vérifier
      que le statut passe `redeemed` automatiquement
- [ ] Création manuelle d'un coupon (via `/api/admin/coupons` ou direct DB), application au POS,
      vérifier `redeemed_at` + `redeemed_transaction_id`

## Prochaines étapes recommandées

Aucun ticket P4 restant. Pré-ouverture (juin-septembre 2026) :

- **Pilote en boutique fermée** — 2 semaines de tests réels avec l'équipe à
  partir de juin pour stress-tester le POS, la douchette, l'imprimante MUNBYN
  et le TPE SumUp.
- **Backup PostgreSQL automatisé** — script `scripts/backup.sh` existe déjà,
  poser un cron quotidien `02:30` qui pousse vers S3/Backblaze.
- **Monitoring** — choisir entre Loki+Grafana / Datadog / Sentry. Les logs JSON
  (`LOG_JSON=true`) sont déjà prêts.
- **Charge SumUp Solo** — vérifier le comportement si le Wi-Fi du TPE flop
  pendant un encaissement (le mode offline gère cash/chèque/avoir mais pas CB).

— Fin de la Phase 4.
