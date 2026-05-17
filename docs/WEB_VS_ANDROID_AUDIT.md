# Audit Web vs Android — écarts constatés (2026-05-17)

Audit réalisé après bug bash sur APK installé en boutique. Documente
les écarts entre `apps/web` (référence UX manager + caissière) et
`apps/android` (Vintiz POS native), avec plan d'action priorisé.

Référence complémentaire : `docs/PARITY_MATRIX.md` (vue théorique des
features cible). Ce doc-ci est le réel post-test.

## Synthèse

| Domaine | État | Sévérité |
|---|---|---|
| Login manager + JWT | ✅ Fonctionne (form-urlencoded) | — |
| Onboarding | ✅ Welcome + Env (3 étapes, plus de tests pré-login bloquants) | — |
| Bottom nav + back button | ✅ TopAppBar avec ← + 7 onglets | — |
| Cahier du jour | ❌ Schéma DTO Android vs backend totalement divergent | **P1 — bloquant manager** |
| Tableau de bord | ❌ Schéma DTO partiellement aligné post-fix, manque `recent_transactions` UI | **P1 — bloquant manager** |
| Plan boutique 3D | ❌ Compose Canvas plat 2D, pas de rendu isométrique | **P2 — perte fonctionnelle vs cahier des charges** |
| Compagnon IA | ❌ Pages vides — DTOs jamais alignés sur backend (weeklyChecklist, trends, personas) | **P1** |
| Admin (transactions, refund, payment-attempts) | ❌ Pages blanches — schémas vs backend non vérifiés | **P1** |
| Newsletter | ✅ DTO aligné `{total, active, unsubscribed, results}` | — (post-fix) |
| Caisse ouverture/fermeture | ✅ Body EUR Decimal (post-fix) | — (post-fix) |
| Rétention session | ✅ Si JWT présent, skip Login → CashierPin direct | — (post-fix) |
| Logo POS | ✅ "€" remplace "₽" | — (post-fix) |
| Loyalty redemption points | ❌ Pas implémenté côté Android (backend manque le champ aussi) | **P2** |
| Fiscal export | ✅ Stream backend → FileProvider Share Intent | — |
| Reports / Z-Report | 🟡 DTOs Z-Report alignés, dashboard via le `top_products_week` | — |

## 1. P1 — Bloquants à fixer cette semaine

### 1.1 Cahier du jour (manager quotidien)

**Symptôme** : crash au clic sur l'onglet Cahier.
**Cause** : `CahierDayDto` Android attend `target_cents`, `actual_cents`,
`ya1_cents`, `cumulative_month_cents` (flat cents). Backend (`apps/api/app/api/cahier/router.py:112-145`)
renvoie nested EUR :
```json
{
  "date": "...",
  "is_past": false,
  "weekday": "lundi",
  "header": {"weather": {...}, "message_du_jour": "...", "operation_en_cours": "..."},
  "objectifs_valeur": {"ca_budget_mois": 50000, "ca_objectif_jour": 1666, "ca_n1_jour": 1520, ...},
  "performance": {"ca": 1280.5, "tk": 45, "iv": 2.1, "pm": 28.4, ...},
  "zoning": {...},
  "crm_loyalty": {...},
  "progression_horaire": [...]
}
```
**Action** :
- Réécrire `CahierDayDto` pour matcher cette structure
- Adapter `CahierScreen` qui consomme `day.target_cents` etc. → utiliser `objectifs_valeur.ca_budget_mois`
- Mettre à jour `WeekdayWeightsDto` selon la vraie réponse `/weekday-weights`
- ETA : 1/2 j (1 dev Android + relecture par manager)

### 1.2 Tableau de bord

**Symptôme partiel** : KPIs vides + crash sur top_products.
**Cause** : DTO aligné maintenant côté champs `today/stock/top_products_week`,
mais le composant `recent_transactions` (10 derniers tickets) n'est
pas rendu UI.
**Action** :
- Ajouter LazyColumn "Tickets récents" dans `DashboardScreen` avec
  navigation vers admin transactions (équivalent web)
