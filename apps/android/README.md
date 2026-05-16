# Vintiz Android — POS + back-office natif

Application Android Kotlin/Jetpack Compose qui consomme `apps/api/*` via
`/api/v1/*`. Voir `docs/MIGRATION_ANDROID_NATIVE.md` pour le plan complet
(opportunités, risques, phasage, frontière web/site).

## État

**Sprint 0 — Setup** — terminé

- [x] Mono-repo `apps/android/` + Gradle catalog `libs.versions.toml`
- [x] `settings.gradle.kts` + root `build.gradle.kts`
- [x] `app` (entry point Compose, Hilt câblé, single-activity)
- [x] `core:core-design` (tokens `vz-*` : `VzColors`, `VzTypography`, `VzTheme`)
- [x] `core:core-common` (`Money`, `VintizResult`/`VintizError`)
- [x] `core:core-network` (Retrofit + Moshi + interceptors Auth/ClientId/RequestId/RateLimit + `RefreshTokenAuthenticator` + cert-pinning prêt)
- [x] `core:core-security` (`TokenStorage` + impl `EncryptedSharedPreferences`)
- [x] `core:core-datastore` (Preferences DataStore : env switch, backends imprimante/TPE, last sync timestamps)
- [x] `core:core-database` (Room + 4 entités + 4 DAOs)
- [x] `core:core-testing` (fakes hardware partagés : Printer, PaymentTerminal, Scanner, Nfc, TokenStorage)
- [x] Hilt root + `network_security_config.xml` + GitHub Action + FileProvider

**Hardware abstractions** — TCP/USB/HID/NFC/Camera livrés, SDK SumUp BT en squelette V2

- [x] `hardware:hardware-api` (`PrinterService`, `LabelPrinterService`, `ScannerService`, `PaymentTerminalService`, `NfcService`, `EscPosBytes`)
- [x] `hardware:hardware-escpos-tcp` (impl MUNBYN réseau port 9100 + retries)
- [x] `hardware:hardware-escpos-usb` (USB-OTG `UsbManager` + chunks/zero-length packet)
- [x] `hardware:hardware-zpl-tcp` (impl Zebra ZD421d réseau port 9100 + retries)
- [x] `hardware:hardware-scanner-hid` (KeyEvent listener Inateck via `MainActivity.dispatchKeyEvent`)
- [x] `hardware:hardware-scanner-camera` (CameraX + ML Kit BarcodeScanning debounce 800 ms)
- [x] `hardware:hardware-nfc` (NfcAdapter foreground dispatch, UID hex)
- [x] `hardware:hardware-sumup-rest` (polling REST aligné `usePosPayment.ts` web — 4 tests verts)
- [x] `hardware:hardware-sumup-sdk` (squelette + interfaces — activation Mac avec credentials + dep Maven `com.sumup:merchant-sdk:5.+` commentée)

**Data layer** — tous les domaines couverts

- [x] `data:data-auth` (login JWT + cashier PIN + refresh)
- [x] `data:data-pos` (commit local-first + idempotence `client_uuid` + `DrainTransactionsWorker`)
- [x] `data:data-inventory` (search / by-barcode / by-id offline-first + `SyncProductsWorker` + import CSV multipart + photos upload)
- [x] `data:data-clients` (identify / byNfcUid offline-first + `SyncClientsWorker` + `PurgePiiWorker` 30 j RGPD + `fullClient` 6 sections)
- [x] `data:data-hardware` (sync GET/PUT `/api/v1/hardware/config` + `SyncHardwareConfigWorker` boot)
- [x] `data:data-cahier` (day + monthly-target + signature + `weekday-weights`)
- [x] `data:data-reports` (dashboard + retail-kpis + Z-reports + fiscal-export DTOs)
- [x] `data:data-admin` (transactions + users CRUD + audit-logs + refund + `payment-attempts` SumUp)
- [x] `data:data-ia` (weekly-checklist + trends + persona + product insights)
- [x] `data:data-trends` (window-display CRUD + markdown rules CRUD + **`PATCH /reorder` produits vitrine**)
- [x] `data:data-fiscal` (export NF525 `@Streaming` + FileProvider)
- [x] `data:data-newsletter` (subscribers + export CSV + suppression RGPD art.17)
- [x] `data:data-loyalty` (subscribe + config 3 modes + `validateCoupon`)
- [x] `data:data-personal-shopper` (recos cliente + companion POS + log CTR)
- [x] `data:data-zones` (store-plan via `/admin/store-plan`)
- [x] `data:data-notifications` (POST `/api/v1/notifications/fcm-token`)

**Domain (pure Kotlin/JVM)**

