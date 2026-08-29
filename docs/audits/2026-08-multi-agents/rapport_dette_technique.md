# Audit de dette technique — Vintiz (monorepo)

Date de l'audit : 2026-08-29. Périmètre : `apps/api`, `apps/web`, `apps/site`,
`scripts/`, `docs/` + fichiers racine (`CLAUDE.md`, `README.md`, `AGENTS.md`).
Méthode : lecture statique, `grep`/`ast` sur l'arborescence, lecture des
migrations Alembic, pas d'exécution de tests (environnement sans les
dépendances Python installées et hors périmètre "lecture seule").

> **Note de contexte** : au moment de cet audit, l'arbre de travail contenait
> des modifications non commitées (probablement une session parallèle) qui
> corrigent un bug de fidélité distinct (double-comptage des chèques cadeau
> au retour, `apps/api/app/services/refund.py`, migration
> `0076_loyalty_debit_at_issuance.py`) et bump `APP_VERSION` à `1.1.5`
> (`apps/api/app/version.py`) sans répercuter ce numéro dans
> `apps/api/pyproject.toml` ni `apps/web|site/package.json` (restés à
> `1.1.2`). Ce correctif en cours n'est pas repris dans les constats
> ci-dessous ; l'état analysé est celui du working tree tel que lu.

## Synthèse

Le backend est propre sur les fondamentaux (pas de dépendance Python inutile,
0 fichier composant/hook front mort, chaîne de migrations 0001→0075
strictement linéaire et idempotente sur le contrat bootstrap+upgrade,
quasiment aucun vrai TODO/FIXME dans le code). La dette réelle est ailleurs :
**la documentation (CLAUDE.md compris) décrit une boutique qui n'existe plus**
(iPad/AirPrint/SATO CT4-LX/scripts renommés) alors que le code a basculé sur
tablette Android + MUNBYN + Zebra depuis plusieurs versions, et **deux bugs
concrets non couverts par les tests** menacent respectivement la conformité
fiscale TVA et l'intégrité de l'historique d'audit produit lors d'un futur
reset boutique. Le reste est de la duplication mineure d'affichage de prix et
quelques fichiers/dépendances orphelins, sans risque fonctionnel à les
retirer.

## Constats P1 — risque prod, à corriger vite

### P1-1 — TVA figée à 20 % dans le calcul de vente, incohérente avec 3 sources de configuration
- **Fichiers** : `apps/api/app/services/pos.py:391-393` (calcul réel à la
  vente) ; `apps/api/app/services/pos.py:483-493` (création de
  `TransactionItem` sans `tva_rate=`) ; `apps/api/app/models/product.py:111-118`
  et `apps/api/app/models/pos.py:176-182` (docstrings décrivant le champ comme
  "copié sur la ligne de transaction au moment de la vente") ;
  `apps/api/app/services/accounting_service.py:552-558` (seul endroit qui lit
  réellement `AccountingConfig.tva_rate`) ; `apps/api/app/services/tva_service.py`
  (module dédié, testé, jamais appelé en dehors de son test).
- **Constat** : `POSService.create_transaction` calcule `total_ht`/`total_tva`
  avec un diviseur codé en dur `Decimal("1.20")` (commentaire "TVA 20 %"), et
  ne renseigne jamais `tva_rate=` sur les lignes créées — la colonne retombe
  systématiquement sur son défaut `20.00`. `Product.tva_rate` (champ éditable
  en base, pensé pour les taux réduits — 5,5 % chaussures enfant, etc., selon
  son propre commentaire) n'est lu nulle part au moment de l'encaissement, et
  n'est exposé dans aucune page d'édition produit de `apps/web` (vérifié :
  aucune occurrence de `tva_rate` dans `apps/web/src/app/inventory/**`). Le
  taux configurable dans `/settings/comptabilite` (`AccountingConfig.tva_rate`,
  `apps/web/src/app/settings/comptabilite/page.tsx:159-160`) n'est lu QUE par
  `accounting_service.py` pour ventiler HT/TVA des bons cadeaux (ligne 555) —
  donc si un jour ce taux est changé, les bons cadeaux et les ventes réelles
  seront ventilés à deux taux différents dans le même export comptable/FEC.
  Le module `tva_service.py` (168 lignes, testé par `tests/test_tva_service.py`,
  261 lignes), qui gère correctement l'arrondi multi-taux et documente
  lui-même qu'il doit être "branché dans le générateur de ticket", n'est
  appelé par aucun code de production.
