# Plan — Vintiz Client (2ème app Android native, B2C)

**Statut** : planning approuvé, à exécuter sur 10-12 semaines après finalisation de la 1ère app Android POS (`fr.vintiz.pos`).

**Pourquoi** : la cliente finale n'a aujourd'hui que le web `apps/site` (Next.js public + 7 zones `/account/*` gated magic-link). Le taux de retour mobile chute après le 1er achat. Une app installable native sert la fidélisation, la recommandation IA, et le drive-to-store via push + carte Wallet pass + parrainage.

**Cible** : 30 % des clientes actives Vintiz installées dans les 6 mois post-release.

## Context

Vintiz a livré sa 1ère app Android native (`fr.vintiz.pos`) — caisse boutique pour le staff. Cette 2ème app Android native, B2C cette fois, porte :

- les 7 zones espace client (`/account/*`)
- le catalogue public
- l'agenda boutique

dans **3 sections principales** : Généralités boutique, Espace client, Personal Shopper.

À étoffer avec **9 features additionnelles "wow"** inspirées du retail (Sézane, Vinted, Sephora, Decathlon, Galeries Lafayette) que la cliente attend d'une app moderne.

## Décisions actées (avec l'utilisateur)

| # | Décision | Choix |
|---|---|---|
| 1 | Architecture monorepo | Renommer `apps/android/app` → `:app-pos` + créer `:app-client` à côté |
| 2 | ApplicationId | `fr.vintiz.pos` (existant) + `fr.vintiz.client` (nouveau) |
| 3 | Bottom nav | **3 onglets** stricts : Boutique / Compte / Shopper (catalogue dans Boutique) |
| 4 | Auth | Magic-link OTP 6 chiffres email JSON (PAS du form-urlencoded comme le staff). Module `data-auth-client` séparé. |
| 5 | Min SDK app-client | 28 (vs 26 POS) — biométrie + FCM stables sur tablettes/smartphones <5 ans |
| 6 | Périmètre MVP | 3 sections + 9 wow features additionnelles (acquisition viral complet, R7/F4 drive-to-store, F8/F11/F12 premium) |
| 7 | Features retirées MVP | Click & Reserve (#1), Geofence (#6), Paiement 3x Alma (#9) |
| 8 | Timeline cible | **10-12 semaines** (4 sprints A→D élargis à 10 sem, sprint E polish/bêta) |
| 9 | Play Store | 2 fiches distinctes (B2C "Vintiz" / B2B "Vintiz POS") |
| 10 | Backend changes | 5 nouveaux endpoints + 3 endpoints à libérer en public (par l'équipe API) |

## Livrable 1 — Périmètre fonctionnel

### Section 1 — Boutique (onglet 1)

Vue magasin temps réel pour la cliente connectée ou visiteuse.

| Screen | Source | Routes appelées |
|---|---|---|
| **BoutiqueHomeScreen** | Hero adresse + horaires d'ouverture du jour + météo Vernon + CTA "Voir la vitrine" | `GET /api/store/info` (nouveau), `GET /api/weather` (à libérer public) |
| **HorairesMapScreen** | Carte OSM ou Google Maps + adresse + lien Waze | `GET /api/store/info` |
| **VitrineWeekScreen** | Curation hebdo manager (déjà existe `/curation/current`) | `GET /api/crm/curation/current` (existant) |
| **CatalogScreen** | Grid lazy 2 colonnes des produits vendables avec filtres catégorie/taille/couleur | `GET /api/catalog/products?status=stock,display&category&size&color&page` (nouveau public) |
| **ProductDetailScreen** | Fiche produit + photos + bouton "Réserver côté boutique" (lien tel) | `GET /api/catalog/products/{id}` |
| **SearchScreen** | Recherche barre + suggestions catégories | `GET /api/catalog/products/search?q=` |
| **EventsCalendarScreen** | Agenda événements boutique (sales, soirées, lookbooks) | `GET /api/events/calendar?from&to` (nouveau) |

Inclus : **Stories curation hebdo** (#5) format Instagram en haut de `BoutiqueHomeScreen` + **J'aime produit** (#10) icône heart sur `ProductCard` + `ProductDetailScreen`.

### Section 2 — Compte (onglet 2)

Porte intégral des 7 zones `/account/*` du web.

| Screen | Web ref | Routes |
|---|---|---|
| **AccountHomeScreen** | `/account` | wallet/coupons/transactions agrégés |
| **FideliteScreen** | `/account/fidelite` | `GET /api/crm/account/wallet`, `coupons` |
| **WalletPassScreen** | sub-écran Apple/Google Wallet | `GET /wallet/apple|google|qr.png` (existants) |
| **HistoriqueScreen** | `/account/historique` | `GET /transactions?email=` |
| **AvoirScreen** | nouveau | `GET /api/crm/clients/{id}/avoir` (existant) |
| **ConsentsScreen** | `/account/rgpd` | `GET/POST /consents` |
| **SettingsScreen** | nouveau | préférences locales (theme, notifs, biométrie) |
| **RgpdScreen** | `/account/rgpd` | `GET /data-export`, `POST /deletion-request` |

Inclus : **Récap mensuel partageable** (#7) card "Mon mois en mode" + **Carnet de style** (#12) moodboards persos sur les favoris.

### Section 3 — Shopper (onglet 3)

| Screen | Web ref | Routes |
|---|---|---|
| **ShopperGateScreen** | `/account/onboarding` | `POST /personal-shopper/toggle` |
| **ShopperHomeScreen** | `/account/shopper` | `GET /personal-shopper/live?email=` |
| **ShopperSearchScreen** | recherche libre Claude Haiku | `POST /personal-shopper/search` (existant) |
| **TrendAlertsScreen** | tendance opt-in | `POST /trend-alerts/toggle` (existant) |
| **TryOnScreen** | nouveau (sprint D) | `POST /shopper/try-on` (nouveau, Claude Vision) |

Inclus : **Try-on photo Claude Vision** (#11) + **Lookbooks capsule** (#8) accessible depuis Shopper.

### Features transverses (acquisition / viral / drive-to-store)

| # | Feature | Localisation UI |
|---|---|---|
| 2 | Parrainage QR partageable | Compte > "Parrainer une amie" + bouton Share |
| 3 | Wishlist partageable public `/w/{slug}` | Compte > Mes favoris > "Partager ma wishlist" |
| 4 | Alerte taille de retour | Fiche produit > toggle "M'avertir si ressort en M" |

## Livrable 2 — Architecture technique

### 2.1 Structure monorepo `apps/android/`

```
settings.gradle.kts diff :
  -include(":app")
  +include(":app-pos")          // ex-:app
  +include(":app-client")       // NOUVEAU
  +
  +// Modules data spécifiques client
  +include(":data:data-auth-client")     // magic-link JSON
  +include(":data:data-account")         // /account/* CRM
  +include(":data:data-catalog")         // produits publics
  +include(":data:data-store-info")      // adresse / horaires
  +include(":data:data-events")          // agenda boutique
  +include(":data:data-wishlist")        // favoris + partage public
  +include(":data:data-referrals")       // parrainage QR
  +include(":data:data-recap")           // récap mensuel
  +include(":data:data-tryon")           // Claude Vision (sprint D)
  +
  +// Modules feature spécifiques client
  +include(":feature:feature-client-shell")      // bottom nav + theme override
  +include(":feature:feature-client-onboarding") // magic-link OTP
  +include(":feature:feature-client-boutique")   // section 1
  +include(":feature:feature-client-account")    // section 2
  +include(":feature:feature-client-shopper")    // section 3
  +include(":feature:feature-client-tryon")      // wow #11
```

**Modules réutilisés sans modification** (12) : `core-design`, `core-network`, `core-security`, `core-common`, `core-datastore`, `core-database`, `core-testing`, `data-loyalty`, `data-personal-shopper`, `data-inventory`, `data-notifications`, `data-newsletter`.

**Modules ignorés côté client** : tous `data-pos`, `data-cahier`, `data-admin`, `data-fiscal`, `data-ia`, `data-reports`, `data-hardware`, `hardware-*`, `feature-pos/cahier/admin/fiscal/drawer/receipt/onboarding`.

### 2.2 AuthInterceptor partagé via Hilt strategy

Extraire dans `core-network` une interface `TokenProvider`. Deux implémentations Hilt :
- `@Named("pos") PosTokenProvider` (DataStore staff, déjà existant)
- `@Named("client") ClientTokenProvider` (EncryptedSharedPreferences magic-link, ajout biométrie unlock)

Chaque `app-*` declare son Hilt module qui bind la bonne stratégie. `RefreshTokenAuthenticator` reste générique.

### 2.3 Magic-link flow Android natif

```
1. ClientApp opens → MainActivity reads tokenStorage
2. Token null/expired → OnboardingNavGraph (magic-link screens)
3. EmailRequestScreen → POST /api/auth/magic-link/request {email}
4. OtpVerifyScreen → POST /api/auth/magic-link/verify {email, code} → JWT 1h
5. Store JWT in EncryptedSharedPreferences via core-security
6. After 1h expiry → token refresh OR re-prompt OTP
7. Deep link from email "Cliquez pour ouvrir l'app" :
   - intent-filter App Links https://m.vintiz.fr/account/verify?code=XXX
   - OR scheme vintiz-client://account/verify?code=XXX&email=YYY
```

Biométrie (sprint D) : après le 1er magic-link réussi, opt-in pour `BiometricPrompt` qui débloque le JWT chiffré dans Keystore — plus de re-OTP toutes les heures, juste empreinte.

### 2.4 Hardware Android exploité

| Capacité | Usage | Sprint |
|---|---|---|
| **FCM push** | Vitrine du jeudi, alertes tendance, alerte taille de retour, récap mensuel mode push | B |
| **NFC** | Tap carte fidélité (HCE émulation côté Android — read en caisse POS) | C |
| **Biométrie** | Unlock JWT rapide après 1er OTP | D |
| **Deep links** | App Links `https://m.vintiz.fr/...` + scheme `vintiz-client://` | C |
| **App Shortcuts** | "Ma carte fidélité", "Vitrine", "Mes coupons" sur long-press icon launcher | D |
| **Camera** | Scan QR coupon + parrainage entrant + try-on selfie | C/D |
| **Share Intent** | Wishlist partage URL, récap mensuel image, QR parrainage | C |

### 2.5 Stack tech

Identique à l'app POS : Kotlin 2.1, Compose BOM 2025.05, Hilt 2.53, Retrofit 2.11, Moshi 1.15, Room 2.6, WorkManager 2.10, Coroutines 1.9, DataStore 1.1, CameraX 1.4, Firebase BOM 33.7, Coil 2.7, JetBrains Mono / Fraunces / Manrope via Google Fonts (déjà câblés dans `core-design`).

## Livrable 3 — Backend changes requis

À demander à l'équipe API (Python FastAPI `apps/api/app/api/`) :

### 3.1 Nouveaux endpoints public (8)

| Endpoint | Verb | Sprint | Body / Response | Note |
|---|---|---|---|---|
| `/api/catalog/products` | GET | B | `?category&size&color&status&page` → `{items, total, page_size}` | Filtres + pagination, status par défaut `stock,display,displayed` |
| `/api/catalog/products/{id}` | GET | B | détail Product public (sans `purchase_price`) | |
| `/api/catalog/products/search` | GET | B | `?q=` → list paginée | Search tolerant (déjà existe en interne) |
| `/api/store/info` | GET | B | `{address, phone, email, hours: [{day, open, close}], lat, lng, photos[]}` | Lecture-only, public |
| `/api/store/weather` | GET | B | météo Vernon | Wrap public sur admin existing |
| `/api/events/calendar` | GET | C | `?from&to` → liste événements | Source : table `store_events` à créer |
| `/api/account/push-tokens` | POST/DELETE | B | `{email, token, platform}` | FCM registration côté client |
| `/api/account/size-alerts` | POST/GET/DELETE | C | `{email, product_id_or_attrs}` | Worker stock-diff envoie le push |

### 3.2 Nouveaux endpoints features wow (5)

| Endpoint | Verb | Sprint | Note |
|---|---|---|---|
| `/api/account/referrals` | POST/GET | C | génère QR + coupon double-side |
| `/api/account/wishlists` | POST/GET/DELETE | C | + endpoint public `/w/{slug}` |
| `/api/account/recap?month=YYYY-MM` | GET | D | données pour la card mensuelle |
| `/api/shopper/try-on` | POST | D | multipart photo → Claude Haiku Vision → suggestions |
| `/api/lookbooks` | GET/{id} | D | curation manager + many-to-many produits |

### 3.3 Endpoints à wrapper en public (3)

Garder le manager-only existant, créer un wrapper read-only :
- `/api/admin/boutique-info` → `/api/store/info` (filtré, sans données sensibles)
- `/api/admin/weather` → `/api/store/weather`
- `/api/inventory/products` → `/api/catalog/products` (statuses limités, pas de `purchase_price`)

## Livrable 4 — Phasage 5 sprints / 10 semaines

### Sprint A (sem 1-2) — Fondations

- Split `:app` → `:app-pos` (rename atomique, PR isolée)
- Scaffold `:app-client` (manifest, theme, Hilt root, MainActivity)
- `data-auth-client` (magic-link request/verify JSON, EncryptedSharedPreferences)
- `feature-client-onboarding` (EmailRequestScreen + OtpVerifyScreen)
- `feature-client-shell` (3 onglets bottom nav teal/cream, TopAppBar Vintiz)
- `AccountHomeScreen` basique (réutilise `data-loyalty` + Wallet pass via CustomTab)
- CI : 2 workflows séparés (`android-pos.yml` + `android-client.yml`)

**Livrable** : APK debug `fr.vintiz.client.debug` installable, login magic-link OK contre `api.vintiz.fr`, écran fidélité affiche les points.

### Sprint B (sem 3-4) — Boutique + Catalogue + FCM

- `data-store-info`, `data-catalog`, `data-push` (FCM)
- `feature-client-boutique` : BoutiqueHomeScreen + HorairesMapScreen + CatalogScreen + ProductDetailScreen
- VitrineWeekScreen avec stories format Instagram (#5)
- FCM registration au login + push test reception
- Backend : 5 endpoints livrés (catalog × 3, store/info, store/weather, push-tokens)

**Livrable** : la cliente peut consulter horaires + parcourir le catalogue + recevoir un push test.

### Sprint C (sem 5-6) — Espace client RGPD complet + Shopper + Wishlist + Parrainage

- `feature-client-account` complet : HistoriqueScreen, AvoirScreen, ConsentsScreen, RgpdScreen
- `feature-client-shopper` : ShopperGateScreen, ShopperHomeScreen, ShopperSearchScreen, TrendAlertsScreen
- `data-wishlist` + UI favoris (heart sur ProductCard + carnet de style #12)
- `data-referrals` + parrainage QR partageable (#2)
- Wishlist publique partageable (#3) avec deep link `vintiz-client://w/{slug}`
- App Links manifest pour `https://m.vintiz.fr/account/*`
- Backend : 4 endpoints livrés (events/calendar, size-alerts, referrals, wishlists)

**Livrable** : MVP complet des 3 sections + 5 wow features (#2, #3, #5, #10, #12).

### Sprint D (sem 7-8) — Try-on + Lookbooks + Récap + Alertes taille

- `data-tryon` + `feature-client-tryon` (upload photo + Claude Vision + suggestions IA) (#11)
- `data-recap` + RecapMensuelCard (#7) avec share intent vers Insta/Stories
- Alertes taille de retour (#4) — opt-in sur fiche produit + push reception
- `data-lookbooks` + LookbooksScreen accessible depuis Shopper (#8)
- Backend : 3 endpoints livrés (try-on, recap, lookbooks)

**Livrable** : tous les wow features livrés. Try-on Claude Vision live.

### Sprint E (sem 9-10) — Polish + Bêta + Play Store

- Biométrie unlock (BiometricPrompt + Keystore)
- App Shortcuts (Ma carte fidélité, Vitrine, Coupons)
- Macrobenchmark + Baseline Profile (cold start < 1.2 s)
- Accessibility audit (TalkBack passes 100 %)
- 3 clientes pilotes recrutées en boutique → Play Console Internal Testing
- Bug bash 1 semaine, NPS interview
- Préparation fiche Play Store B2C (textes, captures, ASO mots-clés)

**Livrable** : APK release signé + fiche Play Store prête. Rollout staged 10 % → 50 % → 100 % sur 2 sem post-validation NPS.

## Livrable 5 — Risques + mitigations

| # | Risque | Mitigation |
|---|---|---|
| 1 | **Split `:app` → `:app-pos` casse CI POS** | PR atomique avec tag `pre-split` pour rollback, alias Gradle pour les chemins, prévenir équipe POS 48h avant, runner full pipeline avant merge |
| 2 | **Magic-link JSON Android pas testé** (le `data-auth` actuel fait form-urlencoded staff) | `data-auth-client` isolé, tests d'intégration MockWebServer + staging dès sprint A |
| 3 | **8 endpoints backend bloquent sprints B-D** | Mock JSON via `BuildConfig.USE_BACKEND_MOCKS=true` pour avancer UI en parallèle. Coordonner roadmap équipe API au sprint A |
| 4 | **RGPD / consents non explicites côté mobile = CNIL** | Onboarding obligatoire avec écrans consents granulaires AVANT toute reco ou FCM. Politique de confidentialité in-app accessible depuis ConsentsScreen |
| 5 | **Performances catalogue 1000+ produits images lourdes** | Coil + `LazyVerticalGrid` + Backend doit servir variante thumbnail `?w=400&format=webp` (à demander API) |
| 6 | **Try-on photo upload RGPD (selfie biometric)** | Disclaimer fort + opt-in explicite + suppression auto serveur 24h post-traitement (à formaliser dans `/shopper/try-on` côté backend) |
| 7 | **Parrainage QR détournement (création de faux comptes)** | Limiter à 5 parrainages / 30 j / email + cap coupon 20 % max |
| 8 | **Wishlist publique exposée scrape produits** | Token slug aléatoire 16 chars + retirer le `client_id` du payload public, juste les produits |
| 9 | **App Links email magic-link non testés** (intent filter) | Tester sur Pixel + Samsung + Lenovo dès sprint A (3 OEMs ≠ comportement) |
| 10 | **Sprint timeline tendu (10 sem ambitieux)** | Sprint A focus fondations + auth (le reste cascade), sprint E peut glisser à sem 11-12 pour bêta propre |

## Livrable 6 — Vérification end-to-end

### 6.1 Compte de test staging

Backend doit provisionner un compte pilote `cliente-pilote@vintiz.fr` :
- 230 points fidélité
- 5 transactions historiques (mix cash/CB/coupon)
- 1 avoir de 12 €
- Consents accordés : email_marketing, profiling
- Consents refusés : sms_marketing, trend_alerts (pour tester opt-in)

### 6.2 Magic-link en boucle locale

Endpoint `/api/dev/magic-link/peek?email=` (existant chez Vintiz pour dev) renvoie le code OTP sans envoi mail. Branché dans Espresso :

```kotlin
val otp = client.devPeekMagicLink("cliente-pilote@vintiz.fr")
onView(withId(R.id.otp_input)).perform(typeText(otp))
```

### 6.3 Suite tests instrumentés

| Flow | Test |
|---|---|
| Login | Email request → OTP peek → verify → token stocké |
| Compte fidélité | Login → Compte tab → AccountHome affiche 230 pts + Wallet button |
| Catalogue | Boutique tab → Catalogue → filtres taille M → liste filtrée |
| Search | Search "robe taille M lin" → 3 résultats Claude Haiku |
| Wishlist | Tap heart sur produit → Compte > Favoris affiche le produit |
| Partage | Wishlist > Partager → Intent ACTION_SEND avec URL `m.vintiz.fr/w/{slug}` |
| Logout | Settings > Déconnexion → tokenStorage vide → écran login |

### 6.4 Bêta pilote sprint E

- Sem 1 : 3 clientes recrutées en boutique (volontaires fidèles), install APK via Play Internal Testing track
- Sem 2 : interview 30 min chacune, focus :
  1. Clarté du magic-link (a-t-elle compris le flow ?)
  2. Compréhension du score fidélité + Wallet pass (a-t-elle ajouté la carte au téléphone ?)
  3. Confiance dans le Personal Shopper IA (recommandations cohérentes ?)
  4. Try-on photo : envie de partager ? Pudeur ?
- Critère go/no-go release publique : NPS ≥ 7 sur 3/3 + zéro bug bloquant + RGPD audit signé

## Fichiers Vintiz critiques à conserver sous la main

### Backend (à étendre)
- `apps/api/app/api/crm/account.py` — endpoints publics existants
- `apps/api/app/api/crm/router.py` — personal-shopper, loyalty, avoir
- `apps/api/app/api/auth/router.py` — magic-link OTP
- `apps/api/app/api/inventory/router.py` — base pour `/catalog/*`
- `apps/api/app/models/client.py` — Client, LoyaltyAccount, Consent
- `apps/api/app/models/product.py` — Product + ProductStatus

### Web (référence UX à porter)
- `apps/site/src/app/account/` — 7 zones à porter en Compose
- `apps/site/src/components/account/AccountShell.tsx` — wrapper layout
- `apps/site/src/components/account/AccountNav.tsx` — sidebar 7 zones
- `apps/site/src/components/account/LoyaltyHeroCard.tsx` — card hero fidélité
- `apps/site/src/components/WalletCard.tsx` — Apple/Google Wallet CTA
- `apps/site/src/components/ProductCard.tsx` — fiche produit grid

### Android POS (à réutiliser ou copier)
- `apps/android/core/core-design/` — theme + typography Sauge Néo
- `apps/android/core/core-network/HttpClientFactory.kt` — interceptors chain
- `apps/android/core/core-security/AndroidTokenStorage.kt` — Encrypted prefs
- `apps/android/data/data-loyalty/` — wallet pass + coupons
- `apps/android/data/data-personal-shopper/` — picks + recherche libre
- `apps/android/data/data-inventory/InventoryApi.kt` — modèle pour `data-catalog`
- `apps/android/app/src/main/kotlin/fr/vintiz/pos/nav/VintizNavGraph.kt` — pattern bottom nav
- `apps/android/app/src/main/res/drawable/vintiz_monogram.png` — launcher icon partagé

### Docs
- `docs/DESIGN_SYSTEM.md` — charte Sauge Néo
- `docs/MIGRATION_ANDROID_NATIVE.md` — plan original POS (référence patterns)
- `docs/WEB_VS_ANDROID_AUDIT.md` — audit qui détaille les écarts entre web et app POS
- `CLAUDE.md` — conventions monorepo + endpoints API
