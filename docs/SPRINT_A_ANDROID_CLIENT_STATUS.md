# Sprint A — Vintiz Client Android — État de pause

**Date de suspension** : 2026-05-17
**Branche** : `claude/sprint-a-android-client`
**HEAD au gel** : `7c129d1` (fix drawable manquant vintiz_monogram.png)
**PRs ouvertes** :
- **#84** — plan B2C (docs uniquement) — base `main` — peut être mergée sans risque
- **#85** — Sprint A code — base `claude/android-bootstrap-and-api-v1` — **CI rouge**

## TL;DR pour la reprise

Le scaffold complet du Sprint A est livré (split `:app`→`:app-pos`, scaffold `:app-client`, 4 nouveaux modules, magic-link OTP, bottom-nav 3 onglets, CI Android étendu). Le code Kotlin compile et les 6 tests MockWebServer de `data-auth-client` passent. **La CI a été rouge sur 4 erreurs séquentielles** corrigées une par une au fur et à mesure que chaque diagnostic apparaissait dans les logs. Le dernier fix poussé (`7c129d1` — ajout de `vintiz_monogram.png` manquant) **n'a pas été vérifié par un run CI** avant la pause.

À la reprise : déclencher un run CI sur la PR #85, lire la sortie, traiter la potentielle 5ème erreur (s'il y en a) avec la même boucle qu'avant.

## Ce qui a été livré dans le Sprint A

### Code (commit principal `58a3196`)

| Bloc | Détail |
|---|---|
| **Split atomique** | `apps/android/app/` → `apps/android/app-pos/` via `git mv`. `settings.gradle.kts` : `include(":app-pos")` + `include(":app-client")`. `benchmark/build.gradle.kts` → `targetProjectPath = ":app-pos"`. Refs docs (`ANDROID_APK_INSTALL`, `PROD_OPS`, `SECURITY_AUDIT`) alignées. |
| **`:app-client`** | App Hilt+Compose minSdk 28, flavors dev/prod, ApplicationId `fr.vintiz.client`. Modules : `VintizClientApp` `@HiltAndroidApp`, `MainActivity`, `ClientRootNavGraph` (bascule onboarding/shell selon JWT), `ClientAppModule` (DI : `ClientTokenStorage`, `HttpClientFactory`, `ClientAuthRepository`). Theme `Theme.VintizClient` Material3 DayNight. |
| **`:core:core-security`** (étendu) | `ClientTokenStorage` interface + `AndroidClientTokenStorage` (EncryptedSharedPreferences fichier distinct `vintiz_client_secure_prefs`) + `ClientTokenStorageAdapter` (pour brancher `HttpClientFactory` typé `TokenStorage`). |
| **`:core:core-testing`** (étendu) | `FakeClientTokenStorage` (in-memory pour tests). |
| **`:data:data-auth-client`** | `ClientAuthApi` (Retrofit, magic-link JSON) + DTOs Moshi + `ClientAuthRepository`. **6 tests MockWebServer** (204 OK, 200 persist, membership null, 401, 429, logout). |
| **`:feature:feature-client-onboarding`** | `EmailRequestScreen` + `OtpVerifyScreen` + `OnboardingViewModel` partagé via sous-graphe Nav imbriqué (scope `getBackStackEntry(GRAPH)`). |
| **`:feature:feature-client-shell`** | Bottom-nav 3 onglets (Boutique / Compte / Shopper) + `AccountHomeScreen` stub (email + n° carte) + Boutique/Shopper placeholders. |

### CI (commits `c625bce` + `7c129d1`)

`android.yml` étendu pour couvrir POS **et** Client en un seul run :
- Steps `Unit tests (POS — modules existants)` + `Unit tests (Client — Sprint A)` (data-auth-client)
- Steps `Android Lint POS/Client` + `Build APK debug POS/Client`
- Artefacts : `vintiz-pos-dev-${SHA}.apk` + `vintiz-client-dev-${SHA}.apk`