- [x] `domain:domain-pos` (`Cart`, `CartLine`, `PaymentSplit.computeChange`)
- [x] `domain:domain-inventory` (`Product`, `ProductStatus`, `BarcodeNormalizer` regex Unicode/NBSP)
- [x] `domain:domain-clients` (`Client`, `LoyaltyTier`)
- [x] `domain:domain-cahier` (`CahierDay` dayProgress / monthProgress / YoY / isSigned)
- [x] `domain:domain-reports` (`ZReport` diff / reconcile / surplus / totalRevenue)
- [x] `domain:domain-zones` (`Zone` saturated/underused/ratio + `ZoneShape` + `ScoreBucket`)

**Features Compose** — 17 modules feature livrés

- [x] `feature:feature-auth` (LoginScreen + CashierPinScreen NumPad 4 chiffres)
- [x] `feature:feature-pos` (cart + recherche + scan HID + NFC fidélité + companion live + remises + **coupons** + paiements espèces/CB SumUp REST + idempotence client_uuid + raccord `ReceiptDialog` post-vente)
- [x] `feature:feature-inventory` (recherche + **ProductDetailScreen** photo Coil + **InventoryImportScreen** CSV dry-run/commit + **capture photo** caméra `ACTION_IMAGE_CAPTURE` + upload)
- [x] `feature:feature-clients` (liste + **ClientDetailScreen 6 onglets** : Synthèse / Achats / Fidélité / Goûts / RGPD / Audit)
- [x] `feature:feature-settings` (config matériel + toggles backends + camera scanner)
- [x] `feature:feature-dashboard` (KPIs + météo + top produits)
- [x] `feature:feature-cahier` (objectif jour + cumul mois + YoY + signatures + **`WeekdayWeightsCard` sparkline 7 jours** + **`MonthlyTargetCard`** saisie objectif)
- [x] `feature:feature-admin` (**5 onglets** : Ventes / Z-Reports / Users (CRUD) / **CB** payment-attempts / Audit + RefundDialog + CreateUserDialog + lien "Exporter période fiscale" depuis Z-Reports)
- [x] `feature:feature-ia` (**4 onglets** : Checklist hebdo / Tendances sociales / Tendances retail / **Vitrine** avec **réordonnancement ▲▼** + accept)
- [x] `feature:feature-zones` (`ZonesCanvas` Compose top-down + bbox auto + tap detection + alerte saturation Accent + chips Saturée/Sous-rempli)
- [x] `feature:feature-onboarding` (**6 étapes** : Bienvenue → Env dev/prod → Sync hardware → **Test impression MUNBYN** → **Test TPE SumUp** → Fin)
- [x] `feature:feature-receipt` (modal post-vente avec impression MUNBYN + kick tiroir auto cash)
- [x] `feature:feature-fiscal` (export NF525 avec date pickers + Share Intent + paramètres initiaux depuis Admin)
- [x] `feature:feature-newsletter` (liste abonnés RGPD + export CSV + AlertDialog suppression art.17)
- [x] `feature:feature-loyalty` (souscription POS V###### avec 3 consents RGPD + mode payant)
- [x] `feature:feature-personal-shopper` (manager : recherche cliente + grid recos + log CTR)
- [x] `feature:feature-drawer` (ouverture/fermeture caisse en machine d'états 5 phases + Z-Report écart colorisé)

**Workers offline** — 5 programmés au boot

| Worker | Période | Réseau |
|---|---|---|
| `DrainTransactionsWorker` | 15 min | CONNECTED (BackoffPolicy.LINEAR 30 s) |
| `SyncProductsWorker` | 1 h | CONNECTED |
| `SyncClientsWorker` | 6 h | CONNECTED |
| `PurgePiiWorker` (RGPD) | 1 jour | — |
| `SyncHardwareConfigWorker` | OneTime au boot | CONNECTED |

**Polish & infra**

- [x] `VintizFcmService` (`FirebaseMessagingService` + register onNewToken)
- [x] `KioskManager` (Lock Task Mode wrapper, device-owner requis pour activation)
- [x] `InAppUpdateManager` (Play Core, check au onResume, prompt IMMEDIATE)
- [x] `benchmark:` module Macrobenchmark + Baseline Profile plugin (`PosColdStartBenchmark`)
- [x] Nav graph étendu : 5 onglets bottom + entrée "Plus" avec 10 destinations (Dashboard / IA / Zones / Admin / Fiscal / Newsletter / Loyalty / Personal Shopper / Drawer / Import CSV)
- [x] `proguard-rules.pro` consolidées (Retrofit / Moshi / Hilt / Room / OkHttp / Firebase)
- [x] `release { isDebuggable=false; isPseudoLocalesEnabled=false }` explicite
- [x] `backup_rules.xml` + `data_extraction_rules.xml` (excluent JWT + DB + DataStore du cloud backup et device-transfer)
- [ ] Gradle wrapper (à générer côté Mac dev, voir §Bootstrap)
- [ ] Cert-pinning prod : poser `BuildConfig.API_PIN_SHA256` flavor prod + brancher dans `AppModule.provideHttpClientFactory` (cf. `docs/ANDROID_SECURITY_AUDIT.md` §3.3)
- [ ] Tests Compose UI + Robolectric (Room DAO, HidScanner, NfcService, UsbEscPosPrinter, ViewModels) — sprint hardening Mac
- [ ] Activation SDK SumUp BT direct (décommenter dep + brancher `openCheckoutActivity` — sprint dédié)
- [ ] Drag-and-drop tactile fluide pour le réordonnancement vitrine (V3, lib `sh.calvin.reorderable` ou Compose pur)

## Tests locaux validés

**89 tests JVM purs verts** sur ce checkout (validation locale Gradle 8.14 / JDK 21) :

| Module | Tests |
|---|---|
| `core:core-common` | 6 (`Money`) |
| `core:core-network` | 9 (interceptors MockWebServer : Auth, RateLimit, ClientId, RequestId) |
| `domain:domain-pos` | 11 (`Cart` 7 + `PaymentSplit` 4 dont multi-leg) |
| `domain:domain-inventory` | 6 (`BarcodeNormalizer` 5 dont NBSP/Unicode + `ProductStatus` 1) |
| `domain:domain-cahier` | 8 (`CahierDay` progress / capping / YoY / signature) |
| `domain:domain-reports` | 4 (`ZReport` diff / reconcile / surplus / totalRevenue) |
| `domain:domain-zones` | 6 (`Zone` saturé / sous-rempli / ratio / bucket / shape) |
| `hardware:hardware-api` | 5 (`EscPosBytes.drawerKick` bytes ESC/POS) |
| `hardware:hardware-escpos-tcp` | 3 (`TcpEscPosPrinter` sur ServerSocket localhost) |
| `hardware:hardware-zpl-tcp` | 2 (`TcpZebraPrinter` UTF-8) |
| `hardware:hardware-sumup-rest` | 4 (`SumUpRestTerminal` succès/refus/annulation/timeout) |
| `data:data-auth` | 7 (`AuthRepository` MockWebServer) |
| `data:data-loyalty` | 5 (`LoyaltyRepository` subscribe + validateCoupon 409/404) |
| `feature:feature-fiscal` | 4 (`FiscalDateValidator` regex ISO + ordre + cas vides) |
| `feature:feature-loyalty` | 7 (`LoyaltySubscribeValidator` champs + email regex + mode paid) |

**Backend `/api/v1/*` versioning** : 5 tests pytest verts (`test_health.py` paramétré + `test_api_versioning.py` safety net).

Tests non couverts par ce harnais (nécessitent Android SDK / émulateur) :

- Compose UI (`feature/*`) → Espresso + ComposeRule sur Mac
- Room DAO (`core:core-database`) → Robolectric ou test instrumenté
- `HidScanner` + `AndroidNfcService` + `UsbEscPosPrinter` → Robolectric ou test device
- `CameraBarcodeAnalyzer` → device avec caméra physique
- `data:data-pos:PosRepositoryTest` (dépend de Room)
- `benchmark:PosColdStartBenchmark` → device Lenovo Tab M11 cible
- `VintizFcmService` → device avec google-services.json valide
- Workers WorkManager → `WorkManagerTestInitHelper` + Robolectric

## Documentation associée

| Doc | Audience | Contenu |
|---|---|---|
| [`MIGRATION_ANDROID_NATIVE.md`](../../docs/MIGRATION_ANDROID_NATIVE.md) | Architecte / cadrage | Plan technique complet, opportunités/risques, phasage, frontière web/site |
| [`ANDROID_APP.md`](../../docs/ANDROID_APP.md) | Caissière / manager | Manuel utilisateur en 10 sections (onboarding, vente, hors-ligne, kiosque, dépannage) |
| [`ANDROID_PROD_OPS.md`](../../docs/ANDROID_PROD_OPS.md) | Ops déploiement | Comptes, keystore, Mac setup, hardware, MDM, CI/CD, rollout Play Console, incidents |
| [`ANDROID_SECURITY_AUDIT.md`](../../docs/ANDROID_SECURITY_AUDIT.md) | Sécurité / audit | Audit OWASP MASVS L1 code-only (9 sections, 90 % conforme) |
| [`PARITY_MATRIX.md`](../../docs/PARITY_MATRIX.md) | Produit / ops | Matrice anti-divergence web ↔ Android sur 15 catégories |
| [`CONTRIBUTING_ANDROID.md`](../../docs/CONTRIBUTING_ANDROID.md) | Dev (Claude / humain) | Style Kotlin/Compose, architecture multi-modules, conventions commits, templates ViewModel/Repository |

## Bootstrap (Mac dev, première fois)

```bash
cd apps/android

# 1. Générer le wrapper Gradle (une seule fois, à committer ensuite)
gradle wrapper --gradle-version 8.11.1 --distribution-type bin

# 2. Vérifier l'environnement
./gradlew --version

# 3. Builder le module app en debug
./gradlew :app:assembleDevDebug

# 4. Lancer les tests unitaires
./gradlew testDevDebugUnitTest

# 5. Lancer le lint (équivalent du job CI)
./gradlew lintDevDebug
```

Pré-requis Mac (Apple Silicon) :

- JDK 17 Zulu ARM64 (`brew install --cask zulu@17`)
- Android Studio Iguana ou plus récent (Toolbox JetBrains)
- Android SDK Platform 34 + 35, Build-Tools 35.0.0
- AVD Pixel Tablet API 34 image ARM64
  (`system-images;android-34;google_apis;arm64-v8a`)

Détails complets : voir `docs/ANDROID_PROD_OPS.md` §3.

## Configuration `local.properties`

Créer `apps/android/local.properties` (ignoré par Git) :

```properties
sdk.dir=/Users/<you>/Library/Android/sdk
```

## Variantes de build

| Flavor | Application ID | API URL |
|---|---|---|
| `dev` | `fr.vintiz.pos.dev` | `https://api.dev.vintiz.fr/` |
| `prod` | `fr.vintiz.pos` | `https://api.vintiz.fr/` |

```bash
./gradlew :app:assembleDevDebug      # APK dev debuggable
./gradlew :app:bundleProdRelease     # AAB prod signé (requiert keystore)
```

## Signing (release uniquement)

Le keystore n'est **pas** committé. Voir
`docs/ANDROID_PROD_OPS.md` §2 pour la procédure de génération
et stockage 1Password / sauvegarde papier QR.

Variables d'environnement attendues au build release :

```bash
export VINTIZ_KEYSTORE_PATH=/path/to/vintiz-release.jks
export VINTIZ_KEYSTORE_PASSWORD=...
export VINTIZ_KEY_PASSWORD=...
```

## Fonts

Les fonts Fraunces / Manrope / JetBrains Mono sont à déposer manuellement
dans `core/core-design/src/main/res/font/` :

- `fraunces_regular.ttf`, `fraunces_bold.ttf`
- `manrope_regular.ttf`, `manrope_medium.ttf`, `manrope_bold.ttf`
- `jetbrains_mono_regular.ttf`

Source : [Google Fonts](https://fonts.google.com). Pas de Downloadable
Fonts (rester offline-first). Tant que les .ttf ne sont pas embarqués,
`VzTypography` retombe sur `FontFamily.Serif/SansSerif/Monospace`
système — le rendu reste lisible mais perd l'identité Vintiz.

## Convention de nommage

- Package racine : `fr.vintiz.pos`
- Modules core : `fr.vintiz.core.{design,common,network,security,datastore,database,testing}`
- Modules feature : `fr.vintiz.feature.{auth,pos,inventory,clients,settings,dashboard,cahier,admin,ia,zones,onboarding,receipt,fiscal,newsletter,loyalty,personalshopper,drawer}`
- Modules hardware : `fr.vintiz.hardware.{api,escpos.tcp,escpos.usb,zpl.tcp,scanner.hid,scanner.camera,nfc,sumup.rest,sumup.sdk}`
- Modules data : `fr.vintiz.data.{auth,pos,inventory,clients,hardware,cahier,reports,admin,ia,notifications,zones,fiscal,newsletter,loyalty,personalshopper,trends}`
- Modules domain : `fr.vintiz.domain.{pos,inventory,clients,cahier,reports,zones}`

Plus de détails sur les conventions de code : voir
`docs/CONTRIBUTING_ANDROID.md`.

## Liens

- Plan complet : [`../../docs/MIGRATION_ANDROID_NATIVE.md`](../../docs/MIGRATION_ANDROID_NATIVE.md)
- API consommée : [`../api/`](../api/)
- Design tokens référence web : [`../web/tailwind.config.ts`](../web/tailwind.config.ts)
- Référence UX POS : [`../web/src/app/pos/page.tsx`](../web/src/app/pos/page.tsx)
