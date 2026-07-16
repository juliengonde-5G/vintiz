# Déploiement — Programme fidélité Vintiz

Plan d'action pour passer le programme fidélité de l'environnement
développement à la production en boutique.

## Prérequis techniques

| Item | État | Détails |
|---|---|---|
| Code adhérent V###### | ✅ Implémenté | `apps/api/app/services/membership_id.py` |
| Backend gestion fidélité | ✅ | `/api/crm/clients/{id}/loyalty/*` |
| Souscription au POS | ✅ | Modal `/pos > Souscrire` (3 modes : free / paid / first_purchase) |
| Plage temporelle config fidélité | ✅ | `/settings > Fidélité > Limiter à une plage temporelle` |
| Identification au POS | ✅ | Scan QR / membership / email / téléphone / **CP + nom** (Lot 3) |
| CTA « Proposer la carte » | ✅ | Bandeau magenta sur panier non-vide sans client identifié (Lot 3) |
| Mention sur ticket caisse | ✅ | `services/receipt.py` — nom + N° + points + would_earn pour non-membres |
| Apple Wallet | 🟡 | Code prêt — nécessite cert .p12 + WWDR + team ID |
| Google Wallet | 🟡 | Code prêt — nécessite Service Account JSON + issuer ID |
| QR fallback | ✅ | `/api/crm/account/wallet/qr.png` toujours actif |
| Magic-link OTP email | ✅ | Brevo / SMTP / simulation — UI dans `/settings > Communication` |
| Magic-link OTP SMS | ✅ | Twilio (ou simulation) — Lot 6 |
| Cron expiration 24 mois | ✅ | `loyalty_expiry.py`, daily 03:30 |

## Étapes ouverture publique

### 1. Configurer la passerelle email (J-7)

1. Créer un compte gratuit sur https://app.brevo.com (300 emails/jour suffisent).
2. Vérifier le domaine `vintiz.fr` (DKIM/SPF/DMARC) — bloque-spam critique.
3. Récupérer la clé API `xkeysib-…` dans Brevo > SMTP & API > API Keys.
4. La saisir dans **/settings > Communication > Clé API Brevo**, puis cliquer
   **« Envoyer un email de test »** depuis l'UI : si OK, c'est branché.

### 2. Activer Apple Wallet (J-7, optionnel mais recommandé)

1. Compte Apple Developer (99 $/an).
2. Créer le Pass Type ID `pass.fr.vintiz.loyalty` dans Certificates,
   Identifiers & Profiles.
3. Générer le certificat de signature → exporter en `.p12` avec mot de passe.
4. Télécharger le cert intermédiaire **AppleWWDRCAG4.cer**, le convertir
   en PEM (`openssl x509 -inform DER -in AppleWWDRCAG4.cer -out wwdr.pem`).
5. Déposer les fichiers dans `/secrets/` du serveur et poser :

```env
WALLET_TEAM_IDENTIFIER=ABCDE12345
WALLET_PASS_TYPE_IDENTIFIER=pass.fr.vintiz.loyalty
WALLET_APPLE_P12_PATH=/secrets/vintiz_pass.p12
WALLET_APPLE_P12_PASSWORD=...
WALLET_APPLE_WWDR_PATH=/secrets/wwdr.pem
WALLET_PASS_ASSETS_DIR=/opt/vintiz/wallet-assets/   # icon.png, icon@2x.png, logo.png
```

6. Smoke test : `curl -i "https://api.vintiz.fr/api/crm/account/wallet/apple?email=test@vintiz.fr"`
   → `Content-Type: application/vnd.apple.pkpass` + binaire ZIP.

### 3. Activer Google Wallet (J-7, optionnel)

