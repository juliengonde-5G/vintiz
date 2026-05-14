# Migration Vintiz POS — PWA Chrome → app Android native

**Statut** : planning, à exécuter après la phase de dev/test stabilisée
sur le PWA actuel (Lenovo Idea Tab Pro Gen 2 / Chrome Android).

**Pourquoi** : intégrer le `sumup-android-sdk` pour piloter le TPE
SumUp Solo en Bluetooth direct (sans dépendance Wi-Fi cloud + SumUp
API). Permet aussi d'embarquer plus tard d'autres SDK natifs si
besoin (lecteur de chèque, balance Bluetooth, etc.).

## Décision haut-niveau : 2 options

### Option A — Trusted Web Activity (TWA, ~3-5 jours)

Un wrapper Android minimal embarque le PWA Vintiz tel quel et ajoute
un pont JS↔natif pour appeler le SDK SumUp.

Structure :

```
android/
  app/
    src/main/
      java/fr/vintiz/pos/
        MainActivity.java         # LauncherActivity TWA
        SumUpBridge.java          # @JavascriptInterface pour le SDK
      AndroidManifest.xml         # déclare l'URL HTTPS du PWA
      assets/                     # rien — le PWA reste hébergé en ligne
    build.gradle                  # androidx.browser:browser + sumup-sdk
```

Le PWA détecte la présence du bridge :

```ts
declare global { interface Window { SumUpNative?: { /* ... */ } } }
if (window.SumUpNative) {
  // appelle le SDK natif via JS bridge
} else {
  // fallback cloud API (chemin actuel)
}
```

**Pros** :
- 90% du code reste partagé (le PWA tourne identiquement)
- 1 base de code, 1 deploy front
- Effort court (3-5 jours)
- Mise à jour transparente (le wrapper recharge l'URL HTTPS)

**Cons** :
- Le wrapper doit être publié sur Google Play (compte développeur 25 €
  une fois, validation 24-72h initialement)
- Les permissions Bluetooth doivent être déclarées dans le manifest
  Android
- Le bridge JS rajoute une couche d'abstraction

### Option B — App Android native pleine (~5-10 jours)

Le POS devient une vraie app Android native (Kotlin + Jetpack
Compose), qui appelle l'API Vintiz pour les données business. Le
back-office (`/dashboard`, `/inventory`, `/admin`, etc.) reste un
PWA.

**Pros** :
- Performance maximale (UI native fluide, transitions Android)
- Accès direct à toutes les API Android (NFC, scanner intégré,
  imprimantes BT…)
- Meilleure expérience hors-ligne (cache structuré, sync différée)

**Cons** :
- Duplication du POS (Vintiz POS Android + Vintiz Web POS)
- Effort 2x (5-10 jours pour la première version)
- Synchronisation des features entre les deux

## Recommandation : Option A

Démarrer en TWA. Reste léger, atteint l'objectif SumUp BT, peut
évoluer vers du natif full plus tard si besoin sans casser le code
existant.

## Plan d'exécution (Option A)

### Phase 1 — Boilerplate TWA (1 jour)

1. `npx @bubblewrap/cli init --manifest=https://app.vintiz.fr/manifest.json`
   génère le squelette Android Studio à partir du manifest PWA déjà
   en place (`apps/web/public/manifest.json`).
2. Vérifier le digital asset link : `.well-known/assetlinks.json`
   servi sur `https://app.vintiz.fr/` doit déclarer le SHA-256 du
   keystore de signature de l'APK — sinon le TWA s'ouvre dans une
   sandbox URL ("Custom Tabs") au lieu du mode app fullscreen.
3. Build local + sideload sur la Lenovo Idea Tab Pro pour valider :
   - launcher icon visible
   - splash screen Vintiz
   - URL barre cachée
   - le PWA tourne identiquement à Chrome.

### Phase 2 — Bridge SumUp (2-3 jours)

1. Ajouter la dépendance SumUp dans `build.gradle` :
   ```gradle
   implementation 'com.sumup:merchant-sdk:5.+'
   ```
2. Créer `SumUpBridge.java` exposant via `@JavascriptInterface` :
   - `login(token)` — connecte la session SumUp
   - `checkout(amount, currency, foreignTxId)` — déclenche le paiement
     en BT
   - `getReaderStatus()` — état live du TPE (paired/offline)
3. Côté PWA, créer `apps/web/src/lib/sumup-native.ts` qui détecte
   `window.SumUpNative` et expose une API homogène avec celle du
   chemin cloud (même shape de retour, le UI ne change pas).
4. Migrer `lib/sumup-service.ts` (frontend) pour piocher dans le
   bridge si présent, fallback cloud sinon.

### Phase 3 — Tests + déploiement Play Store (1-2 jours)

1. Tests manuels en boutique :
   - Vente CB via le bridge BT → TPE sonne, paiement validé,
     transaction signée NF525
   - Hors-ligne (TPE éteint) → fallback cloud, sinon erreur explicite
   - Réinstallation app → re-pairing SumUp facile
2. Compte développeur Google Play (25 € one-time si pas déjà créé)
3. Upload de l'AAB signé, fiche store, screenshots
4. Validation Google (~24-72h la première fois)

### Phase 4 — Sortie progressive (continue)

1. Le PWA reste accessible sur `app.vintiz.fr` pour le back-office et
   en secours
2. La tablette caisse installe le TWA via Play Store + désactive le
   raccourci PWA Chrome
3. Le manager peut continuer à utiliser le navigateur classique
   pour `/dashboard`, `/inventory`, `/admin`

## Risques / vigilance

- **Asset links cassés** : si `assetlinks.json` n'est pas servi en
  HTTPS avec le bon SHA-256, le TWA dégrade en Chrome Custom Tab et
  la fonctionnalité BT du SDK n'est plus accessible. Vérifier le
  servir via `nginx -s reload` puis tester avec
  `https://developers.google.com/digital-asset-links/tools/generator`.
- **Permissions BT runtime** : Android 12+ exige `BLUETOOTH_CONNECT`
  et `BLUETOOTH_SCAN` en runtime. Gérer la première demande de
  permission dans le bridge.
- **SDK SumUp lourd** : ajoute ~10 MB à l'APK. Pas bloquant mais à
  noter pour la fiche Play Store.
- **Versions Android** : le SDK SumUp exige minSdkVersion=21
  (Android 5.0+). La Lenovo Idea Tab Pro tourne sur Android 14 → OK.

## À discuter ensemble avant de démarrer

- [ ] Compte développeur Google Play : qui le crée (Julien) ?
- [ ] Keystore de signature : généré une fois, sauvegardé hors site
- [ ] Nom de l'app store : "Vintiz POS" ? "Vintiz Caisse" ?
- [ ] Visibilité Play Store : public ? privé (managed Google Play) ?
- [ ] Maintenance : qui pousse les updates Android ? CI/CD à
      configurer ?

## État courant (non-migration)

Le PWA en mode Wi-Fi cloud SumUp fonctionne et reste **la solution
courante**. Le check de connectivité (`GET /api/pos/payments/cb/ping`,
banner POS) introduit en parallèle de ce planning alerte le caissier
quand le TPE est offline — sans nécessiter de migration native.
