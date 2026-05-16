# Vintiz Android — guide utilisateur

Cette doc s'adresse à l'équipe boutique (caissière, manager) et à
l'ops Mac dev qui installe / met à jour l'app sur les tablettes.

Pour le plan technique de la migration, voir
[`MIGRATION_ANDROID_NATIVE.md`](MIGRATION_ANDROID_NATIVE.md).
Pour la structure et la liste des modules livrés, voir
[`../apps/android/README.md`](../apps/android/README.md).

## 1. Premier démarrage tablette (onboarding 4 étapes)

À la 1ʳᵉ ouverture de l'app, l'écran *Bienvenue* s'ouvre
automatiquement. Le flux dure ~2 min :

1. **Bienvenue** — explication du déroulé.
2. **Environnement serveur** — choisir `DEV` (test) ou `PROD`
   (`api.vintiz.fr`). En boutique : toujours `PROD`. En siège pour
   tester une nouvelle version : `DEV` avant rollout.
3. **Matériel** — bouton « Synchroniser » qui appelle
   `/api/v1/hardware/config` et récupère les IPs de l'imprimante
   ticket, l'imprimante étiquette et la config tiroir (kick pin,
   timing). Si l'API ne répond pas, l'app reste utilisable mais le
   manager devra recharger plus tard depuis *Réglages*.
4. **Fin** — la 1ʳᵉ install est faite. L'app passe au login.

L'onboarding n'est pas relancé tant que la sélection d'environnement
n'est pas remise par défaut. Pour relancer manuellement : *Réglages →
À propos → Refaire l'onboarding* (à venir, sprint UX).

## 2. Connexion quotidienne

1. **Manager** — `username` + `password` (compte créé via web admin
   ou *Admin → Utilisateurs* sur la tablette). Le token JWT dure
   8 h, renouvellement automatique tant que l'app est active.
2. **PIN caissière** — code 4 chiffres sur le NumPad. Le caissier
   actuel apparaîtra sur les tickets, dans l'audit log et dans les
   Z-reports. Si plusieurs personnes se relayent, *Caisse → ⚙* permet
   de basculer.

Rate-limit : 10 tentatives login / 5 min / IP, puis HTTP 429 avec
`Retry-After`. L'app affiche « Trop de tentatives, réessayer dans Xs ».

## 3. Encaisser une vente

### 3.1 Identifier la cliente (optionnel)
- **Carte fidélité NFC** — tap au dos de la tablette → fiche cliente
  ouverte dans le panneau latéral (points, gain panier, rachat max).
- **Saisie clavier** — *Caisse → champ "Identifier cliente"* : email,
  téléphone, ou numéro `V######`.

### 3.2 Ajouter les articles
- **Douchette Inateck** (USB-OTG) — scan = ajout au panier instantané.
- **Caméra ML Kit** (fallback) — activer dans *Réglages → Backends*,
  puis ouvrir le scanner via le bouton dédié.
- **Recherche manuelle** — taper dans le champ search (≥ 2 chars).

### 3.3 Remises (optionnel)
- Toucher la ligne dans le panier → ouvre le sélecteur de remise
  (0 / 5 / 10 / 15 / 20 / 30 %). Le serveur recalcule au commit.

### 3.4 Choisir le paiement
- **Espèces** — saisir le montant tendu, l'app affiche le rendu monnaie.
- **CB** — le TPE SumUp Solo Wi-Fi reçoit la transaction (push direct
  si `SUMUP_READER_ID` configuré). Statut affiché en live (PENDING →
  PAID/FAILED/CANCELLED). Timeout 90 s.
- **Chèque** — saisie référence libre.
- **Avoir** — débit du solde fidélité cliente.

### 3.5 Ticket post-vente
La modal *Ticket vente* propose :
- **Imprimer (MUNBYN)** — envoie les bytes ESC/POS pré-signés
  serveur ; ouvre automatiquement le tiroir si la vente comporte du
  cash.
- **Fermer sans ticket** — utile pour les ventes sans demande client.

## 4. Mode hors-ligne

Si le réseau tombe en pleine vente :
1. **Encaissement local** — la vente est immédiatement persistée en
   queue locale Room avec un `client_uuid` unique.
2. **Drain automatique** — toutes les 15 min (ou dès qu'une condition
   réseau revient), le `DrainTransactionsWorker` rejoue les ventes
   manquantes. Le serveur déduplique via `client_uuid`.