- Brancher météo Vernon (le backend la renvoie déjà via `weather`)
- ETA : 2 h

### 1.3 Compagnon IA

**Symptôme** : pages vides sur chaque onglet (Checklist, Tendances,
Personas, Insights produit).
**Cause** : `WeeklyChecklistDto`, `TrendsDto`, `PersonaReportDto`,
`ProductInsightsDto` codés sans cross-check backend. Probable mismatch
de champs.
**Action** :
- Audit endpoint par endpoint : `GET /api/ai/weekly-checklist`,
  `/ai/trends`, `POST /api/ai/persona/{marketing|juridique}`,
  `GET /api/inventory/products/{id}/insights`
- Réécrire les 4 DTOs
- Tester chaque écran avec Claude Haiku live
- ETA : 1 j

### 1.4 Admin (transactions, refund, payment-attempts)

**Symptôme** : pages blanches.
**Cause** : `AdminApi` + `AdminRepository` ont 7 endpoints, DTOs
non alignés sur `/api/admin/transactions`, `/payment-attempts`,
`/audit-logs`, `/data-quality`, etc.
**Action** :
- Audit chaque endpoint
- Réécrire les DTOs
- Wirer UI : tableau filtrable + bouton refund (modal)
- ETA : 1 j

## 2. P2 — Important V2 (Sprint suivant)

### 2.1 Plan boutique 3D isométrique

**Cahier des charges originel** : `apps/web/src/components/zones/IsoCanvas.tsx`
(281 L) — rendu isométrique 2.5D des 11 zones boutique avec drag,
zoom, capacité, taux d'occupation, photos zones overlay.

**État Android actuel** : `ZonesScreen` rend une LazyColumn plate des
11 zones avec nom + CA mois. AUCUN canvas isométrique. Énorme perte
fonctionnelle vs vision produit.

**Action** :
- Sprint dédié 3-5 j : porter `IsoCanvas.tsx` en `Canvas` Compose
- Coordonnées : `pos_x, pos_y, width, height, shape, display_order`
  de chaque `Zone` (déjà en DB)
- Pinch-to-zoom + drag : `Modifier.transformable`
- Long-press zone → modal détail (capacité, score moyen, produits assignés)
- ETA : 4 j

### 2.2 Loyalty redemption (1 pt = 0,10 €)

**État web** : toggle "Utiliser X pts (-Y €)" au panier quand cliente
identifiée. Max 50 % du panier.
**État Android** : champ `loyalty_points` exposé en lecture seule via
Companion. Pas de rachat possible.
**Bloqueur backend** : `CreateTransactionRequest` Pydantic n'a pas
de champ `loyalty_redemption_cents`. À ajouter d'abord backend, puis
Android.
**Action** :
- Ticket backend : ajouter le champ + recompute total
- Ticket Android : checkbox + slider "Utiliser X pts"
- ETA : 1 j backend + 1/2 j Android

### 2.3 NumPad cash tendered

**Web** : Numpad tactile pour saisir le cash donné (calcul automatique
de la monnaie rendue).
**Android** : `payCash(effectiveTotal.cents)` envoie le total exact
(pas de monnaie à rendre). Le caissier ne peut pas saisir un cash
différent.
**Action** :
- Ajouter une BottomSheet NumPad qui ouvre au tap "Espèces"
- Pré-rempli avec total, le caissier peut augmenter (rendu calculé)
- ETA : 1/2 j

## 3. P3 — Améliorations différées

- **Discount chip par ligne** : web a -5/-10/-15/-20/-30 %, Android pas
- **Z-Report PDF impression** : web génère et imprime un Z complet
- **Refund avec modal** : web a un workflow refund par méthode de
  paiement, Android pas encore
- **Personal Shopper recherche libre** : web a une zone texte
  Claude Haiku, Android consomme uniquement les `picks` pré-calculés
- **Import CSV inventaire** : Android a l'endpoint mais pas l'écran

## 4. Plan d'action (3 sprints, ~3 semaines)

