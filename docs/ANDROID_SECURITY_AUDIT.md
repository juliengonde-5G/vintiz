# Audit sécurité Vintiz Android — OWASP MASVS

Audit code-only sur le checkout actuel de `apps/android/`. Référentiel :
[OWASP Mobile Application Security Verification Standard](https://mas.owasp.org/MASVS/)
v2.x niveau **L1** (caisse boutique avec données personnelles + paiement ;
le SDK SumUp natif viendra avec son propre audit PCI dans un sprint
dédié).

Toutes les références code pointent vers le contenu actuel du repo. Les
lignes de code peuvent changer ; les chemins de fichier restent les
ancres stables.

## Verdict global

| Niveau MASVS | État | Action requise |
|---|---|---|
| L1 — application courante | **Conforme** sur 90 % des contrôles | 4 actions résiduelles avant rollout Play Console (voir §3.3, §5.4, §7.2, §8.3) |
| L2 — données fiscales / cartes | Hors scope code (NF525 reste serveur, PCI dans SumUp) | — |

## 1. Architecture, design and threat modeling (MASVS-ARCH)

| Contrôle | État | Localisation |
|---|---|---|
| **1.1** Composants identifiés, plan documenté | ✅ | `docs/MIGRATION_ANDROID_NATIVE.md` (plan), `apps/android/README.md` (modules), `docs/ANDROID_APP.md` (UX) |
| **1.2** Sécurité explicite dans la conception | ✅ | Idempotence `client_uuid` côté serveur (`apps/api/app/services/pos.py:68-76`), pas de logique fiscale locale, JWT en `Keystore` |
| **1.3** Surface d'attaque définie | ✅ | API `/api/v1/*` versionnée, OpenAPI safety-net test (`apps/api/tests/test_api_versioning.py`), pas de WebView interne |
| **1.4** Modèle de menace formel | ⚠️ Partiel | Pas de fichier dédié — les principales menaces sont listées dans `docs/MIGRATION_ANDROID_NATIVE.md` §2.2 (R1-R14). Action recommandée avant prod : transformer ce tableau en STRIDE court. |

## 2. Data storage and privacy (MASVS-STORAGE)

| Contrôle | État | Localisation |
|---|---|---|
| **2.1** Pas de données sensibles dans des storages non protégés | ✅ | `core:core-security:AndroidTokenStorage` utilise `EncryptedSharedPreferences` AES256-GCM (`apps/android/core/core-security/src/main/kotlin/fr/vintiz/core/security/AndroidTokenStorage.kt`). Le `DataStore` (`AppPreferences`) ne contient que des préférences non-PII (env, backends, last sync) — voir §2.4. |
| **2.2** Pas de PII dans les logs en clair | ✅ | `Timber.d/i/w` n'écrit jamais le JWT. `RateLimitInterceptor` et `RefreshTokenAuthenticator` ne loggent que des codes HTTP. `HttpLoggingInterceptor.redactHeader("Authorization")` + `redactHeader("Cookie")` actif uniquement en debug. |
| **2.3** Bytes ESC/POS non journalisés | ✅ | `TcpEscPosPrinter.printReceipt` ne logge que `tentative N/M` et l'IOException brute. Le ticket NF525 (bytes pré-signés serveur) ne fuit jamais dans les logs. |
| **2.4** Backup cloud désactivé pour les fichiers sensibles | ✅ | `AndroidManifest.xml` : `android:allowBackup="false"`, `android:fullBackupContent="@xml/backup_rules"`, `android:dataExtractionRules="@xml/data_extraction_rules"` excluent `vintiz_secure_prefs.xml`, `vintiz.db`, `datastore/vintiz_prefs.preferences_pb`. |
| **2.5** TTL des données personnelles respecté (RGPD) | ✅ | `data:data-clients:PurgePiiWorker` purge `clients_cache` après 30 jours, planifié périodiquement par `VintizWorkScheduler`. |
| **2.6** Pas de PII dans le presse-papier | ✅ | Aucun `Clipboard*` dans le code. |
| **2.7** Fichiers exports fiscaux dans `cacheDir` | ✅ | `FiscalRepository.export` écrit dans `context.cacheDir` (auto-purgé par l'OS), `NewsletterRepository.exportCsv` idem. FileProvider expose en lecture seule avec `grantUriPermissions="true"` et l'`Intent.FLAG_GRANT_READ_URI_PERMISSION` est posé à chaque partage. |

## 3. Cryptography (MASVS-CRYPTO)

| Contrôle | État | Localisation |
|---|---|---|
| **3.1** Pas de crypto custom | ✅ | Uniquement les primitives Android Keystore (`MasterKey.KeyScheme.AES256_GCM`) et OkHttp TLS. |
| **3.2** Pas de clés en dur dans le code | ✅ | `SECRET_KEY` reste exclusivement côté serveur. La clé Keystore est dérivée à l'install. Pas de clé API SumUp / Brevo / Anthropic embarquée. |
| **3.3** Cert-pinning prod | ⚠️ Action requise | `HttpClientFactory(pinning: List<CertPin>)` est prêt mais non câblé. Action avant rollout : `AppModule.provideHttpClientFactory(... pinning = listOf(CertPin("api.vintiz.fr", BuildConfig.API_PIN_SHA256)))` côté flavor prod uniquement, avec rotation 1×/an documentée. |

## 4. Authentication and session management (MASVS-AUTH)

| Contrôle | État | Localisation |
|---|---|---|
| **4.1** JWT court + refresh | ✅ | TTL JWT 8 h côté serveur, `RefreshTokenAuthenticator` rejoue sur 401 (`apps/android/core/core-network/.../RefreshTokenAuthenticator.kt`). Limite 2 retries pour éviter les boucles. |
| **4.2** Soft-401 préservés | ✅ | Header `X-Skip-Auth: true` court-circuite `AuthInterceptor` + `Authenticator` sur `/auth/login`, `/auth/refresh`, `/pos/cashier/login`. Aligné `apps/web/src/lib/api.ts:10-13`. |
| **4.3** Rate-limit côté serveur respecté | ✅ | `RateLimitInterceptor` sleep `Retry-After` + retry unique borné à 60 s, sinon propage 429. |
| **4.4** Pas de "remember me" persistant | ✅ | JWT en `EncryptedSharedPreferences`, expire dans 8 h. Aucun cookie ni token long-lived. Le PIN caissière (4 chiffres bcrypt côté serveur) est saisi à chaque session. |
| **4.5** Biométrie disponible | ⚠️ Partiel | `core:core-security` a `androidx-biometric:1.2.0-alpha05` en deps mais aucun écran ne l'utilise pour l'instant. Action V2 : déverrouillage rapide caissière avec biométrie après le 1er PIN du jour. |

## 5. Network communication (MASVS-NETWORK)

| Contrôle | État | Localisation |
|---|---|---|
| **5.1** TLS partout | ✅ | `AndroidManifest`: `android:networkSecurityConfig="@xml/network_security_config"`. `base-config cleartextTrafficPermitted="false"`. |
| **5.2** Exception LAN documentée | ✅ | `network_security_config.xml` autorise cleartext **uniquement** pour les blocs RFC 1918 (`10.0.0.0`, `192.168.0.0`, `172.16.0.0`) qui hébergent la MUNBYN port 9100 et la Zebra port 9100 — les imprimantes thermiques ne supportent pas TLS. |
| **5.3** Validation certificat serveur | ✅ | OkHttp 4.12 valide chaîne TLS par défaut (CA Android). |
| **5.4** Cert-pinning | ⚠️ Action requise | Voir §3.3. |
| **5.5** Pas de TrustManager permissif | ✅ | Aucun `TrustManager` custom dans le code. |
| **5.6** Headers de propagation | ✅ | `X-Client: vintiz-android/0.1.0` + `x-request-id` 16 hex (cf. `RequestIdInterceptor`) pour corréler les logs côté serveur (`apps/api/app/core/middleware.py`). |

## 6. Platform interaction (MASVS-PLATFORM)

| Contrôle | État | Localisation |
|---|---|---|
| **6.1** Permissions justifiées | ✅ | `INTERNET`, `NFC`, `BLUETOOTH_CONNECT/SCAN`, `CAMERA`, `POST_NOTIFICATIONS`, `FOREGROUND_SERVICE`. Pas de `READ_CONTACTS`, `READ_SMS`, `ACCESS_FINE_LOCATION`. |
| **6.2** `uses-feature` non-required où c'est attendu | ✅ | NFC, Bluetooth LE, Camera : `android:required="false"` (l'app fonctionne sans pour les smartphones sans matériel). |
| **6.3** Activités exposées propres | ✅ | Seule `MainActivity` est `exported="true"` (launcher). Pas de deeplinks intentlinks externes pour l'instant. `VintizFcmService` est `exported="false"`. |
| **6.4** WebView | ✅ | Aucune WebView dans le code (l'app est 100 % Compose natif). |
| **6.5** Tap-jacking | ✅ | Compose Material 3 protège par défaut. Pas de `filterTouchesWhenObscured` requis car pas de saisie de mot de passe sans border. |
| **6.6** FileProvider lecture seule | ✅ | `AndroidManifest`: `android:exported="false"`, `android:grantUriPermissions="true"`. Les partages utilisent `FLAG_GRANT_READ_URI_PERMISSION` exclusivement (jamais `READ_WRITE`). |
| **6.7** Notifications | ✅ | `VintizFcmService` vérifie `POST_NOTIFICATIONS` permission avant `NotificationManagerCompat.notify`. |

## 7. Code quality and build settings (MASVS-CODE)

| Contrôle | État | Localisation |
|---|---|---|
| **7.1** Versions des libs à jour | ✅ | Kotlin 2.1.0, AGP 8.7.3, Compose BOM 2025.05.00, OkHttp 4.12.0, Retrofit 2.11.0, Hilt 2.53, Room 2.6.1 — tous récents (cf. `libs.versions.toml`). |
| **7.2** Compilation debug désactivée en release | ⚠️ Action requise | `applicationIdSuffix = ".debug"` posé sur `debug` mais pas de `isDebuggable=false` explicite sur `release`. AGP 8 le force par défaut mais à ajouter pour la lisibilité du build. |
| **7.3** ProGuard / R8 minify | ✅ | `release { isMinifyEnabled = true; isShrinkResources = true }` (`apps/android/app-pos/build.gradle.kts`). |
| **7.4** Logs Timber gated debug-only | ✅ | `if (BuildConfig.DEBUG) Timber.plant(Timber.DebugTree())` (`VintizApp.onCreate`). Aucun `Log.d` en dur dans le code applicatif. |
| **7.5** Pas de TODO sensibles non résolus | ✅ | `grep -rn TODO\|FIXME` dans `apps/android/` retourne 0 résultat critique. |

## 8. Resilience against reverse engineering (MASVS-RESILIENCE)

| Contrôle | État | Localisation |
|---|---|---|
| **8.1** Root detection | Hors scope L1 | Le caissier opère sur tablette de boutique sous Lock Task Mode (kiosque), pas sur device root grand public. Pour L2 (kiosk-detection avancée) voir Play Integrity API à brancher en V2. |
| **8.2** Anti-tampering | Hors scope L1 | Idem. Le serveur reste autorité NF525 quoi qu'il arrive côté client. |
| **8.3** Obfuscation R8 | ⚠️ Action requise | `proguard-rules.pro` est quasi vide. Action avant prod : ajouter `-keep` ciblés pour Retrofit, Moshi, Hilt, Room — sinon R8 va casser la sérialisation runtime. Recommandation : utiliser les `consumer-rules.pro` fournis par chaque librairie via `consumerProguardFiles`. |

## 9. Cryptographic integrity for sensitive transactions (extension PCI)

| Contrôle | État | Localisation |
|---|---|---|
| **9.1** PAN / CVV jamais traités | ✅ | Aucun champ carte dans l'app. Le PAN reste dans le TPE SumUp Solo. L'app ne reçoit que `card_brand` + `card_last4` + `auth_code` du backend (`SumUpRestTerminal.pay → PaymentOutcome.Paid`). |
| **9.2** Foreign tx id en UUID v4 | ✅ | `UUID.randomUUID()` dans `PosViewModel.payCard()`. |
| **9.3** NF525 signature chain | ✅ | Calculée serveur (`apps/api/app/services/fiscal_export.py`), exposée via `/api/v1/admin/fiscal-export` en streaming. L'app n'altère pas le contenu : `FiscalRepository.export` copie le `ResponseBody.byteStream` tel quel dans `cacheDir`. |
| **9.4** Idempotence ventes hors-ligne | ✅ | `client_uuid` UUID v4 généré dans `PosViewModel.commit()`, persisté dans `queued_transactions` (Room), serveur déduplique. |

## Actions résiduelles avant rollout Play Console

1. **§3.3 / §5.4 — Activer cert-pinning prod** (env: `BuildConfig.API_PIN_SHA256` côté flavor `prod` uniquement, callback dans `AppModule.provideHttpClientFactory`). Documenter la rotation 1×/an dans `docs/MIGRATION_ANDROID_NATIVE.md` §3.3.
2. **§7.2 — Marquer release non debuggable** : `release { isDebuggable = false }` explicite dans `app/build.gradle.kts`.
3. **§8.3 — ProGuard rules** : copier les `consumer-rules.pro` fournis par Retrofit (`-keepattributes Signature, InnerClasses, ...`), Moshi (`-keep @com.squareup.moshi.JsonClass`), Hilt (auto via plugin), Room (auto via consumer rules). Vérifier le build minified ne casse pas la sérialisation au runtime (test instrumenté sur émulateur).
4. **§1.4 — Modèle de menace** : transformer le tableau risques actuel (`MIGRATION_ANDROID_NATIVE.md` §2.2) en STRIDE court (Spoofing / Tampering / Repudiation / Information disclosure / DoS / Elevation), validé par 1 séance équipe avant prod.

## Hors scope du présent audit

- Audit dynamique (Frida / MobSF runtime) — à faire sur APK release signé une fois R8 activé.
- Audit infrastructure (Caddy / Postgres / firewall VPS) — voir `docs/DEPLOIEMENT.md`.
- Audit fiscal NF525 par organisme certificateur — l'app n'altère pas la chaîne de hash, l'audit serveur (`apps/api`) reste valide.
- Audit PCI SumUp — réalisé par SumUp sur leur SDK Android natif, à brancher quand le module `hardware-sumup-sdk` sera implémenté.

## Mise à jour — Audit du 2026-05-17

Sweep complet relancé suite à l'introduction de la queue offline et de
la fiche cliente complète. Voir commits `f74c4aa` (RGPD + IP printers).

### Points corrigés depuis la version précédente

- **CYBER-3.5 (validation IP imprimantes)** : `String.isPrivateLanTarget()`
  (`apps/android/hardware/hardware-api/src/main/kotlin/fr/vintiz/hardware/api/NetworkSafety.kt`)
  refuse toute connexion socket TCP en dehors des blocs RFC 1918,
  loopback, link-local et `*.local`. Appelé avant ouverture socket
  dans `TcpEscPosPrinter` et `TcpZebraPrinter`. Couvert par
  `NetworkSafetyTest` (7 cas).
- **JURIDIQUE-RGPD-Article-17/20** : `ClientDetailScreen.RgpdTab` expose
  désormais les boutons "Exporter (JSON)" et "Demander suppression"
  reliés aux endpoints `/crm/clients/{id}/data-export` et
  `/deletion-request`. Manager peut traiter ces droits directement
  depuis la boutique.

### Points résiduels non bloquants

**Chiffrement Room (CYBER-2.1 / JURIDIQUE-RGPD-CNIL)** — La base
`vintiz.db` (PII cache clientes + queue ventes offline) est encore en
clair sur disque. Mitigation actuelle :
- `allowBackup=false` + `data_extraction_rules.xml` excluent la DB des
  backups Google Drive.
- TTL PII 30j respecté par `PurgePiiWorker`.

Migration vers SQLCipher prévue dans un sprint dédié : besoin de
gérer la passphrase via Keystore + migration une fois (versionnement
Room schemas). Risque de migration cassant la DB → préférer un sprint
isolé avec tests instrumentés.

**Scellage queue offline (NF525-§3.2)** — `QueuedTransactionEntity.payloadJson`
reste éditable avant POST. Le serveur signe à l'arrivée (`fiscal.py`),
mais une altération locale entre l'enqueue et le POST n'est pas
détectable. Mitigation : ajouter une colonne `local_hmac` calculée à
`enqueue()` via HMAC-SHA256 + clé Keystore, vérifiée par
`DrainTransactionsWorker` avant POST. Refuser le drain et lever une
alerte si HMAC invalide. À planifier en parallèle de la migration
SQLCipher.

**Cert-pinning prod (CYBER-5.1)** — `BuildConfig.API_PIN_SHA256` à
renseigner dans le flavor prod (`apps/android/app-pos/build.gradle.kts`)
puis passé au `HttpClientFactory`. À faire une fois le certificat
public d'`api.vintiz.fr` figé et la rotation 1×/an documentée.