Les workflows `android-pos.yml` et `android-client.yml` ont été supprimés (redondants — `android.yml` couvre tout).

### Docs (PR #84)

`docs/PLAN_ANDROID_CLIENT_APP.md` (346 lignes) — plan complet 5 sprints / 10 sem, 3 sections + 9 wow features, 13 endpoints backend, risques + bêta.

## Les 4 erreurs CI séquentielles et leurs fixes

Sur la PR #85, chaque push révélait l'erreur SUIVANTE après le fix précédent. Documente pour ne pas refaire les mêmes erreurs au Sprint B :

### 1. `FakeClientTokenStorage` — JVM signature clash (commit `72dd2ff`)

**Symptôme** : `Unit tests` step KO. `:data:data-auth:testDebugUnitTest` ne compile plus.

**Cause** : `var email: String?` génère un `getEmail()` synthétique JVM qui collisionne avec l'override `getEmail()` de l'interface `ClientTokenStorage` → `error: platform declaration clash`. Cassait `core-testing` → cascade sur tous les modules en `testImplementation(core-testing)`.

**Fix** : renommer le backing field `email` → `storedEmail`. Le contrat public (`getEmail()`, `saveEmail()`) reste inchangé.

**Leçon** : pour les fakes Kotlin qui implémentent une interface, ne JAMAIS nommer un `var` du même nom que la méthode `getX()` de l'interface. Préfixer (`stored*`, `current*`) ou utiliser `@JvmName`.

### 2. CI workflow référençait `:app` après le rename (commit `c625bce`)

**Symptôme** : step "Android Lint (dev debug)" KO avec "Project ':app' not found".

**Cause** : Le workflow préexistant `android.yml` avait `./gradlew :app:lintDevDebug` et `:app:assembleDevDebug`. Mes nouveaux workflows `android-pos.yml`/`android-client.yml` n'ont pas tourné — **GitHub Actions utilise les workflows de la branche base pour les PR de sécurité** (les nouveaux workflows ajoutés dans une PR sont ignorés jusqu'au merge).

**Fix** : étendre `android.yml` (du base branch) pour couvrir POS+Client, supprimer mes 2 workflows redondants.

**Leçon** : un nouveau workflow `.yml` ajouté dans une PR ne tourne PAS sur cette PR. Le tester implique soit (a) le merger en avance dans la branche base, soit (b) modifier un workflow existant.

### 3. `@Provides Moshi` manquant dans AppModule POS (merge `eae5679`)

**Symptôme** : `:app-pos:hiltJavaCompileDevDebug` KO : `[Dagger/MissingBinding] com.squareup.moshi.Moshi cannot be provided`.

**Cause** : Une autre session Claude avait poussé le commit `58fe6c9` à 16:07 UTC sur `claude/android-bootstrap-and-api-v1` qui ajoutait `@Provides Moshi` à `AppModule`. Mon fork datait de 16:02, donc je n'avais pas ce fix.

**Fix** : merge de la base branch dans la mienne. Git a appliqué le patch au bon path (`app-pos/`) automatiquement via rename detection.

**Leçon** : avant de pousser un Sprint sur un trunk actif, **toujours fetch+rebase/merge** pour récupérer les commits qui pourraient avoir été poussés en parallèle par d'autres sessions/contributeurs.

### 4. Commentaire de bloc imbriqué `/account/*` dans KDoc (commit `19d00c3`)

**Symptôme** : `:feature:feature-client-shell:kspDebugKotlin` KO : `e: ClientShellRoutes.kt:19:1 Unclosed comment`.

**Cause** : **Kotlin supporte les commentaires de bloc imbriqués** (contrairement à Java). Le `/*` dans le texte `/account/*` du KDoc `/** ... */` ouvrait un nouveau commentaire qui ne se refermait pas avant la fin du fichier.

**Fix** : `/account/*` → `/account/...` dans le KDoc.

