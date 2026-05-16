# Vintiz — matrice de parité web ↔ Android

Tableau de correspondance entre les pages `apps/web` et les écrans
Android `apps/android/feature/*`. Référencé dans
[`MIGRATION_ANDROID_NATIVE.md`](MIGRATION_ANDROID_NATIVE.md) §2.2 R2
comme document interne anti-divergence.

Légende :

- ✅ **Parité atteinte** — feature disponible identiquement sur les deux plateformes.
- 🟡 **Partiel** — feature présente mais avec quelques limitations ou simplifications.
- 🔵 **Android uniquement** — feature native qui n'existe pas (ou seulement en dégradé) côté web.
- 🟠 **Web uniquement** — feature qui restera web par décision produit (SEO, espace client public…).
- ⚪ **À venir** — pas encore livré sur la plateforme.

## 1. POS — caisse boutique

| Feature | Web (`apps/web/src/app/pos/`) | Android (`feature-pos`) |
|---|---|---|
| Recherche produit + auto-focus | ✅ | ✅ |
| Douchette Inateck USB HID | ✅ (focus input) | ✅ (`HidScanner` + `dispatchKeyEvent`) |
| Scan caméra ML Kit | 🟠 (non) | 🔵 `CameraBarcodeAnalyzer` toggle dans Settings |
| Numpad tactile | ✅ | 🟡 (à étoffer Compose) |
| Sélection cliente | ✅ | ✅ |
| Tap NFC carte fidélité | 🟠 (impossible web) | 🔵 `AndroidNfcService` foreground dispatch |
| Companion fidélité (gain / rachat / coupons / alertes RFM) | ✅ | ✅ `ClientCompanionPanel` + `PersonalShopperRepository.companion` |
| Remise par ligne | ✅ | ✅ `PosViewModel.applyDiscount` |
| Coupon code | ✅ | ✅ `CouponBar` + `LoyaltyRepository.validateCoupon` |
| Paiement espèces + rendu monnaie | ✅ | ✅ `PaymentSplit.computeChange` |
| Paiement CB SumUp REST polling | ✅ | ✅ `SumUpRestTerminal` |
| Paiement CB SumUp SDK BT direct | 🟠 (non) | ⚪ squelette `SumUpSdkTerminal`, activation côté Mac |
| Paiement chèque + avoir | ✅ | ⚪ chip présente, modal saisie à brancher |
| Ouverture / fermeture caisse + Z-Report | ✅ | ⚪ DTOs prêts, écran à brancher |
| Idempotence `client_uuid` | ✅ | ✅ Room queue + `DrainTransactionsWorker` |
| Mode offline complet | 🟡 IndexedDB | 🔵 Room + WorkManager robuste |
| Impression ticket MUNBYN | ✅ WebUSB | ✅ TCP + USB-OTG natif |
| Kick tiroir auto cash | ✅ | ✅ |

## 2. Stock / Inventaire

| Feature | Web | Android (`feature-inventory`) |
|---|---|---|
| Liste paginée 20/page | ✅ | 🟡 (search uniquement V1) |
| Filtres status / catégorie | ✅ | ⚪ |
| Détail produit avec photos | ✅ `PhotoGallery` | ⚪ |
| Historique prix / stock | ✅ | ⚪ |
| Nouveau produit + upload photo | ✅ | ⚪ |
| Scan barcode → ajout panier | ✅ | ✅ via POS (`InventoryRepository.byBarcode`) |
| Import CSV | ✅ | ⚪ |
| Impression étiquette unitaire | ✅ | ⚪ (Zebra ZPL prête côté hardware) |
| Impression étiquette batch | ✅ `LabelBatchBar` | ⚪ |

## 3. Clientes / CRM

| Feature | Web | Android (`feature-clients`) |
|---|---|---|
| Recherche email / V###### / téléphone | ✅ | ✅ |
| Fiche cliente 6 onglets | ✅ `/clients/[id]` | ⚪ (V2) |
| Solde fidélité + historique points | ✅ | ✅ via `Client.loyalty_points` |
| Wallet pass Apple + Google | ✅ payload prêt | ⚪ (V2) |
| Adhésion fidélité POS | ✅ | ✅ `feature-loyalty/LoyaltySubscribeScreen` |
| Magic-link OTP auto-login | 🟠 espace client public uniquement | 🟠 jamais exposé staff (cf. §5) |

## 4. Personal Shopper