3. **Affichage caisse** — message « Vente enregistrée hors-ligne —
   sera renvoyée plus tard ».

⚠️ **Limites V1** : les paiements CB nécessitent le réseau Wi-Fi pour
le TPE SumUp (V2 avec SDK BT direct permettra le mode 100 % offline).
En attendant, mode dégradé recommandé : espèces uniquement si Wi-Fi
KO.

## 5. Caisse — ouverture / fermeture

### Ouverture
*Caisse → Ouvrir caisse* → saisir le fond initial. Crée un
`CashDrawer` côté backend.

### Fermeture
*Caisse → Fermer caisse* → saisir le montant compté.
Z-report généré automatiquement :
- Total ventes par méthode (espèces / CB / chèque)
- Solde attendu (fond + espèces - rendus)
- Écart (positif = surplus, négatif = manquant)
- Hash NF525 + signature serveur

Le Z-report est consultable dans *Admin → Z-Reports* (manager).

## 6. Notifications push manager

Activées sur le smartphone manager (pas la tablette caisse) :
- Vente > seuil défini (à venir, Settings)
- Fermeture de caisse + Z-report
- Alerte stock bas
- Erreur paiement SumUp persistante

Réception via FCM. Le device s'enregistre au 1er onResume avec
`/api/v1/notifications/fcm-token`. Si le manager utilise plusieurs
appareils (Pixel + iPad), chaque device a son token.

## 7. Mode kiosque (tablette caisse)

À activer uniquement sur la tablette caisse pour empêcher l'accès aux
autres apps Android :

```
adb shell dpm set-device-owner fr.vintiz.pos/.kiosk.VintizDeviceAdmin
```

Ou via une solution MDM (Headwind / ScaleFusion / Miradore free tier).

Une fois device-owner accordé, `KioskManager.enable()` est appelé au
`onResume` du POS (pas des autres écrans — l'admin reste libre).

## 8. Dépannage rapide

| Symptôme | Cause probable | Action |
|---|---|---|
| Impression ticket KO | MUNBYN éteinte ou réseau Wi-Fi KO | Vérifier voyant MUNBYN, IP dans *Réglages → Imprimantes*, tester ping |
| Tiroir ne s'ouvre pas | Câble RJ-12 débranché ou kick désactivé | *Réglages → Caisse → Test kick* |
| Douchette muette | Câble USB-OTG ou clavier soft virtuel actif | Désactiver clavier soft, rebrancher câble |
| TPE SumUp ne sonne pas | TPE éteint ou pas appairé sur le compte | Pousser un test depuis *Réglages → Paiement → Test* |
| « Cliente non reconnue » NFC | Carte non enregistrée côté backend | Demander au manager d'ajouter la carte (champ `nfc_uid` sur fiche) |
| Login refuse 5×, message Retry-After | Rate-limit IP atteint | Attendre le délai, vérifier les identifiants |
| App lance le mauvais environnement | DEV vs PROD inversé | *Réglages → Backends → Environnement* |

## 9. Mise à jour de l'app

- **Play Console Internal Testing** — pour les tests équipe (rolling).
- **Managed Google Play privé** — canal boutique (rollout staged
  10/50/100 %).
- **In-App Update IMMEDIATE** — déclenchée au `onResume` si une
  version critique est dispo. L'utilisateur ne peut pas l'ignorer.
- Le `keystore release` est stocké hors site (1Password "Vintiz /
  Android signing") — sans lui, impossible de publier une update.

Voir [`MIGRATION_ANDROID_NATIVE.md`](MIGRATION_ANDROID_NATIVE.md) §4.2
pour les comptes et signing keys, §5.3 pour le monitoring Crashlytics.

## 10. Conformité

- **NF525** — toute la chaîne fiscale (hash, signature, export DGFiP)
  reste côté backend `apps/api/app/services/fiscal.py`. L'app ne signe
  rien localement.
- **RGPD** —
  - JWT chiffré Android Keystore (AES256-GCM).
  - Cache clientes purgé après 30 j sans activité (`PurgePiiWorker`).
  - Bouton *Réglages → Effacer données locales* (à venir, sprint UX).
  - Cloud backup + device-to-device désactivés pour les fichiers
    sensibles (`backup_rules.xml`, `data_extraction_rules.xml`).
- **PCI** — aucune donnée carte ne transite par l'app : tout reste
  dans le TPE SumUp.