**Leçon** : éviter les patterns `/*` (slash-étoile collé) dans du texte de KDoc Kotlin. Si tu dois citer un chemin avec wildcard, échappe en backticks (`` `/account/*` ``) ou remplace par `/account/...`.

### 5. `composable(...)` fully-qualified dans une lambda (commit `33af72f`)

**Symptôme** : `:feature:feature-client-shell:compileDebugKotlin` KO : `e: ClientShell.kt:63:41 Unresolved reference 'composable'` × 3.

**Cause** : `androidx.navigation.compose.composable(...)` en fully-qualified dans une lambda à receiver implicite (`NavHost { ... }` → receiver = `NavGraphBuilder`). Kotlin ne résout pas une extension function par son nom complet quand le receiver est implicite — il faut un import.

**Fix** : `import androidx.navigation.compose.composable` + appel non-qualifié. Même pattern que le commit existant `e08b33d` (`detectTransformGestures`).

**Leçon** : pour les extension functions Compose/Nav, toujours utiliser un import explicite. Le fully-qualified inline ne marche pas dans les lambdas à receiver implicite.

### 6. PNG drawable manquant `vintiz_monogram` (commit `7c129d1` — non vérifié CI au gel)

**Symptôme** : `:app-client:processDevDebugResources` KO : `error: resource drawable/vintiz_monogram not found`.

**Cause** : Au scaffold de `:app-client`, j'avais copié `ic_launcher_foreground.xml` (qui réfère `@drawable/vintiz_monogram`) sans copier le PNG correspondant.

**Fix** : `cp app-pos/src/main/res/drawable/vintiz_monogram.png app-client/src/main/res/drawable/`.

**Leçon** : quand on copie un drawable XML inter-modules, faire un `grep "@drawable\|@string\|@color" *.xml` pour identifier toutes les ressources référencées et copier leurs assets.

## Ce qui reste à vérifier à la reprise

