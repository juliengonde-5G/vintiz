# Vintiz Android — guide contributeur

Pour qui : développeur (Claude ou humain) qui ajoute un module, une
feature, ou modifie le code Kotlin dans `apps/android/`.

Pour le plan global : [`MIGRATION_ANDROID_NATIVE.md`](MIGRATION_ANDROID_NATIVE.md).
Pour le rollout prod : [`ANDROID_PROD_OPS.md`](ANDROID_PROD_OPS.md).
Pour la parité web : [`PARITY_MATRIX.md`](PARITY_MATRIX.md).

## 1. Style Kotlin / Compose

### Règles principales
- **Kotlin code style** : `official` (configuré dans `gradle.properties`).
  4 espaces, pas de tab. Trailing commas autorisés.
- **Imports** : un par ligne, jamais d'`import *`. Ordonnés Android Studio
  par défaut (java, javax, kotlin, autres, projet, tests).
- **Fichiers** : un public top-level par fichier dont le nom matche.
  Plusieurs `private` ou `internal` autorisés.
- **Visibilité** : `internal` pour les helpers de module qui ne sortent pas.
  `private` pour les helpers de fichier. `public` (par défaut) réservé à
  l'API du module.
- **`data class`** : pour tout DTO ou state UI. Pas de POJO Java-style.
- **Money** : toujours `fr.vintiz.core.common.Money` (cents en Long).
  Jamais de `Double` ni `Float` pour l'argent — risque d'arrondi.

### Compose
- **`Composable` privé pour les sous-blocs** : extraire dès qu'un bloc
  dépasse 50 lignes.
- **State hoisting** : passer `state` + callbacks en arguments, pas de
  ViewModel injecté dans les sous-Composables (sauf entry-point Screen).
- **`remember(key) { ... }`** quand le calcul est non-trivial. Sans key
  si juste une init.
- **Material 3** uniquement. Pas de Material 2 ni Material Components.
- **MaterialTheme.colorScheme** + tokens `VzColors` exposés via `VzTheme`.
  Jamais de couleur hex en dur dans un Composable (sauf cas exceptionnel
  documenté).

### Naming
- Modules Gradle : `kebab-case` (`feature-personal-shopper`, pas `featurePersonalShopper`).
- Packages : `fr.vintiz.{layer}.{module}` (`fr.vintiz.feature.personalshopper`,
  sans tiret car packages Java).
- Classes : `PascalCase`. ViewModel suffixé `ViewModel`, écran Composable
  suffixé `Screen`.
- Fonctions : `camelCase`. Toujours en verbe pour les actions (`load`,
  `refresh`, `commit`), substantif pour les getters (`displayName`).
- État UI : `*UiState`, hoisted dans le ViewModel.

## 2. Architecture multi-modules

### Pyramide de dépendances (toujours bottom-up, jamais l'inverse)

```
app
 ├─ feature:* (UI Compose, ViewModels Hilt)
 │   └─ data:* (Retrofit, Repository)
 │       └─ domain:* (use-cases purs)
 │           └─ core:core-common (Money, VintizResult, VintizError)
 ├─ hardware:* (PrinterService impls, ScannerService, etc.)
 │   └─ hardware-api (interfaces)
 │       └─ core:core-common
 └─ core:* (network, security, datastore, database, design, testing)
```

### Règles

| Dépendance | Autorisé ? |
|---|---|
| `feature-x` → `feature-y` | ❌ sauf cas particulier (modal post-vente : feature-pos → feature-receipt) |
| `feature` → `data` | ✅ |
| `feature` → `domain` | ✅ |
| `feature` → `core` | ✅ |
| `feature` → `hardware-api` (jamais `hardware-*-impl`) | ✅ |
| `data` → `core` | ✅ |
| `data` → `domain` | ✅ (rare) |
| `domain` → `core` | ✅ (seulement `core-common`) |
| `core-x` → `core-y` | ✅ si pas de cycle |

### Quand créer un nouveau module ?

- **Nouveau domaine métier** isolé qui aurait sa propre couche
  data + domain + feature → 3 modules d'un coup
  (cf. `personal-shopper`, `loyalty`, `newsletter`).
- **Nouveau hardware** → `hardware-{name}-{impl}` qui dépend de
  `hardware-api`.
- **Surface tech transversale** → `core-{name}` (rare).

Pas de module pour un seul fichier de 50 lignes. Préférer ajouter dans
un module proche existant.

## 3. Ajouter une nouvelle feature

### Étapes

1. **Backend** — vérifier que les endpoints existent. Si non, demander
   à l'équipe API + bloquer le PR Android tant qu'ils ne sont pas
   livrés `/api/v1/*`.
