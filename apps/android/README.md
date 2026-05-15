# Vintiz Android — POS + back-office natif

Application Android Kotlin/Jetpack Compose qui consomme `apps/api/*` via
`/api/v1/*`. Voir `docs/MIGRATION_ANDROID_NATIVE.md` pour le plan complet
(opportunités, risques, phasage, frontière web/site).

## État

**Sprint 0 — Setup** (presque fini)

- [x] Mono-repo `apps/android/`
- [x] Gradle catalog `libs.versions.toml`
- [x] `settings.gradle.kts` + root `build.gradle.kts`
- [x] Module `app` (entry point Compose, Hilt câblé)
- [x] Module `core:core-design` (tokens `vz-*` : `VzColors`, `VzTypography`, `VzTheme`)
- [x] Module `core:core-common` (`Money`, `VintizResult`/`VintizError`)
- [x] Module `core:core-network` (Retrofit + Moshi + interceptors Auth/ClientId/RequestId/RateLimit + `RefreshTokenAuthenticator`)
- [x] Module `core:core-security` (`TokenStorage` + impl `EncryptedSharedPreferences`)
- [x] Module `core:core-datastore` (Preferences DataStore : env switch, backends imprimante/TPE, last sync timestamps)
- [x] Hilt root (`@HiltAndroidApp` + `AppModule`)
- [x] `network_security_config.xml` (TLS partout sauf LAN imprimantes RFC 1918)
- [x] GitHub Action `.github/workflows/android.yml`
- [ ] Gradle wrapper (à générer côté Mac dev, voir §Bootstrap)
- [ ] Module `data:data-auth` (refresh token réel câblé dans `AppModule`)
- [ ] `core:core-database` (Room + SQLCipher)
- [ ] Modules `data/*`, `domain/*`, `feature/*`, `hardware/*`

Les modules listés "à venir" seront créés au fil des sprints — voir
`docs/MIGRATION_ANDROID_NATIVE.md` §3.9 pour le phasage.

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
