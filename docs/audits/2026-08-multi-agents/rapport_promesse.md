# Audit « Promesse » — Vintiz (lecture seule)

Périmètre audité : `apps/api`, `apps/web`, `apps/site`, `docs/MANUEL_BOUTIQUE.md`,
`CLAUDE.md`, `docs/ZEBRA_INSTALLATION.md` (POS_TEST_BARCODES.md est référencé
mais **introuvable** dans le dépôt — voir Volet A). État du code au commit
`0a56ce2` (CHANGELOG à `1.1.2`, 2026-07-16) alors que `CLAUDE.md` s'auto-décrit
encore comme le socle verrouillé « v1.0.0 » du 03/06/2026 — premier signe que
la documentation n'a pas suivi le rythme du code.

## Synthèse

L'essentiel du cœur transactionnel (caisse, tiroir, ticket ESC/POS, clôture Z,
étiquettes Zebra, CB SumUp, bons cadeau, fidélité, RGPD, magic-link, alertes
tendance, wallet) est **réellement câblé de bout en bout** : les boutons du
front appellent de vrais endpoints qui font ce qu'ils annoncent, sans
simulation maquillée en succès — bonne nouvelle, le socle « métier » tient sa
promesse. Les écarts trouvés sont de deux natures bien distinctes. D'un côté,
une documentation en retard sur le code : le manuel boutique décrit encore une
imprimante d'étiquettes SATO et un mode « sandbox » SumUp tous deux retirés, et
la fonctionnalité « signatures manager/équipe » du Cahier du Jour a été
supprimée (« Lot 5 ») sans que `CLAUDE.md` ni le manuel ne soient corrigés — un
vendeur qui suit le manuel à la lettre cherchera des boutons qui n'existent
plus. De l'autre côté, deux écarts bien plus graves côté client final : le
formulaire newsletter affiché sur la page d'accueil du site public est un pur
mock front-end (aucun appel réseau) qui affiche un message de succès sans
jamais inscrire personne, alors qu'une route API dédiée et fonctionnelle existe
et n'est simplement pas appelée ; et plusieurs textes légaux/marketing du site
(CGV, FAQ fidélité, wallet, email de bienvenue) figent en dur « 100 points =
5 € » et « 24 mois » alors que ces valeurs sont un réglage admin modifiable à
tout moment sans que ces textes ne se mettent à jour.

## Volet A — Promesse aux équipes boutique (back-office + POS)