2. **`data-{name}`** :
   - Créer `build.gradle.kts` aligné sur un voisin (ex. `data-cahier`).
   - Ajouter au `settings.gradle.kts` racine.
   - `Api` interface Retrofit + `Dto` `data class` `@JsonClass(generateAdapter = true)`.
   - `Repository` qui mappe `Result` → `VintizResult<T>` via le helper
     `call { ... }` (cf. `CahierRepository`).
3. **`domain-{name}`** (optionnel, si pure logique métier) :
   - Modèle métier immutable + computed properties + validators objects.
   - Tests JUnit 5 + Truth sur les invariants.
4. **`feature-{name}`** :
   - `ViewModel` `@HiltViewModel` avec `StateFlow<UiState>`.
   - `Screen` Composable entry-point avec `hiltViewModel()`.
   - Manifest XML vide ou avec permissions ciblées.
5. **DI** :
   - `AppModule` : `@Provides @Singleton fun provideXxxApi(r: Retrofit): XxxApi = r.create(XxxApi::class.java)`
   - `@Provides @Singleton fun provideXxxRepository(...): XxxRepository = ...`
6. **Nav** :
   - Ajouter `const val XXX = "shell/xxx"` dans `Routes`.
   - Ajouter `composable(Routes.XXX) { XxxScreen() }` dans le shell graph.
   - Si entrée PlusMenu : ajouter `PlusItem(...)`.
   - Si route avec arguments : helper `Routes.xxx(id)` + `arguments = listOf(...)`.
7. **Tests** :
   - JVM purs pour validators, mappers, Money operations.
   - Hilt instrumented test pour le ViewModel (à brancher Mac Robolectric).
8. **`PARITY_MATRIX.md`** : ajouter la ligne avec ✅/🟡/🔵/🟠/⚪.

### Template Repository

```kotlin
class XxxRepository(private val api: XxxApi) {

    suspend fun fetch(): VintizResult<XxxDto> = call { api.fetch() }

    private suspend inline fun <T> call(block: suspend () -> T): VintizResult<T> = try {
        VintizResult.Success(block())
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
    }
}
```

### Template ViewModel

```kotlin
@HiltViewModel
class XxxViewModel @Inject constructor(
    private val repo: XxxRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(XxxUiState())
    val state: StateFlow<XxxUiState> = _state.asStateFlow()

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val r = repo.fetch()) {
                is VintizResult.Success -> _state.update {
                    it.copy(loading = false, data = r.value)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
        }
    }
}

data class XxxUiState(
    val loading: Boolean = false,
    val data: XxxDto? = null,
    val error: String? = null,
)
```

## 4. Conventions de commit

Format Conventional Commits :

```
<type>(<scope>): <résumé court 60 chars max>

<corps détaillé en français — sections logiques, listes>

<footer optionnel>
```

### Types

| Type | Quand |
|---|---|
| `feat(android)` | Nouvelle feature ou capacité |
| `fix(android)` | Correction de bug |
| `refactor(android)` | Réécriture sans changement de comportement |
| `docs(android)` | Documentation uniquement |
| `test(android)` | Tests uniquement |
| `chore(android)` | Build / CI / deps |
| `feat(api)` | Backend uniquement |

### Scope

`android` pour tout `apps/android/**`. `api` pour `apps/api/**`. Pas de
scope multi-mots.

### Exemples valides

```
feat(android): feature-drawer (caisse + Z-Report) + ProductDetail inventory
fix(android): bugs détectés par tests JVM purs + revue Compose
docs(android): guide opérateur ANDROID_PROD_OPS.md + raccord POS→Receipt
```

### Inclure dans le corps

- **Quoi** : 1-2 phrases.
- **Pourquoi** (parfois) : pour les choix architecturaux non-évidents.
- **Décisions techniques** : helpers utilisés, fakes injectés, refactor.
- **Tests** : "N tests JVM verts cumulés" si nouveaux ou impacts.
- **Bugs corrigés en cours d'écriture** : tracer les blocages rencontrés
  (utile pour les futurs `grep`).

## 5. Tests

### Pyramide

```
                  /\
                 /  \  E2E (3-5)
                /----\
               /      \  Integration (~10)
              /--------\
             /          \  Compose UI (~30)
            /------------\
           /              \  Unit JVM (~100)
          /----------------\
```

Cible actuelle : 89 tests JVM verts, 0 régression. Tests Compose UI
+ instrumented arrivent côté Mac (cf. `ANDROID_SECURITY_AUDIT.md`
§ Reste à faire).

### Où mettre quoi

