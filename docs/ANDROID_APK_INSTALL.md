# Vintiz Android — installation APK sur tablette (sideload)

Procédure pour installer l'APK Vintiz POS sur une tablette Android sans
passer par le Play Store. À utiliser pour les tests boutique avant le
rollout Managed Google Play privé.

⚠️ **APK debug uniquement** — pointe sur `https://api.dev.vintiz.fr/`,
non signé pour Play Store, pas de Crashlytics actif. Pour la prod
boutique : voir `docs/ANDROID_PROD_OPS.md` § 8 (Managed Google Play).

## 1. Récupérer l'APK

### Option A — Depuis GitHub Actions (recommandé, sans Mac)

1. Aller sur https://github.com/juliengonde-5G/vintiz/actions
2. Cliquer sur le workflow **Android — lint + unit tests + APK debug**
3. Choisir le run le plus récent vert (✅) sur la branche voulue.
4. Section **Artifacts** en bas de la page → télécharger
   `vintiz-pos-dev-debug-<sha>.zip`.
5. Dézipper — l'APK `vintiz-pos-dev-<sha7>.apk` apparaît.

Si aucun run récent n'est dispo : onglet **Actions** → bouton
**Run workflow** → branche → "Run workflow". Compte ~5-7 min.

### Option B — Build local Mac

```bash
cd vintiz/apps/android
./gradlew :app:assembleDevDebug
# APK généré dans app/build/outputs/apk/dev/debug/app-dev-debug.apk
```

Pré-requis : voir `docs/ANDROID_PROD_OPS.md` § 3 (JDK 17 Zulu, Android
Studio, AVD ARM64, etc.).

## 2. Préparer la tablette

### 2.1 Activer les sources inconnues

- **Android 14+** (Pixel, Lenovo Tab M11/Pro) :
  Settings → Apps → Special access → Install unknown apps →
  Files (ou le file manager utilisé) → Allow from this source

- **Android < 14** :
  Settings → Security → Unknown sources → ON

### 2.2 Activer USB debugging (optionnel, pour adb)

Settings → About tablet → tap 7 fois sur **Build number** → retour
arrière → **Developer options** active → cocher **USB debugging**.

## 3. Installer

### Méthode 1 — adb depuis le Mac (sideload USB)

```bash
adb devices                          # vérifier que la tablette apparaît
adb install -r vintiz-pos-dev-<sha>.apk
```

- `-r` : réinstalle en gardant les données si l'app existe déjà.
- Si l'app est en cours d'exécution : `adb shell am force-stop fr.vintiz.pos.dev`
  d'abord, puis réinstaller.

### Méthode 2 — Sideload via Files (sans Mac)

1. Transférer l'APK sur la tablette (Drive, mail, AirDroid, USB).
2. Ouvrir le file manager → tap sur l'APK → **Install**.
3. Accepter les permissions (l'app les redemandera au runtime).

### Méthode 3 — Sideload via lien direct (artifact GitHub)

1. Sur la tablette : ouvrir Chrome / Firefox.
2. Se connecter à GitHub.
3. Aller sur la page Actions, télécharger le `.zip`.
4. Dézipper avec un gestionnaire d'archives (ex. ZArchiver).
5. Installer comme méthode 2.

## 4. Premier lancement

L'app affiche d'abord l'onboarding 6 étapes :

1. Bienvenue
2. **Environnement serveur** : choisir **DEV** (par défaut). Pour
   pointer en prod, voir § 5 ci-dessous.
3. **Sync hardware** : récupère la config matériel via
   `/api/v1/hardware/config`. Si l'API dev est down, l'app utilise
   `10.0.0.20:9100` (MUNBYN) et `10.0.0.21:9100` (Zebra) par défaut.
4. **Test impression MUNBYN** : ping + kick tiroir test. Le tiroir
   doit s'ouvrir (si imprimante branchée).
5. **Test TPE SumUp** : ping backend. Bascule sur REST polling si BT
   non appairé.
6. Fin → login manager (`admin` / `vintiz2026` en dev) + PIN
   caissière (`1234` par défaut sur l'env dev seed).

## 5. Passer en environnement prod (rare, pour tester avant rollout)

L'APK debug pointe par défaut sur `api.dev.vintiz.fr`. Pour le faire
pointer sur prod sans rebuild :

```bash
# Pas possible en debug-signed. Pour le prod il faut un AAB signé +
# Managed Google Play privé (cf. docs/ANDROID_PROD_OPS.md § 8).
```

Si tu veux quand même un APK debug **pointant sur prod**, modifie
temporairement `apps/android/app-pos/build.gradle.kts` flavor `dev` →
poser `API_BASE_URL = "\"https://api.vintiz.fr/\""` et rebuild. **Ne
pas committer ce hack.**

## 6. Vérifier que l'app est installée

```bash
adb shell pm list packages | grep vintiz
# Devrait afficher : package:fr.vintiz.pos.dev
```

Ou sur la tablette : Settings → Apps → chercher "Vintiz".

## 7. Désinstaller

```bash
adb uninstall fr.vintiz.pos.dev
```

Ou sur la tablette : long-press sur l'icône → Uninstall.

## 8. Logs en live (adb logcat)

```bash
# Filtre sur les tags Vintiz uniquement (Timber)
adb logcat -s Vintiz:* VintizApp:* HttpClientFactory:*

# Logs complets de l'app
adb logcat --pid=$(adb shell pidof fr.vintiz.pos.dev)
```

## 9. Permissions au runtime

L'APK debug ne demande pas les permissions au premier lancement. Elles
arrivent quand la feature est utilisée :

| Permission | Quand |
|---|---|
| `INTERNET` + `ACCESS_NETWORK_STATE` | Toujours (déclarée install-time) |
| `CAMERA` | Première utilisation du scan camera ou capture photo produit |
| `NFC` | Tap NFC carte fidélité au POS |
| `BLUETOOTH_CONNECT/SCAN` | Activation SumUp SDK BT (V2, pas encore actif) |
| `POST_NOTIFICATIONS` | FCM push manager (Android 13+) |

Si une permission est refusée : Settings → Apps → Vintiz → Permissions
→ activer manuellement.

## 10. Problèmes courants

| Symptôme | Cause / solution |
|---|---|
| "App not installed" | APK corrompu (re-télécharger), ou conflit signature avec une install précédente (`adb uninstall` puis réinstaller) |
| App crash au lancement | Vérifier `adb logcat` pour la stack. Souvent : version Android < 8.0 (minSdk 26), ou archi incompatible (l'APK est universal ARM64 + ARMv7) |
| "Cannot connect to server" | API dev down ou réseau bloquant. Tester `curl https://api.dev.vintiz.fr/api/v1/health` |
| Imprimante non détectée | Settings → Onboarding → Sync hardware → re-tester |
| Tiroir ne s'ouvre pas | RJ-12 débranché. Tester depuis Settings > Matériel > "Kicker tiroir" |
| Push FCM non reçus | Normal en debug — `google-services.json` absent. Voir `ANDROID_PROD_OPS.md` § 1 pour activer en prod. |

## 11. Étapes suivantes pour la prod

Une fois l'APK debug validé en boutique :

1. Build AAB prod signé via CI (`gradlew :app:bundleProdRelease` avec
   les secrets keystore — cf. `ANDROID_PROD_OPS.md` § 6).
2. Upload Play Console Internal Testing.
3. Tests équipe 1 semaine.
4. Managed Google Play privé pour la boutique.
5. Rollout staged 10 → 50 → 100 %.

Détails complets : `docs/ANDROID_PROD_OPS.md` § 8.