| Promesse (source) | État | Preuve front | Preuve back | Commentaire |
|---|---|---|---|---|
| Ticket ESC/POS « Imprimer (MUNBYN) » + ouverture tiroir | **TENUE** | `apps/web/src/components/pos/ReceiptPreviewCard.tsx:151` | `apps/api/app/services/escpos_service.py:659` (`kick_drawer`, socket TCP réel, `ESC p m`) | Vrai flux réseau port 9100, pas de simulation. |
| Bouton « Imprimer (AirPrint) » (MANUEL_BOUTIQUE.md:107) | **ROMPUE** | `ReceiptPreviewCard.tsx:19-23` : prop `onPrintAirprint` conservée dans la signature mais **jamais rendue** (commentaire : « cette prop n'est plus rendue ») | — | Le manuel boutique documente encore un 3ᵉ bouton qui n'existe plus dans l'UI (retrait confirmé par `CLAUDE.md`). |
| Impression étiquette produit (« Imprimer SATO », MANUEL_BOUTIQUE.md:147-148, Settings §9) | **PARTIELLE** | `apps/web/src/app/inventory/[id]/page.tsx:685` → « Imprimer sur Zebra » | `apps/api/app/api/labels/router.py:1-9` (« Replaces the previous SATO/SBPL stack ») ; `zebra_printer.py`/`zebra_cloud.py` : vrais sockets/HTTPX | La fonctionnalité marche (Zebra ZD421d, réseau/cloud/BLE tous réels), mais le manuel boutique (§5, §9) et `apps/web/src/app/dashboard/workflows/workflows.json` décrivent encore une imprimante SATO CT4-LX et un bouton « Imprimer SATO » qui n'existent plus — confusion garantie en formation. |
| Réglage SumUp « env / sandbox / simulation » (MANUEL_BOUTIQUE.md §9) | **ROMPUE (doc)** | `apps/web/src/app/settings/page.tsx:2123` — carte « Terminal de paiement — SumUp » : aucun sélecteur d'environnement/sandbox | `apps/api/app/services/sumup_service.py:7-9` : « Le mode sandbox/simulation a été retiré » ; sans clé → `status: FAILED` explicite | Cohérent avec `CLAUDE.md`, mais le manuel boutique n'a pas été mis à jour et documente un onglet qui n'existe plus. |
| Remises panier 0/5/10/15/20/30 % | **TENUE** | `apps/web/src/app/pos/page.tsx:2095` | `apps/api/app/api/pos/router.py` (discount_percent appliqué serveur) | Conforme au manuel. |
| Fidélité : 1 €=1 pt, 100 pts → chèque 5 €, hors promo/solde/remise | **TENUE (mécanique)** | `apps/web/src/components/pos/LoyaltyCustomerCard.tsx` | `apps/api/app/services/pos.py:809-950` (`_credit_loyalty_and_emit_milestones`, `milestones_crossed`) | Le calcul est correct et exclut bien les lignes `promotional`. Voir Volet B pour la fragilité des valeurs affichées côté client. |
| Bons cadeau événementiel (émission + débit en caisse) | **TENUE** | `apps/web/src/app/pos/page.tsx:76` (bon affecté comme règlement) | `apps/api/app/api/pos/router.py:547-727`, `services/event_vouchers.py` | Catalogue, émission sur fiche client, débit en caisse et affichage à l'identification tous réels. |
| Ouverture/fermeture caisse + rapport Z numéroté | **TENUE** | `apps/web/src/app/pos/page.tsx:528-574`, `CashDrawerCloseModal.tsx` | `apps/api/app/api/pos/router.py:993-1167` (`z_report_number`, `report_number`) | Écart attendu/compté calculé serveur, PDF Z téléchargeable (`:3528`). |
| Cahier du Jour : objectif CA, poids historiques, comparatif N-1, messages libres | **TENUE** | `apps/web/src/app/dashboard/cahier-du-jour/page.tsx:119-171` | `apps/api/app/api/cahier/router.py:50-231`, `services/cahier_service.py` | KPI et répartition par poids de jour réels. |
| Cahier du Jour : « Signatures manager + équipe » (MANUEL_BOUTIQUE.md:58 ; `CLAUDE.md` liste `PUT /api/cahier/signature`) | **ROMPUE** | Aucune UI de signature dans `apps/web/src/app/dashboard/cahier-du-jour/page.tsx` | `apps/api/app/api/cahier/router.py:87` : commentaire « signatures supprimées Lot 5 » — endpoint `/signature` absent du routeur | Fonctionnalité supprimée du produit, mais toujours documentée comme active dans le manuel **et** dans `CLAUDE.md` (doc technique de référence). |
| Score produit recalculé « le 1er mercredi de chaque mois » (MANUEL_BOUTIQUE.md:161, `CLAUDE.md`) | **PARTIELLE** | — | `apps/api/app/jobs.py:672` : `run_weekly_scoring` sur `CronTrigger(day_of_week="mon", hour=4)` | La cadence réelle est **hebdomadaire (lundi)**, pas mensuelle (1er mercredi). Le score est recalculé plus souvent que promis — inoffensif pour l'équipe mais la doc reste factuellement fausse. |
| Boutons de test matériel (ticket / tiroir / étiquette) dans `/settings > Materiel` | **TENUE** | `apps/web/src/app/settings/page.tsx:387-679` | `apps/api/app/api/hardware/router.py:132,171,231` | Tests live réels (pas de placebo). |
| `docs/POS_TEST_BARCODES.md` (référencé par `CLAUDE.md` et le manuel) | **ROMPUE** | — | — | Fichier **absent du dépôt** (`git ls` / `Glob` négatifs) : lien mort dans deux documents de référence. |
| Checklist IA hebdo « tous les lundis » | **TENUE** | `apps/web/src/app/ia/*` | `apps/api/app/jobs.py:469-486,816-818` (cron lundi 09:00) | Conforme. |

## Volet B — Promesse aux utilisateurs du site / espace client

| Promesse (source) | État | Preuve front | Preuve back | Commentaire |
|---|---|---|---|---|
| Formulaire newsletter page d'accueil (double consentement implicite, RGPD) | **ROMPUE** | `apps/site/src/components/home/NewsletterCard.tsx:9-12` : `onSubmit` fait uniquement `e.preventDefault(); setDone(true);` — **aucun `fetch`**, aucune case à cocher de consentement, affiche « Merci ! Nous vous recontactons très vite. » | `apps/api/app/api/newsletter/router.py:117-135` (endpoint réel, exige `consent=true`) ; `apps/site/src/app/api/subscribe/route.ts` (proxy Next.js fonctionnel vers le back) **jamais appelé** par `NewsletterCard` | Le formulaire visible sur `vintiz.fr` (rendu dans `apps/site/src/app/page.tsx:357`) ne fait strictement rien : aucune adresse n'est enregistrée, aucun consentement n'est tracé, alors qu'un back-end et une route proxy conformes existent déjà et sont utilisés nulle part. Toast de succès mensonger. |
| « 100 pts = chèque cadeau de 5 € », « validité 24 mois » (CGV, FAQ fidélité, login, wallet, email de bienvenue) | **PARTIELLE (promesse fragile)** | 6 occurrences en dur : `apps/site/src/app/cgv/page.tsx:135`, `account/fidelite/page.tsx:22,103-107`, `account/page.tsx:253-254`, `account/login/page.tsx:344`, `components/account/LoyaltyHeroCard.tsx:23` (valeur par défaut jamais surchargée par `account/page.tsx:203`) | `apps/api/app/services/loyalty_config.py:115-186` (`LoyaltyEarningConfig`, `set_earning_config`) éditable via `PUT /api/admin/loyalty/earning-config` ; `apps/api/app/services/wallet.py:43` (`BENEFIT_TEXT` constante en dur, jamais lue depuis la config) | Si un manager modifie le seuil, le montant du chèque ou la durée de validité depuis `/admin/operations`, **aucun** de ces textes clients (CGV, FAQ, wallet pass, email de bienvenue, page compte) ne change : ils continueront d'afficher « 100 pts / 5 € / 24 mois » même si la règle réelle est différente. Mensonge différé, pas immédiat. |
| « Coupons... s'appliquent automatiquement au prochain passage en caisse » (`account/offres/page.tsx:88`) | **PARTIELLE** | `apps/site/src/app/account/offres/page.tsx:88` | `apps/web/src/components/pos/ClientCompanion.tsx:242-245` : bouton **« Appliquer »** — le coupon n'est ajouté au panier que si le vendeur clique dessus ; `apps/web/src/app/pos/page.tsx:1341,1429` (`couponApplied` alimenté uniquement par ce clic) | Le mot « automatiquement » est trompeur : la remise dépend d'une action manuelle du vendeur dans le panneau companion. Si le vendeur ne clique pas, le client ne reçoit pas la réduction promise. |
| Wallet Apple/Google (carte fidélité dématérialisée) | **TENUE** | `apps/site/src/components/WalletCard.tsx:180-221` — boutons masqués tant que `apple_signed_available`/`google_save_available` sont faux | `apps/api/app/api/crm/router.py:1688-1689` → `apple_wallet_available()`/`google_wallet_available()` (vérifient la présence réelle des secrets de signature) | Bon exemple de promesse honnête : pas de bouton « Ajouter au Wallet » tant que la signature n'est pas réellement configurée (cohérent avec le manuel : « en attente d'activation côté ops »). |
| Magic-link email + SMS (OTP 6 chiffres) | **TENUE (email)** / **À surveiller (SMS)** | `apps/site/src/app/account/login/page.tsx:97-116` | `apps/api/app/services/magic_link.py:141-249` | Le canal SMS retombe en simulation silencieuse si Twilio/Brevo SMS n'est pas configuré (log serveur uniquement, warning « PRODUCTION using SMS simulation ») — le client voit « code envoyé par SMS » sans qu'il parte réellement si l'ops n'a pas configuré la clé. |
| Personal Shopper réservé aux membres + consentement profilage | **TENUE** | `apps/web/src/app/clients/[id]/page.tsx:299` (message de gating identique) | `apps/api/app/services/personal_shopper.py:499-527` (`PersonalShopperGatedError` — contrôle serveur, pas seulement UI) | Gating appliqué côté serveur, impossible à contourner en tapant l'URL. |
| Alertes tendance : email dès que `trend_score>70` + cap 1 email/7 jours | **TENUE** | `apps/site/src/app/confidentialite/page.tsx:94-98` | `apps/api/app/services/trend_alerts.py` (cap réel via `last_trend_alert_at`), cron `apps/api/app/jobs.py:517-525,791-793` (11:00 Paris) | Conforme au texte affiché. |
| Export RGPD Article 20 + suppression sous 30 jours (annulable) | **TENUE** | `apps/site/src/app/account/rgpd/page.tsx:98,126,149` | `apps/api/app/services/rgpd.py:44` (`DELETION_WINDOW = timedelta(days=30)`), cron `run_daily_rgpd_purge` (`apps/api/app/jobs.py:160-169,677-680`) | Fenêtre de 30 jours réellement respectée par le cron quotidien, annulation fonctionnelle. |
| Anniversaire : coupon `ANNIV-XXXXXX` -10 %, 7 jours, idempotent | **TENUE** | — (email uniquement) | `apps/api/app/services/anniversary.py:80-167`, `coupon.py:72-108` (dédoublonnage par jour calendaire) | Conforme au manuel. |
| Politique de confidentialité : pas de double opt-in newsletter promis | **Cohérent** | `apps/site/src/app/confidentialite/page.tsx:73-76` : ne mentionne qu'un lien de désinscription, pas de confirmation email | `apps/api/app/api/newsletter/router.py` : simple opt-in, pas de token de confirmation | Contrairement au manuel boutique (§8 : « lien email de confirmation prévu en S2 »), la page RGPD publique n'affirme jamais ce double opt-in — donc pas de mensonge *client*, seulement une incohérence interne CLAUDE.md/manuel vs réalité (déjà notée en volet A). |