| Feature | Web | Android (`feature-personal-shopper`) |
|---|---|---|
| Recos manager pour une cliente | ✅ `/clients/[id]` onglet PS | ✅ `PersonalShopperScreen` |
| PS v2 embeddings + Claude Haiku | ✅ | ✅ même endpoint |
| Log CTR clicks | ✅ | ✅ `trackClick` |
| Companion live au POS (cart-aware) | ✅ | ✅ `refreshCompanion` |
| Trend alerts opt-in | ✅ `/account/shopper` (espace client) | 🟠 côté espace client uniquement |

## 5. Espace client public

| Feature | Web (`apps/site`) | Android |
|---|---|---|
| Catalogue public + SEO | ✅ | 🟠 **jamais** (outil staff) |
| Magic-link OTP | ✅ | 🟠 jamais |
| Mes points fidélité | ✅ | 🟠 jamais |
| Mes achats | ✅ | 🟠 jamais |
| Personal Shopper gated | ✅ | 🟠 jamais |
| RGPD self-service (export, suppression, consentements) | ✅ | 🟠 jamais |

**Règle d'or** : l'app Android est un outil staff. Le client final n'utilise jamais l'app. Pour ses besoins libre-service, c'est `apps/site` qui répond.

## 6. Dashboard / Reporting

| Feature | Web (`/dashboard`) | Android (`feature-dashboard`) |
|---|---|---|
| KPI jour (CA, panier, tickets) | ✅ | ✅ |
| Météo Vernon | ✅ | ✅ |
| Top produits | ✅ | ✅ |
| Sparkline 7 j | ✅ | ⚪ (V2) |
| Briefing IA | ✅ `BriefingWidget` | ⚪ (V2) |
| Cahier du jour | ✅ `/dashboard/cahier-du-jour` | ✅ `feature-cahier` |
| Z-Reports historique | ✅ `/admin/z-reports` | ✅ via `feature-admin` onglet Z-Reports |
| Retail KPIs (sell-through, GMROI) | ✅ `/reports` | ⚪ (V2 — DTOs déjà en place) |
| Export fiscal NF525 | ✅ | ✅ `feature-fiscal` |
| Liaison Z-Reports → Export fiscal périodique | 🟠 (à faire web) | 🔵 bouton "Exporter période fiscale" |

## 7. Admin / Opérations

| Feature | Web | Android (`feature-admin`) |
|---|---|---|
| Liste transactions filtrable | ✅ `/admin/transactions` | ✅ |
| Refund modal | ✅ `RefundModal` 291 L | ✅ `RefundDialog` |
| Audit logs | ✅ | ✅ |
| Gestion utilisateurs (création, rôle) | ✅ `/admin/users` | ✅ (lecture, création V2) |
| Payment attempts SumUp | ✅ `/admin/payment-attempts` | ⚪ (V2) |
| Z-Reports détails | ✅ | ✅ |
| Sélection éditoriale | ✅ `/admin/selection` | ⚪ (V2) |

## 8. IA Booster

| Feature | Web (`/ia`) | Android (`feature-ia`) |
|---|---|---|
| CompanionHero priorités | ✅ 249 L | ⚪ (V2 — DTO `ChecklistItem` en place) |
| Checklist hebdo | ✅ | ✅ |
| Tendances sociales / retail | ✅ | ✅ |
| Vitrine — proposition + accept | ✅ `/ia` zone overlays | ✅ onglet Vitrine (`TrendsRepository.windowDisplay`) |
| Vitrine — réordonnancement produits avant accept | 🟠 (web ne le fait pas encore) | 🔵 boutons ▲▼ + `PATCH /window-display/{id}/reorder` |
| Règles markdown CRUD | ✅ `/settings > Scoring` | ⚪ (DTOs `TrendsApi` prêts) |
| Vision produit (analyse photo) | ✅ | ⚪ (V2) |
| Personas IA (marketing, juridique) | ✅ | ⚪ DTOs `IaApi.persona` câblés |

## 9. Zones / Plan boutique

| Feature | Web (`/zones`) | Android (`feature-zones`) |
|---|---|---|
| Vue 2D des zones | ✅ `IsoCanvas` SVG isométrique | ✅ Compose `Canvas` top-down |
| Tap zone → détail | ✅ | ✅ |
| Drag&drop édition zones | ✅ | ⚪ (V2) |
| Score moyen + bucket coloré | ✅ | ✅ |
| Saturation / sous-rempli alerte | ✅ | ✅ chips + bord Accent |
| Rendu isométrique 3D | ✅ | ⚪ V2 (`ZoneShape.Custom` + Path) |