### Sprint A (semaine 1) — Bloquants manager

- [ ] Cahier du jour : DTO + UI alignés backend nested EUR
- [ ] Dashboard : "Tickets récents" + météo
- [ ] Admin : 7 écrans aligné DTOs (transactions, refund, audit, fiscal-export, ...)
- [ ] Compagnon IA : 4 DTOs alignés + Claude Haiku live

**Livrable** : manager peut piloter une journée complète depuis la
tablette (cahier matinal → POS → admin refund → IA checklist → fiscal
export).

### Sprint B (semaine 2) — Caisse & Fidélité

- [ ] Backend : champ `loyalty_redemption_cents` + recompute
- [ ] Android : toggle rachat points au POS
- [ ] NumPad cash tendered avec rendu monnaie visible
- [ ] Discount chips par ligne (-5/-10/-15/-20/-30 %)
- [ ] Avoir partiel multi-leg (cash + avoir + CB sur un même ticket)

**Livrable** : parité fonctionnelle POS web/Android sur les 4 méthodes
de paiement + fidélité full.

### Sprint C (semaine 3) — Plan boutique 3D + polish

- [ ] Plan boutique : `Canvas` Compose isométrique
  (pinch-zoom + drag + détail zone)
- [ ] Z-Report PDF impression via MUNBYN
- [ ] Personal Shopper recherche libre (texte → Claude Haiku → picks)
- [ ] Import CSV inventaire (file picker + dry-run preview)
- [ ] Bug bash final + macrobenchmark

**Livrable** : V1 prod-ready pour Managed Google Play privé.

## 5. Architecture résiduelle

Risques moyen-terme à monitorer :

1. **Drift DTO récurrent** : chaque évolution backend casse silencieusement
   un DTO Android. Solution : auto-générer les DTOs via OpenAPI Generator
   (déjà planifié `MIGRATION_ANDROID_NATIVE.md` §2.3).

2. **SQLCipher pour Room** : PII clientes en clair sur disque,
   non-conformité CNIL (cf. `ANDROID_SECURITY_AUDIT.md` §2026-05-17 mise à jour).

3. **HMAC scellage queue offline** : transaction modifiable avant POST,
   risque NF525 §3.2. Sprint dédié à planifier (cf. audit juridique).

4. **Cert-pinning prod** : `BuildConfig.API_PIN_SHA256` à figer une fois
   le certificat `api.vintiz.fr` validé.

## Annexe — Endpoints à vérifier en priorité (DTOs Android)

| Endpoint backend | DTO Android | État | Sévérité |
|---|---|---|---|
| `GET /api/cahier/{date}` | `CahierDayDto` | ❌ | P1 |
| `GET /api/cahier/weekday-weights` | `WeekdayWeightsDto` | ❓ | P1 |
| `GET /api/reports/dashboard` | `DashboardDto` | ✅ post-fix | — |
| `GET /api/ai/weekly-checklist` | `WeeklyChecklistDto` | ❓ | P1 |
| `GET /api/ai/trends` | `TrendsDto` | ❓ | P1 |
| `POST /api/ai/persona/{kind}` | `PersonaReportDto` | ❓ | P1 |
| `GET /api/inventory/products/{id}/insights` | `ProductInsightsDto` | ❓ | P1 |
| `GET /api/admin/transactions` | `TransactionListDto` | ❓ | P1 |
| `GET /api/admin/payment-attempts` | `PaymentAttemptDto` | ❓ | P1 |
| `GET /api/admin/audit-logs` | `AuditLogDto` | ❓ | P1 |
| `GET /api/newsletter/subscribers` | `SubscribersListDto` | ✅ post-fix | — |
| `POST /api/pos/drawer/open` | `DrawerOpenRequest/Response` | ✅ post-fix | — |
| `GET /api/admin/store-plan` | `StorePlanDto` (zones) | ❌ rendu 2D plat | P2 |
| `POST /api/pos/transactions` | `CreateTransactionRequest` | 🟡 manque `loyalty_redemption_cents` | P2 |