## Top 5 des écarts les plus graves

1. **Formulaire newsletter du site public entièrement factice.**
   `apps/site/src/components/home/NewsletterCard.tsx` ne fait aucun appel
   réseau et affiche un faux message de succès, alors qu'un back-end RGPD
   complet (`/api/newsletter/subscribe`) et une route proxy Next.js
   (`apps/site/src/app/api/subscribe/route.ts`) existent et fonctionnent.
   **Recommandation** : brancher `NewsletterCard` sur `POST /api/subscribe`
   (ajouter la case de consentement obligatoire) en 30 minutes de dev ; c'est
   le point le plus visible et le plus trompeur de tout l'audit — zéro
   inscription n'a probablement jamais été captée depuis la landing.

2. **Chiffres de fidélité (« 100 pts = 5 € », « 24 mois ») figés en dur alors que la config admin les rend modifiables.**
   6+ pages/textes clients (CGV, FAQ, wallet, emails, login) hardcodent ces
   valeurs pendant que `PUT /api/admin/loyalty/earning-config` permet de les
   changer sans redéploiement. **Recommandation** : exposer un endpoint
   public `GET /api/crm/account/loyalty/rules` et faire consommer ce texte
   dynamiquement par le site/wallet/emails plutôt que des chaînes en dur ;
   à défaut, verrouiller la config admin en lecture seule tant que les
   textes ne sont pas dynamiques.