## 10. Hardware / Settings

| Feature | Web (`/settings > Materiel`) | Android (`feature-settings` + `feature-onboarding`) |
|---|---|---|
| Config IPs imprimantes + tiroir | ✅ | ✅ `hardware_config` Room |
| Test ticket MUNBYN | ✅ | ✅ `OnboardingScreen` étape 4 |
| Test étiquette Zebra | ✅ | ⚪ (V2 — accessible via Settings) |
| Test kick tiroir | ✅ | ✅ inclus dans le test impression |
| Pairing USB MUNBYN (`requestUsbDevice`) | ✅ WebUSB | 🔵 `UsbEscPosPrinter` Android natif |
| Test ping TPE SumUp | ✅ | ✅ `OnboardingScreen` étape 5 |
| Toggle backend imprimante USB/réseau | 🟠 (driver Chrome) | 🔵 `AppPreferences.printerBackend` |
| Toggle TPE SDK BT / REST | 🟠 (impossible web) | 🔵 `AppPreferences.paymentBackend` |
| Toggle scanner caméra fallback | 🟠 (impossible web) | 🔵 `AppPreferences.cameraScannerEnabled` |

## 11. Newsletter

| Feature | Web (`/newsletter`) | Android (`feature-newsletter`) |
|---|---|---|
| Liste abonnés avec filtre | ✅ | ✅ |
| Export CSV | ✅ | ✅ FileProvider + Intent SEND |
| Suppression RGPD article 17 | ✅ | ✅ AlertDialog confirmation |
| Édition campagne email | ✅ | 🟠 (back-office web — pas d'API mobile prévue) |
| Subscribe public + double opt-in | 🟠 (site public uniquement) | — |

## 12. SEO / Marketing

| Feature | Web (`/seo`) | Android |
|---|---|---|
| Snapshots SEO + reviews Google | ✅ | 🟠 (back-office web — pas prioritaire mobile) |
| Social posts auto + accept | ✅ | 🟠 |
| Mentions Insta / TikTok | ✅ | 🟠 |

## 13. Notifications

| Feature | Web | Android |
|---|---|---|
| Push manager (FCM) | 🟠 (polling) | 🔵 `VintizFcmService` |
| In-App Update IMMEDIATE | 🟠 (rechargement page) | 🔵 `InAppUpdateManager` |
| Kiosque tablette caisse | 🟠 | 🔵 `KioskManager` Lock Task Mode |

## 14. Sécurité

| Feature | Web | Android |
|---|---|---|
| JWT stockage | localStorage (clair) | 🔵 EncryptedSharedPreferences + Keystore |
| Cert-pinning prod | 🟠 (HTTPS standard) | 🔵 `HttpClientFactory(pinning=...)` à brancher |
| Backup cloud désactivé fichiers sensibles | — | 🔵 `backup_rules.xml` + `data_extraction_rules.xml` |
| TTL cache PII RGPD | localStorage permanent | 🔵 `PurgePiiWorker` 30 j |
| Biométrie déverrouillage rapide | 🟠 | ⚪ V2 (`androidx.biometric` en deps) |

## 15. Synthèse

| Catégorie | État global |
|---|---|
| Cœur POS vente | ✅ Parité atteinte (avec gains natifs : NFC, USB-OTG, kick auto) |
| Inventaire / CRM | 🟡 Lecture OK, écriture détail V2 |
| Admin / Fiscal | ✅ Parité + nouveau bouton "Exporter période fiscale" depuis Z-Reports |
| IA Booster | 🟡 Checklist + tendances + vitrine OK ; règles markdown + personas DTOs prêts, écrans V2 |
| Hardware | 🔵 L'app Android dépasse le web sur les périphériques boutique |
| Espace client | 🟠 Reste 100 % web par décision (le staff utilise l'app, le client utilise le site) |
| Sécurité | 🔵 L'app Android dépasse le web (cert-pinning, Keystore, RGPD TTL, kiosque) |

## Règle anti-divergence

Toute nouvelle feature POS / admin doit être livrée sur Android **avant ou en même temps** que sur web. Le web reste secours (Chromebook prêté si tablette HS) et ne doit pas devenir terrain d'innovation produit. Voir `docs/MIGRATION_ANDROID_NATIVE.md` §5.3 règle d'or n°5.
