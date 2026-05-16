# Vintiz Android — guide opérateur de mise en prod

Audience : Julien + l'ops Mac qui pilote la première installation
boutique. Couvre tout ce que **Claude Code ne peut pas faire** :
comptes, signatures, devices physiques, MDM, déploiement Play Console.

Pour le plan technique, voir
[`MIGRATION_ANDROID_NATIVE.md`](MIGRATION_ANDROID_NATIVE.md).
Pour le guide caissière, voir
[`ANDROID_APP.md`](ANDROID_APP.md).
Pour l'audit sécurité, voir
[`ANDROID_SECURITY_OWASP.md`](ANDROID_SECURITY_AUDIT.md).

---

## 1. Pré-requis comptes

| Compte | Coût | Qui crée | Action |
|---|---|---|---|
| Google Play Console (Vintiz SAS) | 25 € one-time | Julien | Créer compte développeur entreprise, identité Vintiz SAS. |
| Firebase Project "vintiz-pos-prod" | Gratuit | Julien | Activer FCM + Crashlytics + Analytics. Télécharger `google-services.json` → coller dans `apps/android/app/prod/`. |
| Firebase Project "vintiz-pos-dev" | Gratuit | Julien | Idem → `apps/android/app/dev/`. |
| SumUp Developer Portal | Gratuit | Julien | Récupérer App ID + Affiliate Key Android (distinct du web). |
| MDM (Headwind / ScaleFusion / Miradore free) | Gratuit < 25 devices | Julien | Optionnel mais recommandé pour le mode kiosque tablette caisse. |

Empreintes SHA-1 / SHA-256 du keystore release à fournir au Firebase
Console (Project Settings → Your apps → Add fingerprint).

## 2. Keystore release

```bash
cd ~/Documents/vintiz-keystore   # créer le dossier hors du repo
keytool -genkey -v \
  -keystore vintiz-release.jks \
  -keyalg RSA -keysize 4096 \
  -validity 25000 \
  -alias vintiz-release
```

Réponses :
- CN = Vintiz SAS
- OU = Caisse Vintiz Vernon
- O = Vintiz SAS
- L = Vernon, C = FR
- Validité : 25000 jours (~68 ans) pour ne jamais avoir à renouveler

⚠️ **Stockage obligatoire** — sans ce keystore, plus aucune mise à
jour Play Store n'est possible et il faut publier une nouvelle app
(perte des installs, comptes, abonnements) :

- 1Password coffre **"Vintiz / Android signing"** : `vintiz-release.jks`
  en base64 + mot de passe + alias password.
- Sauvegarde papier dans le coffre Vintiz : QR code des 3 secrets,
  recouvert d'une enveloppe scellée.

Empreintes à archiver dans le même coffre :

```bash
keytool -list -v -keystore vintiz-release.jks -alias vintiz-release \
  | grep "SHA"
```

→ noter `SHA-1` et `SHA-256`.

## 3. Setup Mac dev (Apple Silicon, première install)

```bash
# 1. JDK 17 ARM64 + Android Studio
brew install --cask zulu@17 android-studio

# 2. SDK Android Platform 34 + 35 + Build-Tools via SDK Manager Android Studio
# Tools → SDK Manager → Android 14 (API 34) + 15 (API 35) + Build-Tools 35.0.0

# 3. AVD ARM64 (les images x86_64 sont 10x trop lentes sur M-series)
sdkmanager "system-images;android-34;google_apis;arm64-v8a"

# 4. Outils ops
brew install gh fastlane pre-commit

# 5. Clone + bootstrap Gradle wrapper (1 seule fois, à committer ensuite)
git clone git@github.com:juliengonde-5G/vintiz.git
cd vintiz/apps/android
gradle wrapper --gradle-version 8.11.1 --distribution-type bin
git add gradle/wrapper gradlew gradlew.bat
git commit -m "build(android): gradle wrapper 8.11.1"
git push

# 6. Premier build local
./gradlew :app:assembleDevDebug
```

Variables d'env nécessaires pour les builds release :

```bash
# ~/.zshrc.local (jamais committé)
export VINTIZ_KEYSTORE_PATH=~/Documents/vintiz-keystore/vintiz-release.jks
export VINTIZ_KEYSTORE_PASSWORD='...'
export VINTIZ_KEY_PASSWORD='...'
export ANDROID_HOME=~/Library/Android/sdk
export PATH=$PATH:$ANDROID_HOME/platform-tools
```

## 4. Matériel boutique

