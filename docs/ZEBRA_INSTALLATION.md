# Installation imprimante étiquettes — Zebra ZD421d

Guide de mise en service de l'imprimante d'étiquettes **Zebra ZD421d**
(ZPL II, thermique direct 203 dpi, format Vintiz 25×52 mm).

Deux modes de fonctionnement sont supportés. Choisis selon **où tourne
l'API Vintiz** :

| Mode | Quand l'utiliser | Comment ça marche |
|---|---|---|
| **Réseau local** | L'API tourne sur le **même réseau** que l'imprimante (ex. serveur en boutique). | L'API ouvre une connexion TCP directe vers l'IP de l'imprimante, port 9100. |
| **Cloud (Weblink)** | L'API tourne **hors site** (cloud / VPS) et ne peut pas joindre l'imprimante derrière la box. | L'imprimante se connecte **en sortie** à Zebra Data Services ; l'API pousse le ZPL via l'API REST `SendFileToPrinter`. |

> **Pourquoi pas le MQTT ?** Le MQTT natif des imprimantes Zebra ne sert
> qu'à la **gestion / supervision** : il **ne peut pas** recevoir de
> travaux d'impression. La voie native pour « l'imprimante se connecte au
> cloud et reçoit du ZPL » est **Weblink**, pas MQTT.

---

## 0. Pré-requis matériels (communs aux deux modes)

1. Brancher l'alimentation de la ZD421d.
2. Charger un rouleau d'étiquettes 25×52 mm (thermique direct — pas de
   ruban). Vérifier le sens : le côté thermosensible vers la tête.
3. Brancher l'imprimante au réseau :
   - **RJ45** sur la box / le routeur (recommandé, stable), **ou**
   - **Wi-Fi** (voir Zebra Printer Setup Utility).
4. Récupérer son **adresse IP** et son **numéro de série** :
   - Appui long sur le bouton **FEED** → l'imprimante imprime une étiquette
     de configuration réseau (IP, masque, n° de série `SN`).
   - Ou via l'app *Zebra Printer Setup Utility* (Android / iOS / Windows).

> ⚠️ `192.168.1.1` est en général l'adresse de **la box**, pas de
> l'imprimante. L'imprimante a sa propre IP (ex. `192.168.1.50`).

---

## 1. Mode réseau local (TCP 9100)

À utiliser **uniquement** si l'API Vintiz tourne sur le même réseau que
l'imprimante.

1. Donner à l'imprimante une **IP fixe** (réservation DHCP sur la box,
   recommandé, ou IP statique sur l'imprimante).
2. Dans Vintiz : **/settings → Matériel → Imprimante d'étiquettes**.
   - Mode de connexion : **Réseau local (TCP 9100)**.
   - Adresse IP : l'IP de l'imprimante. Port : `9100`.
   - Cocher **Activer l'imprimante Zebra**, **Enregistrer**.
3. Cliquer **Imprimer une étiquette de test**.

Variables d'environnement équivalentes (optionnel) :

```env
ZEBRA_CONNECTION=network
ZEBRA_PRINTER_IP=192.168.1.50
ZEBRA_PRINTER_PORT=9100
```

---

## 2. Mode cloud (Weblink + SendFileToPrinter)

À utiliser quand l'API Vintiz tourne **hors site** (VPS / cloud) : elle ne
peut pas ouvrir de socket vers l'imprimante derrière la box. C'est
l'imprimante qui initie la connexion **sortante** vers le cloud Zebra.

### 2.1 Créer un compte Zebra Data Services + clé API

1. Aller sur le **portail développeur Zebra** (`developer.zebra.com`),
   créer un compte / une organisation (**tenant**).
2. Créer une application utilisant l'API **SendFileToPrinter** → récupérer
   la **clé API** (`apikey`).
3. Noter le **numéro de tenant** (compte) — il est demandé par l'API.

### 2.2 Enrôler l'imprimante (Weblink)

1. Dans le portail, générer le **code d'enrôlement** de l'imprimante : on
   obtient un fichier de config (JSON) qui pose le réglage
   `weblink.ip.conn1.location` sur une URL du type :
   ```
   https://savanna-device.zpc.zebra.com/weblink/connect?...
   ```