| Couche | Tests | Outil |
|---|---|---|
| `domain-*` | Pure logique + validators | JUnit 5 + Truth |
| `data-*` Repository | Mapping HTTP → VintizError | JUnit 5 + MockWebServer |
| `core-network` interceptors | Headers, retry 429, auth | JUnit 5 + MockWebServer |
| `hardware-*` JVM | Bytes ESC/POS, ZPL, TCP fake socket | JUnit 5 |
| `core-database` DAO | Schéma + queries | Robolectric (Mac) |
| `feature-*` ViewModel | Coroutines test + Turbine | À écrire Mac |
| `feature-*` Compose UI | Sémantique + interactions | ui-test-junit4 (Mac) |
| Workers | WorkManager test framework | À écrire Mac |

### Lancer en local (Mac)

```bash
cd apps/android
./gradlew :feature:feature-drawer:test            # unit tests JVM
./gradlew :feature:feature-drawer:testDebugUnitTest  # idem avec resources
./gradlew :app:connectedDevDebugAndroidTest        # instrumented sur AVD
./gradlew :app:lintDevDebug                        # lint Android
```

### Lancer en local (Claude Code, env JVM pur)

Voir `/tmp/vt` setup dans les commits récents — copie les sources sans
`androidx.*` ni `android.*` dans un projet Gradle JVM, lance
`gradle test`. Couvre ~70 % des tests de la base.

## 6. Sécurité

À ne **jamais** faire :

- Log d'un JWT, d'un Bearer token, d'un PAN/CVV (PAN n'arrive jamais
  dans l'app de toute façon).
- Stocker un secret hardcodé dans le code source.
- Désactiver `usesCleartextTraffic` ou `networkSecurityConfig` pour
  contourner un cert problématique en prod.
- Faire un `runBlocking` sur le main thread (sauf `MainActivity.onCreate`
  pour la décision route de départ — déjà documenté).
- Annoter un endpoint `@JavascriptInterface` (pas de WebView dans l'app).
- Persister du PII (cliente, JWT) dans `SharedPreferences` non-chiffré
  ou dans la `cacheDir` non-isolée.

À **toujours** faire :

- JWT → `EncryptedSharedPreferences` via `TokenStorage`.
- Cache cliente PII → Room + `PurgePiiWorker` TTL 30 j.
- Exports fiscaux / CSV → `context.cacheDir` + `FileProvider` lecture seule.
- Logs `Timber` avec `redactHeader` pour Authorization/Cookie.
- Cert-pinning en prod (à activer avant rollout, cf. `ANDROID_SECURITY_AUDIT.md` §3.3).

## 7. Performance

### Cibles documentées (`ANDROID_SECURITY_AUDIT.md` §5.1)

- Cold start POS < 1.5 s (Macrobenchmark)
- Frame timing < 16 ms p99 sur scroll inventory 200+ items
- Network waterfall payment wizard < 4 s online
- Battery drain Foreground Service < 5 %/h écran allumé

### Ce qui consomme

| Couche | Risque |
|---|---|
| Compose recomposition | Hoister le state. Éviter `mutableStateOf` dans body Composable sans `remember`. |
| Coil | Set `crossfade(false)` sur les listes scroll, `size(...)` pour pré-dimensionner. |
| Retrofit | Streaming pour les binaires (>500 ko), Moshi codegen plutôt que reflective. |
| Room | Index sur les colonnes filtrées (déjà fait : barcode, nfcUid). Éviter `LiveData`. |
| WorkManager | `BackoffPolicy.LINEAR` pour les retries fréquents, `EXPONENTIAL` pour les rares. |

## 8. Pull request

### Avant de pousser

```bash
./gradlew lint                        # Android lint
./gradlew :app:lintDevDebug           # focus sur app
./gradlew testDebugUnitTest           # tous les tests JVM unit
./gradlew detekt                      # à brancher Mac (pas dans le repo encore)
```

### Format PR

```
Titre : feat(android): <résumé court>

Body :
## Quoi
<3-5 bullets>

## Pourquoi (si non évident)
<paragraphe ou bullets>

## Tests
- 89 tests JVM verts ✓
- Compose UI test à brancher en V2

## Checklist
- [ ] PARITY_MATRIX.md à jour si feature web existante
- [ ] CLAUDE.md mis à jour si nouvelle convention
- [ ] Pas de TODO/FIXME critique laissé
- [ ] Pas de secret en clair / log JWT
```

## 9. Quand demander de l'aide

- **Backend bloque** : pinger l'équipe API avec le nom de l'endpoint
  attendu et l'OpenAPI snippet souhaité. Bloquer le PR Android en
  attendant.
- **Doute archi** : ouvrir une issue avec `architecture` tag avant le
  développement, surtout si on touche les couples `feature ↔ feature`
  ou les `hardware-*-impl`.
- **Doute sécurité** : pinger `dpo@solidarite-textiles.fr`, ne pas
  improviser. L'audit OWASP MASVS L1 est la référence.