- **Impact** : si un article à taux réduit est un jour vendu (le modèle le
  permet explicitement), le ticket, la ligne NF525 et l'export FEC afficheront
  20 % au lieu du taux réel — risque de conformité DGFiP sur un projet qui
  documente abondamment sa conformité NF525 (`docs/COMPLIANCE_NF525.md`).
- **Preuve d'absence de couverture** : `grep -rl tva_rate apps/api/tests` ne
  remonte que `test_fiscal_v2.py` (taux fixé à 20 dans la fixture) et
  `test_tva_service.py` (teste le module orphelin) — aucun test ne fait
  passer un produit à taux non-standard dans `POSService.create_transaction`
  et n'assert le résultat.

### P1-2 — `go_live_reset.py` : le TRUNCATE…CASCADE PostgreSQL efface l'audit `product.created` qu'il est censé préserver
- **Fichiers** : `scripts/go_live_reset.py:86-117` (`TABLES_TO_WIPE`, contient
  `clients` et `transactions`) ; ligne 260 (`TRUNCATE TABLE {quoted} RESTART
  IDENTITY CASCADE`) ; lignes 267-270 (commentaire justifiant que le DELETE
  filtré sur `events_log` peut être fait *après* le TRUNCATE "car aucune table
  ne référence events_log") ; `apps/api/app/models/events.py:90` et `:96`
  (`EventLog.customer_id → clients.id`, `EventLog.transaction_id →
  transactions.id`).
- **Constat** : le commentaire raisonne dans le mauvais sens. La question
  n'est pas "est-ce que `events_log` est référencée" mais "est-ce que
  `events_log` référence une table truncatée" — c'est le cas deux fois
  (`customer_id`, `transaction_id`). En PostgreSQL, `TRUNCATE ... CASCADE`
  truncate **automatiquement toute table qui a une FK vivante vers les
  tables nommées**, indépendamment de l'action `ON DELETE` déclarée et
  indépendamment du fait que la table cible figure ou non dans la liste
  explicite. Donc l'étape 3 (`TRUNCATE clients, transactions, ...  CASCADE`)
  vide entièrement `events_log` — carve-out `product.created` compris — AVANT
  que l'étape "3 bis" (`_wipe_events_log_partial`, ligne 181-186) ne s'exécute
  sur une table déjà vide. Le script ne fait ensuite aucune assertion entre
  `events_remaining` et `events_to_keep` (lignes 292-310) : il imprime le
  compte final tel quel et annonce "Reset terminé... Inventaire intact ✓" même
  si 0 ligne `product.created` a survécu — sans lever d'erreur ni avertir
  l'opérateur que la garantie documentée (lignes 9-34 du même fichier) n'a
  pas été tenue.
- **Pourquoi ce n'est pas détecté par les tests** : `apps/api/tests/
  test_go_live_reset.py:5` dit explicitement "Tourne sur SQLite (chemin
  DELETE)". Le script bifurque sur `engine.dialect.name` (ligne 256-264) :
  SQLite prend la branche `DELETE FROM {table}` table par table, qui ne
  déclenche aucune cascade implicite — c'est exactement le chemin QUI NE PEUT
  PAS reproduire le bug. Le test `test_live_wipes_operational_keeps_inventory`
  passe donc au vert alors que le comportement réel en production (Postgres)
  est différent et cassé.
- **Impact** : ce script est documenté dans `CLAUDE.md` comme outil
  disponible ("Reset one-shot pré-ouverture") et le monorepo montre des
  signes d'expansion (`docs/MULTI_STORE.md`) qui pourraient amener à le
  rejouer pour une seconde boutique — toute ré-exécution effacerait
  silencieusement la traçabilité "qui a saisi quel produit" que le script
  affiche pourtant comme préservée.

## Constats P2 — dette réelle, planifiable

### P2-1 — `scripts/diag.sh` ne surveille pas la moitié de la stack Docker de prod
- **Fichiers** : `scripts/diag.sh:32` (`SERVICES=(vintiz-api vintiz-db
  vintiz-web vintiz-caddy)`) vs `docker/docker-compose.prod.yml` (8
  `container_name` déclarés : `vintiz-caddy`, `vintiz-db`, `vintiz-redis`,
  `vintiz-api`, `vintiz-web`, `vintiz-site`, `vintiz-matomo-db`,
  `vintiz-matomo`).
- **Constat** : `diag.sh` ne vérifie ni `vintiz-site` (le site public), ni
  `vintiz-redis` (cache/rate-limit), ni la stack Matomo ajoutée récemment. Un
  `diag.sh` qui affiche "tout est OK" alors que le site public ou Redis est en
  panne est un faux négatif dangereux pour un script utilisé en pré-ouverture.

### P2-2 — Documentation matériel massivement désynchronisée du code (iPad/AirPrint/SATO)
- **Fichiers concernés** :
  - `docs/DEPLOIEMENT.md:202` (« Imprimante 80 mm | AirPrint (Wi-Fi) »),
    `docs/DEPLOIEMENT.md:203` (« TPE SumUp Solo | sandbox ou production »).
  - `docs/MANUEL_BOUTIQUE.md:107` (« Imprimer (AirPrint) — fallback via la
    dialogue d'impression iPad »), `:31`, `:147-148`, `:251-252` (SATO CT4-LX).
  - `docs/ARCHITECTURE.md:94`, `:112`, `:150-151` (schéma "iPad Safari",
    "Imprimante 80mm : AirPrint Wi-Fi", "SumUp sandbox").
  - `docs/UX_DESIGN.md:268` (« Fermer sans ticket → MUNBYN → AirPrint »).
  - `docs/DEPLOIEMENT_FIDELITE.md:68` (« Imprimante SATO étiquettes »).
  - `docs/AUDIT_2026_05_BOUTIQUE.md:79,137-142,594,605` (`sato_service.py`
    cité comme "prêt").
  - `README.md:5-6` (« caisse iPad… ESC/POS / SATO / SumUp »), `:118`, `:137`.
- **Preuve que c'est faux aujourd'hui** :
  `apps/api/app/api/labels/router.py:1-3` — "Label printing endpoints — Zebra
  ZD421d over ZPL. Replaces the previous SATO/SBPL stack." ; `find . -iname
  "*sato*"` sur tout le repo ne retourne **aucun fichier** (`sato_service.py`
  n'existe plus) ; `apps/web/src/lib/platform.ts:1-8` — "Vintiz tourne
  désormais 100% sur Android... Les helpers iOS/Safari/AirPrint/Apple Wallet
  ont été retirés — la base de code est sans branche iOS." ; le hardware
  officiel est décrit dans `docs/HARDWARE_LENOVO_IDEA_TAB_PRO_GEN_2.md` (tablette
  Lenovo Idea Tab Pro Gen 2, Android 16). `CLAUDE.md:794` liste pourtant
  encore « Tablette caisse | iPad (Safari) ».
- **Impact** : quiconque (humain ou agent) suit ces docs pour mettre en
  service une boutique ou dépanner le matériel configurera le mauvais
  device/imprimante.

### P2-3 — `CLAUDE.md` et `README.md` référencent des scripts qui n'existent plus
- **Fichiers** : `CLAUDE.md` (section "Architecture", scripts listés :
  `seed_data.py`, `seed_test_products.py`) ; `README.md:34` (« scripts/
  seed_data.py, seed_test_products.py, deploy.sh, diag.sh, go_live_reset.py,
  smoke_prod.sh »).
- **Preuve** : `find . -iname "seed_data.py" -o -iname
  "seed_test_products.py"` ne retourne rien dans le repo. Les scripts
  actuellement présents pour cet usage sont `scripts/seed_demo_products.py`
  (50 produits via `/from-photo`) et `scripts/seed_witness_clients.py` (20
  clientes témoins) — remplacement fonctionnel mais jamais répercuté dans la
  doc. Corollaire : `docs/POS_TEST_BARCODES.md` et `docs/test_barcodes/*.png`
  (cités dans l'arborescence de `CLAUDE.md`) n'existent pas non plus.

### P2-4 — Code mort : `app/services/cash_drawer.py` (`CashDrawerService`), et il est en plus moins correct que le calcul réel
- **Fichiers** : `apps/api/app/services/cash_drawer.py` (48 lignes, classe
  `CashDrawerService`) vs `apps/api/app/api/pos/router.py:1186-1259`
  (endpoint `GET /drawer/current`, calcul `expected_cash` réellement utilisé).
- **Preuve d'absence de référence** : `grep -rn "CashDrawerService"
  apps/api apps/api/tests` ne retourne que la définition elle-même — 0 appelant,
  0 test.
- **Constat aggravant** : si ce service était un jour réutilisé en pensant
  qu'il est la source de vérité, il donnerait un résultat **faux** : sa
  méthode `calculate_expected` (lignes 15-29) fait `opening_amount + somme de
  TOUS les paiements cash` sans exclure les remboursements ni prendre en
  compte les mouvements de tiroir (`CashMovement` apports/prélèvements),
  contrairement au calcul réellement branché dans le routeur qui, lui,
  soustrait les remboursements espèces et ajoute/retranche les mouvements
  (lignes 1213-1253).

### P2-5 — Code + dépendance morts : `app/services/barcode.py` et `python-barcode`
- **Fichiers** : `apps/api/app/services/barcode.py` (génère un Code128 PNG via
  `python-barcode`/`ImageWriter`) ; `apps/api/pyproject.toml` (dépendance
  `python-barcode>=0.15.1`).
- **Preuve** : `grep -rn "generate_barcode\b" apps/api scripts` ne retourne
  que la définition ; `grep -rn "^import barcode$\|^from barcode"
  apps/api/app` ne retourne que ce même fichier — `python-barcode` n'est
  utilisé nulle part ailleurs dans le code. La génération de code-barres
  réellement utilisée aujourd'hui est une simple chaîne `"VTZ" +
  random.randint(...)` (`apps/api/app/services/product_intake.py:77-79`) ou
  `"VTZP-{year}-{...}"` (`apps/api/app/api/inventory/permanent.py:96-103`),
  sans rendu PNG via cette librairie. C'est le même reliquat que P2-3 (l'usage
  PNG de `python-barcode` servait probablement à générer
  `docs/test_barcodes/*.png`, disparus).

### P2-6 — Formatage de prix dupliqué et incohérent (virgule FR vs point)
- **Fichiers `apps/site`** : `apps/site/src/app/account/historique/page.tsx:102,112`
  et `apps/site/src/app/account/page.tsx:246,297` — `{'{'}montant.toFixed(2){'}'}
  €` brut au lieu de `formatPriceEuros`/`formatPriceCents`
  (`apps/site/src/lib/format.ts`).
- **Fichiers `apps/web`** : `apps/web/src/app/pos/page.tsx:1702,2737,2740` et
  `apps/web/src/components/pos/LoyaltyCustomerCard.tsx:76` — même pattern, au
  lieu de `formatCurrency` (`apps/web/src/lib/format.ts`, qui gère
  explicitement la virgule + espace insécable pour la convention française).
- **Constat** : `apps/web/src/lib/format.ts:4-7` dit avoir « remplacé 13
  définitions ad-hoc de `formatCurrency` qui avaient dérivé » — la dérive
  n'est pas éteinte : `grep -c "toFixed(2)" apps/web/src --include=*.tsx`
  hors `lib/format.ts` remonte encore 48 occurrences (la plupart légitimes,
  utilisées pour arrondir une valeur avant calcul, mais celles listées
  ci-dessus sont bien de l'**affichage** direct). Résultat visible : ces
  montants s'affichent avec un point décimal anglais (`45.00 €`) au lieu de
  la virgule utilisée partout ailleurs dans la même page (`45,00 €`).
  (`apps/site/src/app/produits/[slug]/page.tsx:101` utilise aussi
  `toFixed(2)` mais c'est légitime : c'est un champ JSON-LD schema.org qui
  attend un point, pas un texte affiché.)

### P2-7 — `apps/web/src/app/pos/page.tsx` (3675 lignes) fait cohabiter deux parcours de paiement complets
- **Fichiers** : `apps/web/src/app/pos/page.tsx:340` (flag `wizardEnabled`),
  blocs gated `wizardEnabled`/`!wizardEnabled` répartis sur tout le fichier
  (ex. lignes 1720, 2317, 2628-2632, 3055, 3147, 3238, 3308, 3395).
- **Constat** : c'est un rollout de feature-flag légitime et fonctionnel (pas
  un bug — cf. section "à ne pas toucher"), mais tant que l'ancien parcours
  "legacy fullscreen" n'est pas retiré, le fichier porte le double de la
  logique de paiement à maintenir. À planifier : retirer le chemin legacy une
  fois le wizard généralisé sur tous les appareils.

### P2-8 — `AGENTS.md` duplique `CLAUDE.md` avec un risque de dérive déjà amorcé
- **Fichiers** : `/home/user/vintiz/AGENTS.md` vs `/home/user/vintiz/CLAUDE.md`.
- **Constat** : `AGENTS.md` reprend quasiment mot pour mot l'en-tête
  "Version 1.0.0 — mise en production officielle 03/06/2026" et la liste de
  scripts de `CLAUDE.md`, mais avec un contenu déjà légèrement différent
  (ex. `AGENTS.md` cite `bootstrap_database.py` dans sa liste de scripts,
  que la section correspondante de `CLAUDE.md` omet). Maintenir deux guides
  qui se recopient invite mécaniquement à ce genre de divergence silencieuse.

### P2-9 — `docs/CHANGELOG.md` n'a pas suivi les 36 commits les plus récents
- **Fichiers** : `docs/CHANGELOG.md` (dernière entrée : `[1.1.2] - 2026-07-16`)
  vs `git log --oneline --since=2026-07-16` (36 commits, dont la stack Matomo
  self-hosted, la conformité pixels CNIL/consentement d'ouverture d'e-mail,
  les correctifs SEO/GSC canoniques+hreflang, et les correctifs CI/migrations
  0072-0075 mentionnés en tête de ce document).
- **Constat** : aucune de ces fonctionnalités (dont une nouvelle table —
  `email_open_tracking_consent`, migration 0075 — et un service applicatif
  entier, Matomo) n'a de ligne de changelog ni de bump de version associé.

## Constats P3 — cosmétique

### P3-1 — `CLAUDE.md:56` documente "python-jose" alors que le code utilise PyJWT
- **Preuve** : `apps/api/app/core/security.py:6` fait `import jwt` (PyJWT,
  déclaré dans `apps/api/pyproject.toml` sous `PyJWT>=2.8.0`) ;
  `grep -rn "jose" apps/api/app` ne retourne aucun résultat.

### P3-2 — `CLAUDE.md` sous-estime très largement la taille de la suite de tests
- **Preuve** : `CLAUDE.md` (section Tests) annonce « 11 tests, dont 6
  régression sécurité » ; `ls apps/api/tests/*.py | wc -l` = 112 fichiers,
  ~22 800 lignes cumulées, couvrant POS, fidélité, fiscal (`test_fiscal.py`,
  `test_fiscal_v2.py`, `test_nf525_chain.py`, `test_migration_0072.py`,
  `test_tva_service.py`, etc.). Un contributeur qui fait confiance à ce
  chiffre risque de recoder un test qui existe déjà.

### P3-3 — Docstring obsolète sur le remboursement CB
- **Fichier** : `apps/api/app/api/pos/router.py:2777` — « Le remboursement CB
  est enregistré (record only — l'appel SumUp est un TODO) ». En réalité
  l'appel SumUp réel est implémenté et branché plus bas dans la même fonction
  (`apps/api/app/api/pos/router.py:2813-2877`, incluant gestion d'erreur et
  journalisation `sumup_exchange_log`). Le commentaire n'a simplement jamais
  été mis à jour après l'implémentation.

### P3-4 — Faux positifs "XXX" — aucun vrai TODO/FIXME/HACK notable dans le code
- Les seules occurrences de `TODO|FIXME|XXX|HACK` dans `apps/api/app` et
  `apps/web|site/src` sont soit des tailles de vêtements (`XXL`, `XXXL`),
  soit des masques de numéro (`SIRET : XXX XXX XXX XXXXX`,
  `ANNIV-XXXXXX`), soit deux TODO mineurs sans risque :
  `apps/api/app/api/pos/router.py:2777` (cf. P3-3, déjà résolu en pratique)
  et `scripts/ai_benchmark.py:47` (flag `--regenerate-samples` non implémenté
  dans un script d'outillage, pas de chemin de prod).

### P3-5 — `apps/site/src/lib/platform.ts` revendique un "miroir" de `apps/web` qui n'en est plus un
- **Fichier** : `apps/site/src/lib/platform.ts:5-7` — « Mirrors
  apps/web/src/lib/platform.ts so we don't duplicate UA-sniffing ». En
  pratique les deux fichiers ont divergé (le site ajoute `isIOS()`, absent
  côté web, qui n'a plus de branche iOS du tout — cf. P2-2). Ce n'est pas un
  bug (le site a un besoin légitime : distinguer Apple Wallet / Google
  Wallet), mais le commentaire pourrait laisser croire à tort qu'un diff des
  deux fichiers doit rester vide.

### P3-6 — Versions désynchronisées entre `app/version.py` et les manifestes (constat lié au working tree non commité, voir note en tête de rapport)
- `apps/api/app/version.py` (non commité) : `APP_VERSION = "1.1.5"`.
  `apps/api/pyproject.toml`, `apps/web/package.json`,
  `apps/site/package.json` : `"1.1.2"`. À aligner avant de committer ce
  changement en cours.

## Quick wins sûrs (preuve de non-référence fournie, aucun risque fonctionnel)

1. **Supprimer `apps/api/app/services/cash_drawer.py`** (classe
   `CashDrawerService`) — 0 import trouvé dans `apps/api/app` ni
   `apps/api/tests` en dehors du fichier lui-même (P2-4). Vérifié aussi
   qu'aucun test ne l'importe.
2. **Supprimer `apps/api/app/services/barcode.py`** et retirer la dépendance
   `python-barcode` de `apps/api/pyproject.toml` — 0 appelant de
   `generate_barcode()`, et `import barcode`/`from barcode...` n'apparaît nulle
   part ailleurs dans `apps/api/app` (P2-5). `Pillow` reste nécessaire (utilisé
   par `apps/api/app/services/storefront_photo.py`), ne pas y toucher.
3. **Retirer la prop `onPrintAirprint`** de l'interface `Props` dans
   `apps/web/src/components/pos/ReceiptPreviewCard.tsx:19-23` — jamais
   déstructurée dans la signature de la fonction (lignes 48-60), et le seul
   appelant (`apps/web/src/app/pos/page.tsx:3156`) ne la passe pas.
4. **Mettre à jour les 3 occurrences de `.toFixed(2)` d'affichage brut** dans
   `apps/site/src/app/account/historique/page.tsx:102,112` et
   `apps/site/src/app/account/page.tsx:246,297` pour utiliser
   `formatPriceEuros`/`formatPriceCents` (`apps/site/src/lib/format.ts`) —
   correction cosmétique pure, la fonction cible existe déjà et est déjà
   utilisée ailleurs dans les mêmes fichiers pour d'autres montants.
5. **Documentation** (aucun risque, mais nécessite une relecture ciblée plutôt
   qu'un simple `sed`) : purger `AirPrint`/`iPad`/`SATO CT4-LX`/`sato_service.py`
   de `README.md`, `docs/DEPLOIEMENT.md`, `docs/MANUEL_BOUTIQUE.md`,
   `docs/ARCHITECTURE.md`, `docs/UX_DESIGN.md`, `docs/DEPLOIEMENT_FIDELITE.md`
   et remplacer les références à `scripts/seed_data.py` /
   `scripts/seed_test_products.py` par `scripts/seed_demo_products.py` /
   `scripts/seed_witness_clients.py` (`README.md:34`, `CLAUDE.md`).

## À ne pas toucher (ressemble à du mort ou à un bug, mais ne l'est pas)

- **`POST /api/crm/clients/{id}/loyalty/earn` et `/loyalty/redeem`**
  (`apps/api/app/api/crm/router.py:809-835`) renvoient systématiquement
  `HTTPException(410, ...)`. Ça ressemble à du code oublié après le retrait
  documenté du "rachat direct de points" (`CLAUDE.md`), mais c'est en fait une
  tombstone volontaire : le corps de la fonction ne fait rien d'autre que
  documenter/retourner l'erreur 410 pour tout appelant historique — bonne
  pratique de dépréciation, pas une régression à corriger.
- **`SumUpService.is_sandbox`** (`apps/api/app/services/sumup_service.py:248-262`)
  détecte un préfixe de clé `sup_sk_test_`. Ça peut sembler contredire
  `CLAUDE.md`/`sumup_service.py:1-11` ("le mode sandbox/simulation a été
  retiré"), mais c'est une fonctionnalité différente et toujours désirée :
  elle sert uniquement à afficher un bandeau d'alerte côté caisse si une clé
  de test a été configurée par erreur en prod (`describe()`,
  `ping_reader()`), jamais à simuler un paiement réussi. Preuve :
  `grep -n "is_sandbox" apps/api/app/api/pos/router.py` ne montre que des
  vérifications de garde (`if settings.is_production and service.is_sandbox`),
  aucune branche de simulation de paiement.
- **Deux fonctions `_generate_barcode()`** dans
  `apps/api/app/services/product_intake.py:77-79` et
  `apps/api/app/api/inventory/permanent.py:96-103` ressemblent à une
  duplication à fusionner. Ce n'en est pas une : elles produisent
  délibérément deux formats distincts (`VTZ######` pour les produits
  d'occasion, `VTZP-{année}-######` pour les "articles permanents") — le
  préfixe différent est explicitement documenté comme un signal pour
  l'export comptable, pas une redite accidentelle.
- **Chaîne de migrations Alembic 0001→0075** : strictement linéaire (aucun
  trou de numérotation, aucune branche), et les migrations qui s'exécutent
  réellement sur un bootstrap frais (0072-0075, au-delà de `BASELINE_REVISION
  = "0071"` dans `scripts/bootstrap_database.py:24`) sont toutes idempotentes
  (`IF NOT EXISTS` / `CREATE OR REPLACE` / vérifications d'existence de
  colonne avant `ADD COLUMN`) — bon état, rien à signaler malgré le volume
  (75 fichiers).
- **Dépendances déclarées** (`apps/api/pyproject.toml` hors `python-barcode`
  signalé en P2-5 ; `apps/web/package.json` ; `apps/site/package.json`) :
  toutes les dépendances runtime (y compris `@zxing/browser` côté web et
  `qrcode` côté site, qui semblaient à première vue inutilisées) ont été
  retrouvées utilisées après recherche précise de leur point d'import réel
  (`apps/web/src/app/inventory/scan/page.tsx:51` et
  `apps/site/src/components/WalletCard.tsx:4`).
- **Fichiers composants/hooks front** : un scan systématique de
  `apps/web/src/components`, `apps/web/src/hooks` et `apps/site/src/components`
  (référence croisée de chaque nom de fichier contre le reste de l'arbre) n'a
  trouvé aucun fichier orphelin — le front-end est bien élagué.
