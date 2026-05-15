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
- [x] `core:core-network` (Retrofit + Moshi + interceptors Auth/ClientId/RequestId/RateLimit + `RefreshTokenAuthenticator`)
- [x] `core:core-security` (`TokenStorage` + impl `EncryptedSharedPreferences`)
- [x] `core:core-datastore` (Preferences DataStore : env switch, backends imprimante/TPE, last sync timestamps)
- [x] `core:core-database` (Room + 4 entités + 4 DAOs)
- [x] `core:core-testing` (fakes hardware partagés)
- [x] Hilt root + `network_security_config.xml` + GitHub Action

**Semaines 2-3 — Hardware abstractions** — terminé

- [x] `hardware:hardware-api` (`PrinterService`, `LabelPrinterService`, `ScannerService`, `PaymentTerminalService`, `NfcService`, `EscPosBytes`)
- [x] `hardware:hardware-escpos-tcp` (impl MUNBYN réseau port 9100 + retries)
- [x] `hardware:hardware-escpos-usb` (USB-OTG `UsbManager` + chunks/zero-length packet)
- [x] `hardware:hardware-zpl-tcp` (impl Zebra ZD421d réseau port 9100 + retries)
- [x] `hardware:hardware-scanner-hid` (KeyEvent listener Inateck via `MainActivity.dispatchKeyEvent`)
- [x] `hardware:hardware-scanner-camera` (CameraX + ML Kit BarcodeScanning debounce 800 ms)
- [x] `hardware:hardware-nfc` (NfcAdapter foreground dispatch, UID hex)
- [x] `hardware:hardware-sumup-rest` (polling REST aligné `usePosPayment.ts` web)
- [ ] `hardware:hardware-sumup-sdk` (sumup-android-sdk BT direct) — sprint hardware ultérieur

**Semaines 4-10 — Data + Domain + Features** — terminé

- [x] `data:data-auth` (login JWT + cashier PIN + refresh)
- [x] `data:data-pos` (commit local-first + idempotence `client_uuid` + `DrainTransactionsWorker`)
- [x] `data:data-inventory` / `data:data-clients` / `data:data-hardware` (offline-first Room cache)
- [x] `data:data-cahier` / `data:data-reports` / `data:data-admin` / `data:data-ia`
- [x] `data:data-notifications` (POST `/api/v1/notifications/fcm-token`)
- [x] `domain:domain-pos` / `domain-inventory` / `domain-clients` / `domain-cahier` / `domain-reports`
- [x] `feature:feature-auth` / `feature-pos` / `feature-inventory` / `feature-clients` / `feature-settings`
- [x] `feature:feature-dashboard` (KPIs + météo + top produits)
- [x] `feature:feature-cahier` (progress jour + cumul mois + YoY + signature)
- [x] `feature:feature-admin` (4 onglets : Ventes / Z-Reports / Users / Audit + RefundDialog)
- [x] `feature:feature-ia` (Checklist hebdo + Signaux sociaux / retail)
- [x] `feature:feature-zones` (`ZonesCanvas` Compose top-down + tap detection)

**Semaines 11-14 — Polish** — terminé

- [x] `VintizFcmService` (`FirebaseMessagingService` + register onNewToken)
- [x] `KioskManager` (Lock Task Mode wrapper, device-owner requis pour activation)
- [x] `InAppUpdateManager` (Play Core, check au onResume, prompt IMMEDIATE)
- [x] `benchmark:` module Macrobenchmark + Baseline Profile plugin (`PosColdStartBenchmark`)
- [x] Nav étendue : 5 onglets bottom + entrée "Plus" → Dashboard / IA / Zones / Admin
- [ ] Gradle wrapper (à générer côté Mac dev, voir §Bootstrap)
- [ ] Robolectric tests Room + HidScanner + NfcService (sprint hardening Mac)
- [ ] OWASP MASVS audit + MobSF report (sprint hardening Mac)

## Tests locaux validés

**41 tests JVM purs verts** sur ce checkout (validation locale Gradle 8.14 / JDK 21) :

| Module | Tests |
|---|---|
| `core:core-common` | 6 (`Money`) |
| `core:core-network` | 9 (interceptors MockWebServer) |
| `domain:domain-pos` | 11 (`Cart` 7 + `PaymentSplit` 4) |
| `domain:domain-inventory` | 2 (`BarcodeNormalizer`) |
| `domain:domain-cahier` | 8 (`CahierDay` progress / YoY / signature) |
| `domain:domain-reports` | 4 (`ZReport` diff / reconcile / surplus) |
| `hardware:hardware-api` | 5 (`EscPosBytes`) |
| `hardware:hardware-escpos-tcp` | 3 (`TcpEscPosPrinter` sur ServerSocket localhost) |
| `hardware:hardware-zpl-tcp` | 2 (`TcpZebraPrinter` UTF-8) |
| `hardware:hardware-sumup-rest` | 4 (`SumUpRestTerminal` succès/refus/annulation/timeout) |
| `data:data-auth` | 7 (`AuthRepository` MockWebServer) |

Tests non couverts par ce harnais (nécessitent Android SDK / émulateur) :
- Compose UI (`feature/*`) → Espresso + ComposeRule sur Mac
- Room DAO (`core:core-database`) → Robolectric ou test instrumenté
- `HidScanner` + `AndroidNfcService` + `UsbEscPosPrinter` → Robolectric ou test device
- `CameraBarcodeAnalyzer` → device avec caméra physique
- `data:data-pos:PosRepositoryTest` (dépend de Room)
- `benchmark:PosColdStartBenchmark` → device Lenovo Tab M11 cible
- `VintizFcmService` → device avec google-services.json valide

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
`docs/MIGRATION_ANDROID_NATIVE.md` §4.2 pour la procédure de génération
et stockage 1Password.

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
Fonts (rester offline-first).

## Convention de nommage

- Package racine : `fr.vintiz.pos`
- Modules core : `fr.vintiz.core.{design,common,network,...}`
- Modules feature : `fr.vintiz.feature.{pos,inventory,...}`
- Modules hardware : `fr.vintiz.hardware.{escpos,zpl,sumup,...}`

## Liens

- Plan complet : [`../../docs/MIGRATION_ANDROID_NATIVE.md`](../../docs/MIGRATION_ANDROID_NATIVE.md)
- API consommée : [`../api/`](../api/)
- Design tokens référence web : [`../web/tailwind.config.ts`](../web/tailwind.config.ts)
- Référence UX POS : [`../web/src/app/pos/page.tsx`](../web/src/app/pos/page.tsx)