1. **Run CI sur HEAD `7c129d1`** — déclencher un run (push d'un commit vide ou rerun manuel) et vérifier que `:app-client:processDevDebugResources` passe maintenant que le PNG est là.
2. Si une 5ème erreur apparaît, suivre la même méthode : instrumenter le step `Android Lint Client (dev debug)` avec le grep ci-dessous, pousser, lire la sortie, fixer.

   ```yaml
   - name: Android Lint Client (dev debug)
     run: |
       set +e
       ./gradlew :app-client:lintDevDebug --stacktrace --info > lint-client.log 2>&1
       EXIT=$?
       set -e
       echo "=== KOTLIN COMPILER ERRORS ==="
       grep -nE "^e: |^w: |error: |Caused by:|FAILED|Compilation error|Unresolved reference" lint-client.log || echo "(no error/e: lines)"
       echo "=== END ==="
       exit $EXIT
   ```

3. **Vérifier `Build APK debug Client`** — après lint OK, l'étape suivante est `./gradlew :app-client:assembleDevDebug`. Peut révéler de nouvelles erreurs (signing config, manifest merge).
4. **APK debug signé + sideload** sur un device de test pour valider :
   - Magic-link en boucle locale via `/api/dev/magic-link/peek?email=` (endpoint existant chez Vintiz)
   - 3 onglets bottom-nav fonctionnels
   - Logout depuis Compte → retour écran email

## Comment reprendre

```bash
# 1. Récupérer l'état
git fetch origin
git checkout claude/sprint-a-android-client
git rebase origin/claude/android-bootstrap-and-api-v1   # au cas où le trunk a bougé

# 2. Déclencher un run CI propre
git commit --allow-empty -m "chore(ci): trigger run post-pause"
git push

# 3. Si le CI passe → demander review sur PR #85 + merger PR #84 (docs)
# 4. Si le CI échoue → suivre la méthode d'instrumentation ci-dessus
```

## Périmètre encore à livrer (Sprints B → E)

Voir `docs/PLAN_ANDROID_CLIENT_APP.md` §Livrable 4 pour le détail complet.

| Sprint | Contenu | Sem cible |
|---|---|---|
| **B** | Boutique + Catalogue + FCM push | 3-4 |
| **C** | Espace client RGPD complet + Shopper + Wishlist + Parrainage | 5-6 |
| **D** | Try-on Claude Vision + Lookbooks + Récap + Alertes taille | 7-8 |
| **E** | Polish + Biométrie + Bêta + Play Store | 9-10 |

**Pré-requis backend** : 8 nouveaux endpoints public + 5 wow features + 3 wrappers — voir `docs/PLAN_ANDROID_CLIENT_APP.md` §Livrable 3.

## État des branches au gel

| Branche | Statut | Action recommandée |
|---|---|---|
| `claude/plan-vintiz-android-app-cD4rB` | PR #84 — plan docs uniquement | Mergeable, low-risk |
| `claude/sprint-a-android-client` | PR #85 — code Sprint A, CI rouge | Garder en draft, reprendre depuis ce doc |
| `claude/android-bootstrap-and-api-v1` | Trunk Android natif, jamais mergé sur main | Indépendant, géré par une autre session |

## Annexes

### Stack technique livrée
Kotlin 2.1.0 · AGP 8.7.3 · Gradle 8.11.1 · Compose BOM 2025.05.00 · Hilt 2.53 · Retrofit 2.11 · Moshi 1.15 · Coroutines 1.9 · DataStore 1.1 · Room 2.6 · WorkManager 2.10 · CameraX 1.4 · Firebase BOM 33.7 · Coil 2.7.

### Fichiers clés ajoutés par Sprint A
```
apps/android/
  app-client/                                       (nouveau module app B2C)
    build.gradle.kts
    proguard-rules.pro
    src/main/AndroidManifest.xml
    src/main/kotlin/fr/vintiz/client/
      VintizClientApp.kt
      MainActivity.kt
      di/ClientAppModule.kt
      nav/ClientRootNavGraph.kt
    src/main/res/{drawable,mipmap-anydpi-v26,values}/

  core/core-security/src/main/kotlin/fr/vintiz/core/security/
    ClientTokenStorage.kt                           (interface)
    AndroidClientTokenStorage.kt                    (impl + adapter)

  core/core-testing/src/main/kotlin/fr/vintiz/core/testing/
    FakeClientTokenStorage.kt

  data/data-auth-client/                            (nouveau module)
    build.gradle.kts
    src/main/kotlin/fr/vintiz/data/authclient/
      ClientAuthApi.kt
      ClientAuthRepository.kt
      dto/MagicLinkDtos.kt
    src/test/kotlin/fr/vintiz/data/authclient/
      ClientAuthRepositoryTest.kt

  feature/feature-client-onboarding/                (nouveau module)
    build.gradle.kts
    src/main/kotlin/fr/vintiz/feature/client/onboarding/
      OnboardingNavGraph.kt
      OnboardingViewModel.kt
      EmailRequestScreen.kt
      OtpVerifyScreen.kt

  feature/feature-client-shell/                     (nouveau module)
    build.gradle.kts
    src/main/kotlin/fr/vintiz/feature/client/shell/
      ClientShell.kt
      ClientShellRoutes.kt
      AccountHomeScreen.kt
      BoutiqueHomeScreen.kt
      ShopperHomeScreen.kt
```

### Tests verts au gel
- `:data:data-auth-client:testDebugUnitTest` (6 cas MockWebServer)
- `:app-pos:lintDevDebug` (après merge du fix Moshi)
- Tous les tests POS existants (15 modules listés dans `android.yml`)

### Tests/builds NON vérifiés au gel
- `:app-client:lintDevDebug` (le PNG manquant était la 4ème erreur, fix poussé mais run CI non re-déclenché avant pause)
- `:app-client:assembleDevDebug` (jamais atteint)
- Sideload APK sur device