3. **« Signatures manager/équipe » du Cahier du Jour documentée comme active dans `CLAUDE.md` et le manuel, alors que la fonctionnalité a été supprimée (« Lot 5 »).**
   Aucun endpoint `/api/cahier/signature`, aucune UI. **Recommandation** :
   retirer la mention des deux documents de référence (`CLAUDE.md` §API et
   `MANUEL_BOUTIQUE.md` §2.D) pour éviter qu'un nouveau vendeur/dev cherche un
   bouton fantôme.

4. **« Coupons appliqués automatiquement en caisse » — en réalité geste manuel du vendeur.**
   Le texte de `/account/offres` laisse croire à une application sans
   intervention humaine, alors que le vendeur doit cliquer « Appliquer » dans
   le panneau companion (`ClientCompanion.tsx`). **Recommandation** :
   reformuler en « proposés automatiquement au vendeur, à valider en
   caisse » — ou, mieux, auto-appliquer réellement le coupon le plus
   avantageux à l'identification du client pour tenir la promesse actuelle.

5. **Documentation matériel périmée (SATO → Zebra, SumUp sandbox retiré, POS_TEST_BARCODES.md manquant).**
   `MANUEL_BOUTIQUE.md` et `apps/web/.../workflows.json` décrivent encore une
   imprimante d'étiquettes SATO CT4-LX et un mode sandbox SumUp tous deux
   remplacés/retirés ; `docs/POS_TEST_BARCODES.md` référencé par deux
   documents n'existe plus dans le dépôt. **Recommandation** : passe de mise
   à jour documentaire ciblée (manuel §5/§9, workflows.json, régénérer ou
   retirer la référence à POS_TEST_BARCODES.md) avant la prochaine formation
   d'équipe.
