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

**Semaines 2-3 — Hardware abstractions** — TCP livrés, USB/SDK BT pour V2

- [x] `hardware:hardware-api` (`PrinterService`, `LabelPrinterService`, `ScannerService`, `PaymentTerminalService`, `NfcService`, `EscPosBytes`)
- [x] `hardware:hardware-escpos-tcp` (impl MUNBYN réseau port 9100 + retries)
- [x] `hardware:hardware-zpl-tcp` (impl Zebra ZD421d réseau port 9100 + retries)
- [x] `hardware:hardware-scanner-hid` (KeyEvent listener Inateck via `MainActivity.dispatchKeyEvent`)
- [x] `hardware:hardware-nfc` (NfcAdapter foreground dispatch, UID hex)
- [x] `hardware:hardware-sumup-rest` (polling REST aligné `usePosPayment.ts` web)
- [ ] `hardware:hardware-escpos-usb` (UsbManager + USB-OTG MUNBYN) — V2
- [ ] `hardware:hardware-scanner-camera` (CameraX + ML Kit) — V2
- [ ] `hardware:hardware-sumup-sdk` (sumup-android-sdk BT direct) — V2

**Semaines 4-10 — Data + Domain + Features**

- [x] `data:data-auth` (login JWT + cashier PIN + refresh)
- [x] `data:data-pos` (commit local-first + idempotence `client_uuid` + `DrainTransactionsWorker`)
- [x] `data:data-inventory` (search / by-barcode / by-id offline-first Room cache)
- [x] `data:data-clients` (identify / byNfcUid offline-first)
- [x] `data:data-hardware` (sync GET/PUT `/api/v1/hardware/config`)
- [x] `domain:domain-pos` (`Cart`, `CartLine`, `PaymentSplit`, `computeChange`)
- [x] `domain:domain-inventory` (`Product`, `ProductStatus`, `BarcodeNormalizer`)
- [x] `domain:domain-clients` (`Client`, `LoyaltyTier`)
- [x] `feature:feature-auth` (LoginScreen + CashierPinScreen NumPad)
- [x] `feature:feature-pos` (recherche + panier + paiements espèces/CB SumUp REST + ticket id)
- [x] `feature:feature-inventory` (recherche + liste)
- [x] `feature:feature-clients` (identification + fidélité)
- [x] `feature:feature-settings` (config matériel + toggles backends + camera scanner)

**Semaines 11-14 — à venir**

- [ ] Gradle wrapper (à générer côté Mac dev, voir §Bootstrap)
- [ ] `feature:feature-dashboard` + `feature:feature-cahier` + `feature:feature-zones` (IsoCanvas)
- [ ] `feature:feature-admin` (refund / users / Z-reports / fiscal export)
- [ ] `feature:feature-ia` (CompanionHero + RecosDuJour)
- [ ] In-App Update, Kiosk Mode, Baseline Profile, FCM, hardening OWASP MASVS

## Tests locaux validés

**40 tests JVM purs verts** sur ce checkout (validation locale Gradle 8.14 / JDK 21) :

| Module | Tests |
|---|---|
| `core:core-common` | 6 (`Money`) |
| `domain:domain-pos` | 11 (`Cart` 7 + `PaymentSplit` 4) |
| `domain:domain-inventory` | 2 (`BarcodeNormalizer`) |
| `hardware:hardware-api` | 5 (`EscPosBytes`) |
| `hardware:hardware-escpos-tcp` | 3 (`TcpEscPosPrinter` sur ServerSocket localhost) |
| `hardware:hardware-zpl-tcp` | 2 (`TcpZebraPrinter` UTF-8) |
| `hardware:hardware-sumup-rest` | 4 (`SumUpRestTerminal` succès/refus/annulation/timeout) |
| `data:data-auth` | 7 (`AuthRepository` MockWebServer) |
| `core:core-network` | 9 (interceptors MockWebServer) |

Tests non couverts par ce harnais (nécessitent Android SDK / émulateur) :
- Compose UI (`feature/*`) → Espresso + ComposeRule sur Mac
- Room DAO (`core:core-database`) → Robolectric ou test instrumenté
- `HidScanner` + `AndroidNfcService` → Robolectric KeyEvent / Intent
- `data:data-pos:PosRepositoryTest` (a une dep `core:core-database` Android lib)

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