1. Console https://pay.google.com/business/console > Issuer ID (19 chiffres).
2. Créer un Service Account avec le rôle **Wallet Object Issuer**.
3. Télécharger la clé JSON, déposer en `/secrets/google-wallet-sa.json`.
4. Poser `WALLET_GOOGLE_ISSUER_ID=…` et `WALLET_GOOGLE_SERVICE_ACCOUNT_JSON=/secrets/google-wallet-sa.json`.

### 4. Hardware POS (J-3)

Voir `docs/POS_TEST_BARCODES.md`. À valider :
- Imprimante MUNBYN connectée + IP renseignée → ticket de test OK.
- Tiroir Safescan → kick OK depuis `/settings > Matériel > Tester`.
- Imprimante SATO étiquettes → label de test OK.
- Douchette Inateck → scan d'un produit ajoute au panier au POS.
- TPE SumUp Solo + reader_id renseigné dans `/settings > Paiement` → push OK.

### 5. Choisir la mécanique fidélité (J-1)

Dans **/settings > Fidélité** :

- **Mode** : libre choix parmi *gratuite* / *payante* / *offerte 1er achat*.
- **Plage temporelle** : facultatif. Hors plage → retour au mode gratuit
  par défaut (utile pour une opération « adhésion offerte » pendant 1 mois).
- 1 € dépensé sur un produit hors promotion, solde ou remise = 1 point.
- Chaque tranche de 100 points génère un chèque cadeau de 5 €, utilisable comme moyen de paiement au POS et valable 6 mois.
- Les points expirent après 24 mois sans activité. Un retour annule les points correspondants et, si nécessaire, le bon non utilisé associé.

### 6. Formation caissière (J-1, 30 minutes)

Démo par l'équipe technique :
1. Souscrire un client de A à Z (POS → Modal souscription → ticket avec V######).
2. Identifier un client par scan QR / email / téléphone / **CP + nom** (Lot 3).
3. Voir le panneau companion : compteur points, suggestions, alertes,
   bandeau « Vous gagneriez X pts » côté client non-membre.
4. Renvoyer un ticket par email ou SMS.
5. Reconnaître les alertes RFM (`at_risk`, `champion`, `hibernating`).

### 7. Communication clients (J)

- Bannière site `vintiz.fr` (déjà en place sur landing v3 — Lot 4).
- Story Instagram + post de la semaine (générés par `/ia/marketing`).
- Affichage en boutique : cadre A4 « Carte fidélité offerte ».

## KPIs à suivre les 30 premiers jours

| KPI | Cible J+30 | Source |
|---|---|---|
| Taux de souscription / cliente identifiée | > 40 % | `/admin > Sessions caisses` + `/clients` |
| Nombre cartes V###### actives | 50 | `SELECT COUNT(*) FROM loyalty_accounts WHERE active = true` |
| Taux de retour membre fidélité | > 25 % | RFM via `/api/admin/rfm/run` |
| Chèques cadeaux de 5 € émis vs convertis | > 60 % conversion | `coupons` + `transactions` |
| Wallet pass téléchargés | > 30 % des membres | logs Caddy `/api/crm/account/wallet/*` |
| OTP envoyés / vérifiés | ratio > 80 % | logs `magic_link` |

## Procédure de désactivation rapide

Si bug en prod :
1. **/settings > Fidélité > Mode = `free`** (toujours plus permissif que `paid`).
2. **/settings > Communication > Provider = `simulation`** stoppe les envois
   réels (les codes ne partent plus, l'opérateur le voit).
3. **Bandeau caissier** : aucun moyen de désactiver côté UI ; reverter le
   commit Lot 3 du POS si vraiment nécessaire.
4. Apple/Google Wallet : retirer les certs des variables d'env → /apple
   répond 503 immédiatement.

## Annexes

- `/admin/audit-logs` : toutes les souscriptions / activations / désactivations
  laissent une trace audit.
- `/admin/data-quality` : surveiller `events_log` pour détecter une dérive.
- `scripts/reset-prod.sh` : remise à zéro complète (idempotent, à n'utiliser
  que pendant la phase pré-ouverture).