| Composant | Référence | Quantité | Où |
|---|---|---|---|
| Tablette caisse | Lenovo Tab M11 (Android 14) | 1 (+ 1 secours) | Fixée bras articulé caisse |
| Smartphone manager | Pixel 7a (Android 14) | 1 | Julien personnel |
| Tablette rayon | Galaxy Tab A9 8" | 1 | Vendeuse |
| Imprimante ticket | MUNBYN 047P-WiFi | 1 | DHCP fixe |
| Imprimante étiquettes | Zebra ZD421d | 1 | DHCP fixe |
| Tiroir-caisse | Safescan SD-4141 | 1 | RJ-12 sur MUNBYN |
| Douchette | Inateck BCST-35 | 1 | USB-OTG tablette |
| TPE | SumUp Solo Wi-Fi | 1 | Compte SumUp existant |

### 4.1 Réseau LAN boutique

DHCP réservations dans la box (FreeBox Pop ou Bbox Ultym) :

```
MUNBYN 047P-WiFi    : MAC XX:XX:XX → 10.0.0.20
Zebra ZD421d        : MAC YY:YY:YY → 10.0.0.21
Tablette caisse     : ZZ:ZZ:ZZ    → 10.0.0.30
SumUp Solo          : (libre, géré côté SumUp)
```

`apps/api/data/hardware.json` doit pointer sur ces 2 IPs avant le
1ᵉʳ boot tablette. Sinon onboarding tablette → Settings → onglet
Matériel → saisir manuellement → bouton "Recharger depuis serveur".

### 4.2 Hotspot 4G failover

Plan Free Mobile à 19,99 €/mois ou Bbox 4G de secours. À configurer
sur un routeur 4G TP-Link MR400 branché en backup WAN. Test mensuel
recommandé.

## 5. Configuration MDM kiosque tablette caisse

Headwind MDM ou ScaleFusion (free tier < 25 devices). Étapes :

1. Enrôler la tablette dans le MDM via QR code de provisioning.
2. Déclarer `fr.vintiz.pos` comme Device Owner.
3. Activer Lock Task Mode pour `fr.vintiz.pos` uniquement.
4. Bloquer Play Store, paramètres système, notification panel.
5. Forcer l'orientation paysage.

Alternative ADB (sans MDM, pour tests) :

```bash
adb shell dpm set-device-owner fr.vintiz.pos/.kiosk.VintizDeviceAdmin
```

⚠️ `set-device-owner` ne fonctionne que sur une tablette **factory
reset** sans aucun compte Google enregistré.

## 6. CI/CD GitHub Actions

`.github/workflows/android.yml` est déjà committé. Secrets repo à
ajouter dans GitHub → Settings → Secrets and variables → Actions :

```
VINTIZ_KEYSTORE_BASE64       = base64 du .jks (cat vintiz-release.jks | base64)
VINTIZ_KEYSTORE_PASSWORD     = mot de passe du store
VINTIZ_KEY_PASSWORD          = mot de passe de la clé
PLAY_SERVICE_ACCOUNT_JSON    = JSON du Service Account Play Console
FIREBASE_TOKEN               = `firebase login:ci` token (optionnel pour App Distribution)
```

Workflow `build-aab-prod` se déclenche sur tag `android-vX.Y.Z`,
signe et uploade automatiquement vers Play Console Internal Testing.

## 7. Bootstrap équipe API backend

Demandes ouvertes côté `apps/api` à valider AVANT 1ʳᵉ release Android
(cf. `docs/MIGRATION_ANDROID_NATIVE.md` §4.4) :

- [x] Préfixer toutes les routes `/api/v1/` avec `/api/` alias temporaire (déjà fait, commit `0139d94`)
- [ ] Endpoint `POST /api/v1/notifications/fcm-token` (table `fcm_devices`)
- [ ] Endpoint `POST /api/v1/notifications/test` (push debug manager)
- [ ] Enrichir `apps/api/app/core/audit_context.py` pour tracer
      `X-Client` (vintiz-web / vintiz-site / vintiz-android/X.Y.Z)
- [ ] Exposer `GET /api/v1/openapi.json` en CI (déjà disponible, à
      câbler sur la génération client Kotlin)
- [ ] Rate-limit séparé pour `/api/v1/auth/refresh` (mobile l'appelle
      plus souvent que web)
- [ ] Optionnel V2 : SSE `/api/v1/events/stream` pour les push
      manager en temps réel sans round-trip FCM

## 8. Rollout Play Console (séquence)

### 8.1 Internal Testing — semaine S+0 à S+1

- Uploader l'AAB `bundleProdRelease` signé.
- Tester équipe (Julien + ops) sur 5 devices Android distincts.
- Crash-free > 99 % sur 7 jours avant de passer à la suite.

### 8.2 Managed Google Play (privé) — semaine S+2

- Créer une organisation Managed Google Play.
- Publier l'app en `Privately distributed` à la boutique de Vernon.
- Installer sur tablette caisse + smartphone manager + tablette rayon.
- Période de pilotage 1-2 semaines avant le passage à 100 %.

### 8.3 Production publique — pas avant 1 mois en kiosque privé

- Si jamais un autre point de vente Vintiz s'ouvre, on déplace
  l'app en Production publique avec rollout staged 10 → 50 → 100 %.
