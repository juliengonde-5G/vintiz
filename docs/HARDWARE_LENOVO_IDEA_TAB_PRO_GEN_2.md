# Lenovo Idea Tab Pro Gen 2 — compatibilité Vintiz POS

Tablette caissier officielle Vintiz Vernon. Modèle : **TB39OFU**
(Lenovo / 2026).

## Spécifications matériel (Lenovo PSREF)

| Composant | Spec |
|---|---|
| Affichage | 13" IPS, 3540 × 2190, 144 Hz, ~334 PPI |
| SoC | Qualcomm Snapdragon 8s Gen 4 |
| RAM | 12 GB |
| Stockage | 256 / 512 GB |
| OS | Android 16 (Lenovo One UI) |
| USB-C | USB 3.2 Gen 1, supporte OTG host |
| Bluetooth | 6.0 |
| Wi-Fi | Wi-Fi 7 |
| Caméras | 13 MP arrière, 8 MP avant |
| Capteurs | Accéléromètre, gyroscope, lumière ambiante |

## Fonctionnalités Vintiz qui dépendent du matériel

### 1. Affichage haute densité
- 3540 × 2190 sur 13" = ~334 PPI
- Vintiz utilise Tailwind avec des classes `rem` + `px`; pas de calc
  vectoriel custom → le rendu reste net.
- Le mode plein écran Odoo 17 du POS exploite la largeur 3540 px pour
  une grille produits 4 colonnes (`2xl:grid-cols-4`).
- 144 Hz : non utilisé directement, mais profite aux animations
  Tailwind (hover, active-scale) qui restent fluides.

### 2. PWA install
- Manifest valide à `apps/web/public/manifest.json` (`display:
  standalone`, `scope: /`, icônes 192 et 512).
- Chrome Android propose automatiquement "Installer l'app" après ~30 s
  d'utilisation soutenue. Composant `PwaInstallBanner.tsx` proposé
  manuellement aussi.
- Une fois installé, l'app ouvre en fullscreen sans barre URL — pas
  de pollution de l'écran caisse.

### 3. Caméra (scan code-barres)
- `getUserMedia({ video: { facingMode: "environment" } })` cible la
  caméra arrière → utilisée par `/inventory/scan` pour scanner sans
  douchette.
- Permission accordée une fois, mémorisée par le navigateur (site
  HTTPS requis).

### 4. USB-OTG (imprimante ticket)
- USB 3.2 Type-C avec OTG host → la tablette peut alimenter et
  communiquer avec la MUNBYN 047P en USB.
- Driver côté Vintiz : `apps/web/src/lib/webusb-printer.ts` (WebUSB
  Chrome Android).
- Le câble OTG USB-A femelle / USB-C mâle est fourni avec la MUNBYN.

### 5. Bluetooth 6.0
- Non utilisé directement par Vintiz aujourd'hui.
- Potentiel futur (post-migration TWA Android natif) : pilotage
  direct du SumUp Solo en BLE via le SDK natif (cf.
  `docs/MIGRATION_ANDROID_NATIVE.md`).

### 6. Orientation
- Tablette en mode paysage permanent en boutique.
- `apps/web/src/lib/orientation.ts` appelle
  `screen.orientation.lock('landscape')` au mount du POS (nécessite
  HTTPS + fullscreen). Si lock refusé (PWA non installé), la UI
  reste utilisable en portrait grâce aux breakpoints Tailwind
  `md:`/`lg:`/`xl:`.

## Compatibilité APIs web

| API | Support Chrome Android 16 | Vintiz l'utilise pour |
|---|---|---|
| **WebUSB** | ✓ (Chrome 61+) | MUNBYN en USB-OTG |
| **Web Bluetooth** | ✓ | non encore utilisé |
| **getUserMedia (camera)** | ✓ | scan caméra inventaire |
| **Service Worker / PWA** | ✓ | install + offline fallback |
| **screen.orientation.lock** | ✓ | verrouillage paysage POS |
| **fetch / streams** | ✓ | toute la pile API |
| **localStorage / IndexedDB** | ✓ | JWT, prefs, cache POS offline |
| **WebRTC** | ✓ | non utilisé |
| **Wake Lock** | ✓ Chrome 84+ | non encore utilisé |
| **Web Share** | ✓ | non utilisé |

## Permissions Android à autoriser à la première installation

Le PWA Chrome demande les permissions au runtime (pas dans le
manifest) :

1. **Caméra** — pour `/inventory/scan` (scan code-barres)
2. **USB** — pour piloter la MUNBYN OTG (popup `navigator.usb.requestDevice`)
3. **Notifications** — non utilisé actuellement (peut être proposé
   plus tard pour les alertes manager)

## Réglages tablette recommandés

| Réglage Android | Valeur Vintiz |
|---|---|
| Auto-rotation | Désactivée (paysage forcé) |
| Veille écran | Jamais (boutique ouverte) — ou bouton "Wake Lock" si non disponible |
| Luminosité | Adaptative (capteur de lumière) |
| Mode "Ne pas déranger" | Activé pendant les heures d'ouverture |
| Lenovo One UI > Apps autorisées en arrière-plan | Chrome ON |
| Wi-Fi | Connecté au réseau boutique (séparé du Wi-Fi clients) |
| Localisation | Désactivée (pas requise par Vintiz) |
| Compte Google | Optionnel — utile pour les sauvegardes système, pas pour Vintiz |
| Lenovo Pen | Désactivé (la caisse marche au doigt) |

## Procédure de déploiement boutique

1. Déballer la tablette, charger 100 %
2. Premier boot Android — sauter Google account si pas désiré
3. Ouvrir Chrome → `https://app.vintiz.fr` → login
4. Accepter le prompt "Installer l'app Vintiz"
5. Ouvrir l'app installée (icône maison Android)
6. `/pos` → "Identifier caissier" (PIN 4 chiffres défini dans
   `/admin/users`)
7. Brancher la MUNBYN OTG → autoriser USB
8. `/settings > Matériel` → coupler le périphérique USB → "Imprimer
   ticket test" → vérifier
9. Brancher la douchette Inateck BCST-35 (USB-A → adaptateur USB-C)
   — fonctionne comme un clavier, aucune config nécessaire
10. Brancher le SumUp Solo au Wi-Fi boutique, configurer
    `SUMUP_READER_ID` dans `/settings > Paiement`

## Limites connues

- **Pas de NFC** sur le Tab Pro Gen 2 (vérifié 2026-05-14). Si la
  boutique veut accepter Apple Pay / Google Pay sans le TPE, il faut
  passer par le Solo (qui a un module NFC).
- **Pas de port jack 3.5 mm** — pas de scanner audio bluetooth si
  ça devait être un jour pertinent.
- **Haut-parleurs basiques** — `escpos_service.beep` (commande
  ``ESC B``) ferait beeper la MUNBYN, mais pas la tablette directement.

## Référence externe

- [Lenovo Idea Tab Pro Gen 2 PSREF](https://psref.lenovo.com/l/Product/Idea_Tab_Pro_Gen_2)
- [GSMArena specs](https://www.gsmarena.com/lenovo_idea_tab_pro_gen_2-14575.php)
- [Chrome Web Platform features sur Android](https://developer.chrome.com/docs/capabilities)