2. Envoyer ce fichier à l'imprimante via l'app **Zebra Printer Setup
   Utility** (Android / iOS / Windows), connectée à la même imprimante.
3. L'imprimante ouvre alors une connexion TLS **sortante** persistante vers
   Zebra Data Services et y reste connectée. Elle peut rester en RJ45.

> Vérification : dans le portail Zebra, l'imprimante doit apparaître
> « connectée / online » une fois l'enrôlement effectué.

### 2.3 Configurer Vintiz

Dans **/settings → Matériel → Imprimante d'étiquettes** :

1. Mode de connexion : **Cloud Zebra (Weblink + SendFileToPrinter)**.
2. Renseigner :
   - **Clé API Zebra Data Services** (`apikey`).
   - **Tenant** (n° de compte Zebra).
   - **N° de série imprimante** (le `SN` de l'étiquette de config).
3. Cocher **Activer l'imprimante Zebra**, **Enregistrer**.
4. Cliquer **Imprimer une étiquette de test**.

> La clé API est **masquée** après enregistrement (on n'affiche que les 4
> derniers caractères). Laisser le champ vide pour conserver la clé déjà
> enregistrée ; ne le remplir que pour la **changer**.
>
> En mode cloud, le bouton de test utilise les identifiants **enregistrés**
> (pas ceux en cours de saisie) : **enregistrer d'abord**, puis tester.

Variables d'environnement équivalentes (optionnel) :

```env
ZEBRA_CONNECTION=cloud
ZEBRA_CLOUD_API_KEY=...           # clé API Zebra Data Services
ZEBRA_CLOUD_TENANT=...            # n° de tenant
ZEBRA_CLOUD_SERIAL=...            # n° de série de l'imprimante enrôlée
# Optionnel — override de l'endpoint (défaut ci-dessous) :
ZEBRA_CLOUD_ENDPOINT=https://api.zebra.com/v2/devices/printers/send
```

---

## 3. Détails techniques (référence)

### Contrat API SendFileToPrinter

```
POST https://api.zebra.com/v2/devices/printers/send
Headers : apikey: <clé>
          tenant: <n° de compte>
Body (multipart/form-data) :
  sn        = <n° de série imprimante>
  zpl_file  = <contenu ZPL>
```

Réponse 2xx = job accepté et relayé à l'imprimante via Weblink.

### Fichiers concernés (code)

| Fichier | Rôle |
|---|---|
| `app/services/zebra_cloud.py` | Transport cloud (SendFileToPrinter) |
| `app/services/zebra_printer.py` | Transport réseau local (ZPL TCP 9100) |
| `app/services/zebra_zpl.py` | Génération du ZPL d'une étiquette produit |
| `app/services/hardware_config.py` | Config persistée (`data/hardware.json`) |
| `app/api/labels/router.py` | Endpoints d'impression (dispatch network/cloud) |
| `app/api/hardware/router.py` | Endpoints config + test (`/settings → Matériel`) |

---

## 4. Dépannage

| Symptôme | Piste |
|---|---|
| **Réseau** : « Imprimante injoignable » | Mauvaise IP (vérifier l'étiquette FEED), imprimante éteinte / pas sur le réseau, IP non fixée (a changé au reboot). L'API doit être sur le même réseau. |
| **Cloud** : test renvoie une erreur 4xx | Clé API / tenant / n° de série incorrects, ou imprimante pas (ou plus) enrôlée Weblink. Vérifier qu'elle est « online » dans le portail Zebra. |
| **Cloud** : rien ne sort, pas d'erreur | L'imprimante a perdu sa connexion sortante (coupure réseau). Vérifier le réglage `weblink.ip.conn1.location` et la connectivité Internet de la box. |
| Étiquette blanche | Rouleau à l'envers (gratter le côté pour repérer le thermosensible) ou mauvais format. |
| Aperçu OK mais impression décalée | Calibrer le capteur d'écart (gap) via la procédure de calibration Zebra (appui FEED au démarrage). |

L'aperçu d'une étiquette (sans imprimer) reste disponible via Labelary :
`GET /api/labels/preview/{product_id}`.