- En attendant, **rester en privé**.

## 9. Monitoring post-prod

| Outil | KPI | Seuil alerting |
|---|---|---|
| Firebase Crashlytics | Crash-free | < 99 % sur 24 h → Slack #vintiz-ops |
| Firebase Performance | `pos_transaction_completed` médiane | > 6 s online → enquête |
| Play Console Vitals | ANR rate | > 0.5 % → release block |
| Logs serveur (`apps/api`) | Taux d'erreur `/api/v1/pos/transactions` | > 1 % sur 5 min → page |
| WorkManager dashboard | Drain queue offline | > 5 ventes en queue depuis > 1 h → ping manager |

## 10. Procédure de mise à jour (rolling)

```
1. Commit + push sur main.
2. CI build-aab-prod auto-déploie en Internal Testing (signé).
3. Test équipe 24 h.
4. Tag `android-vX.Y.Z` → CI publie en Managed Google Play (canal stable privé).
5. Rollout staged 10 → 50 → 100 % sur 3 jours.
6. Crashlytics monitoré pendant 1 semaine post-rollout 100 %.
```

In-App Update IMMEDIATE force l'update pour les versions critiques
(failles sécurité, NF525). Sinon Play Store gère naturellement.

## 11. Procédure d'incident

### 11.1 Caisse bloquée en boutique

1. Vendeuse passe en mode dégradé manuel (papier + caisse mécanique).
2. Julien appelé immédiatement.
3. Diagnostic : ouvrir Crashlytics + logs serveur, isoler le commit
   coupable.
4. Rollback Play Console : Production → halt rollout → install
   précédent automatique au reboot tablette (In-App Update sait
   downgrader si la version Play Console est inférieure).
5. Post-mortem dans `docs/INCIDENTS/` (à créer).

### 11.2 Vol / perte tablette caisse

1. Révoquer le device dans le MDM (efface l'app à distance).
2. Révoquer tous les JWT manager actifs côté backend (`apps/api`
   → endpoint admin à brancher si pas déjà fait).
3. Changer les mots de passe SumUp + Firebase si la tablette n'était
   pas en mode kiosque.
4. Le cache local clientes est chiffré (EncryptedSharedPreferences +
   Keystore Android) — bas risque PII.

### 11.3 Backend `apps/api` indisponible

L'app reste fonctionnelle pour les ventes espèces grâce à la queue
offline `client_uuid` + `DrainTransactionsWorker`. Le SumUp reste
opérationnel tant que le TPE a son propre Wi-Fi. Les Z-reports sont
calculés côté backend → bloqués jusqu'au retour. Documenter à
l'équipe boutique qu'on ne ferme **pas** la caisse en mode dégradé,
on attend le retour API et on clôture après.

## 12. Conformité — actions à faire avant prod

- [ ] **NF525** : faire valider par l'organisme certificateur que
      l'ajout d'un client Android (qui appelle la même API certifiée
      `apps/api`) ne requiert pas re-certification.
- [ ] **RGPD CGU app** : rédiger les CGU spécifiques à l'app dans la
      fiche Play Store + une page interne `/account/cgu-android`.
- [ ] **Politique de stockage local** : annexer aux CGU le tableau
      détaillé (cache produits illimité non-PII / cache clients
      30 j RGPD / JWT chiffré Keystore / Crashlytics opt-in
      manager / opt-out par défaut tablette caisse).
- [ ] **Délégué à la Protection des Données** : `dpo@solidarite-textiles.fr`
      dans CGU + écran *Réglages → À propos* → mailto: bouton.
- [ ] **Cert-pinning prod** : voir `ANDROID_SECURITY_AUDIT.md` §3.3.

## 13. Annexe — checklist J-1 avant 1ʳᵉ mise en boutique

- [ ] Tablette caisse factory-reset
- [ ] Compte Google Workspace Vintiz enrôlé via MDM
- [ ] Tablette en Lock Task Mode `fr.vintiz.pos` actif
- [ ] APK release signé installé via Managed Google Play privé
- [ ] Wi-Fi boutique configuré + IP statiques DHCP MUNBYN / Zebra
- [ ] TPE SumUp Solo appairé et test paiement OK
- [ ] MUNBYN ESC/POS testée (impression + kick tiroir)
- [ ] Zebra ZPL testée (étiquette test)
- [ ] Inateck BCST-35 branchée USB-OTG + scan test
- [ ] Caissière formée 30 min (parcours vente espèces + CB)
- [ ] Manager formé 1 h (admin + Z-reports + fidélité)
- [ ] Fiche dépannage imprimée à la caisse
- [ ] Hotspot 4G failover testé (Wi-Fi coupé → tablette toujours OK)
- [ ] Crashlytics et Play Console Vitals monitorés sur smartphone manager
- [ ] Premier `SyncHardwareConfigWorker` validé au boot (IPs chargées)
