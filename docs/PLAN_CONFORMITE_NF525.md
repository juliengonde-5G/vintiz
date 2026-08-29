# Plan de mise en conformité fiscale — Vintiz POS

> **Statut : plan de travail actif, ouvert le 29 août 2026.**
> Le logiciel n'est **pas** certifié et ne doit pas être présenté comme conforme
> tant que les lots 1 et 2 ne sont pas clos. La mention admise dans l'intervalle
> reste : « version candidate à la certification NF525 ».

| | |
|---|---|
| Version applicative concernée | `APP_VERSION = 1.2.0` (`apps/api/app/version.py:3`) |
| Révision de base attendue | `0076` en branche de travail, `0075` sur `main` (`apps/api/app/version.py:4`) |
| Version de signature fiscale | `2` (`apps/api/app/version.py:5`) |
| Source du plan | Audit de conformité du 29/08/2026 — 46 exigences, 5 écarts bloquants, 7 majeurs, 7 mineurs |
| Documents liés | `docs/COMPLIANCE_NF525.md` (auto-déclaration, **à réaligner**, écart m-2), `docs/DOSSIER_CERTIFICATION_NF525.md` (dossier de présentation) |
| Responsable du plan | *(à nommer — voir §7)* |

---

## 1. Cadre réglementaire et voie de preuve retenue

### 1.1 L'obligation

Le **3° bis du I de l'article 286 du CGI** impose à tout assujetti à la TVA qui
enregistre les règlements de ses clients au moyen d'un logiciel de caisse
d'utiliser un logiciel satisfaisant à quatre conditions cumulatives :

| Pilier | Ce que la loi exige |
|---|---|
| **Inaltérabilité** | Une donnée d'encaissement enregistrée ne peut plus être modifiée ni supprimée ; toute correction se fait par une opération inverse tracée. |
| **Sécurisation** | Les données sont protégées de bout en bout : numérotation continue, identification de l'opérateur, intégrité prouvable. |
| **Conservation** | Clôtures périodiques obligatoires (journalière, mensuelle, annuelle) avec cumuls et grand total, données conservées 6 ans. |
| **Archivage** | Archives figées, datées, scellées, restituables dans un format lisible et contrôlable hors du logiciel. |

Le commentaire administratif applicable est le **BOI-TVA-DECLA-30-10-30**
(version publiée le 25 mars 2026). Le manquement est sanctionné d'une amende de
7 500 € par logiciel, avec obligation de régularisation sous 60 jours.

### 1.2 Les deux voies de preuve

| Voie | Contenu | Qui peut l'emprunter |
|---|---|---|
| **A — Certificat d'organisme accrédité** | Audit externe (référentiel **NF525** d'Infocert/AFNOR Certification, ou référentiel du **LNE**) : examen documentaire, revue de code, tests d'inaltérabilité, audit du processus de développement. Certificat nominatif par version. | Tout éditeur ou détenteur de solution. |
| **B — Attestation individuelle de l'éditeur** | Déclaration écrite du représentant légal de l'éditeur, sur le modèle **BOI-LETTRE-000242**, engageant sa responsabilité sur les quatre conditions. | L'**éditeur** du logiciel. |

### 1.3 Position de Vintiz — et pourquoi elle doit être tranchée par écrit

Vintiz est à la fois **exploitant** (la boutique de Vernon encaisse avec ce
logiciel) et **auteur** du logiciel (le code source est détenu et développé en
interne). C'est précisément le cas de figure que la doctrine encadre : un
logiciel développé par l'assujetti **pour ses propres besoins** doit en principe
être **certifié par un organisme accrédité** (voie A) ; l'attestation
individuelle (voie B) est réservée à celui qui exerce une **activité réelle
d'édition** de logiciels ou de systèmes de caisse.

Conséquence pratique pour ce plan :

- **Le travail technique est le même dans les deux voies.** Les lots 1 à 3
  ci-dessous doivent être réalisés quelle que soit l'issue juridique : ils
  corrigent des écarts au regard des quatre conditions légales, pas au regard
  d'un référentiel privé.
- **Le choix de la voie est une décision juridique**, à documenter par un avis
  écrit (pièce n° 2 du dossier, cf. `docs/DOSSIER_CERTIFICATION_NF525.md` §5).
  Elle conditionne uniquement la **pièce finale** : certificat d'organisme
  (voie A) ou attestation signée (voie B).
- **En l'absence d'avis tranchant en faveur de la voie B, la voie A est la
  position prudente** — c'est déjà la position retenue par
  `docs/COMPLIANCE_NF525.md:19-22`.

### 1.4 Périmètre du plan

Sont dans le périmètre fiscal : création des ventes/paiements/remboursements
(`/api/pos`), encaissement CB SumUp, tickets et factures, tiroirs et clôtures Z,
clôtures périodiques, archives et exports (FEC et export de chaîne), signature
et chaînage (`apps/api/app/services/fiscal.py`, `fiscal_closure.py`,
`fiscal_export.py`, `accounting_service.py`), triggers de la migration `0072`,
gestion de la clé `FISCAL_SIGNING_KEY`, et les scripts d'exploitation qui
touchent ces données (`scripts/go_live_reset.py`, `scripts/deploy.sh`).

Sont hors périmètre : CRM, inventaire, IA, site vitrine — sauf lorsqu'ils
figent une donnée dans une vente (libellé d'article, remise, coupon, taux de
TVA du produit, moyen de paiement).

---

## 2. Où en est-on au 29 août 2026

### 2.1 En une phrase

Le socle fiscal est **sain** (signature HMAC-SHA256 v2 couvrant l'intégralité de
la vente, chaînage avec genesis explicite, triggers PostgreSQL, numérotation
sans trou sous verrou consultatif, clôtures scellées et chaînées, archives
SHA-256, FEC équilibré) ; ce sont ses **frontières** qui ne le sont pas encore
(script d'effacement livré en production, privilèges de base de données,
héritage de signature v1, absence de preuve automatisée, duplicata).

### 2.2 Tableau de bord des écarts

Effort : **S** ≤ 1 jour · **M** = 2 à 5 jours · **L** > 5 jours ou dépendance externe.

| Réf. | Écart | Gravité | Lot | Effort | Statut au 29/08/2026 |
|---|---|---|---|---|---|
| B-1 | Effacement fiscal possible par `go_live_reset.py` | Bloquant | 1 | M | 🟡 **partiellement corrigé (2026-08-29)** |
| B-2 | Compte applicatif PostgreSQL superutilisateur | Bloquant | 1 | M | 🔴 à faire |
| B-3 | Signature v1 non clefée acceptée (03/06 → 15/07/2026) | Bloquant | 1 | M | 🔴 à faire |
| B-4 | Aucune preuve automatisée d'inaltérabilité (CI sur SQLite) | Bloquant | 1 | M | 🔴 à faire |
| B-5 | Réimpressions non identifiées comme duplicata | Bloquant | 1 | S (reliquat) | 🟢 **corrigé (2026-08-29)** — 2 reliquats |
| M-1 | TVA figée à 20 %, `tva_service` non branché | Majeur | 2 | L | 🔴 à faire |
| M-2 | Vente pouvant échapper définitivement à toute clôture Z | Majeur | 2 | M | 🔴 à faire |
| M-3 | Journal d'événements ni inaltérable ni complet | Majeur | 2 | L | 🔴 à faire |
| M-4 | Mode dégradé non maîtrisé (horodatage, pertes, marquage) | Majeur | 2 | L | 🔴 à faire |
| M-5 | Z sans cumul perpétuel, montants de caisse mutables | Majeur | 2 | M | 🔴 à faire |
| M-6 | Contrôle d'intégrité non automatisé, clôtures muettes | Majeur | 2 | M | 🔴 à faire |
| M-7 | Verrouillage intangible du Z resté manuel | Majeur | 2 | S | 🔴 à faire |
| m-1 | Mention « Conforme NF525 » envoyée au comptable | Mineur | 3 | S | 🔴 à faire |
| m-2 | Auto-déclaration périmée (1.1.1 / 0072) | Mineur | 3 | S | 🔴 à faire |
| m-3 | CHANGELOG interrompu à 1.1.2 | Mineur | 3 | S | 🔴 à faire |
| m-4 | Deux mécanismes de numérotation concurrents | Mineur | 3 | S | 🔴 à faire |
| m-5 | Journées de caisse bornées en UTC | Mineur | 3 | S | 🔴 à faire |
| m-6 | Anonymisation RGPD non journalisée | Mineur | 3 | S | 🔴 à faire |
| m-7 | Sauvegardes à 30 jours, sur le même volume | Mineur | 3 | M | 🔴 à faire |
| D-1…D-10 | Dix pièces documentaires manquantes | Bloquant *dossier* | 3 | L | 🔴 à faire |

**Reste à faire : 4 écarts bloquants (dont 1 partiel), 7 majeurs, 7 mineurs, 10
pièces documentaires.**

---

## 3. Fiches de correction

Chaque fiche indique : le constat, la correction concrète (fichier et couche —
code / base / ops / CI / documentation), le **critère d'acceptation vérifiable**
(ce qu'un auditeur peut rejouer), l'effort et les dépendances.

### 3.1 Écarts bloquants

---

#### B-1 — `go_live_reset.py` peut effacer la chaîne fiscale en contournant les triggers

**Constat.** `scripts/go_live_reset.py` liste `transactions`,
`transaction_items`, `payments`, `receipts`, `payment_attempts`, `z_reports`,
`cash_drawers`, `cash_movements`, `accounting_exports`,
`accounting_export_lines` dans `TABLES_TO_WIPE` (`scripts/go_live_reset.py:86-117`)
et les vide par `TRUNCATE … RESTART IDENTITY CASCADE`. Or **`TRUNCATE` ne
déclenche pas** les triggers `BEFORE DELETE … FOR EACH ROW` posés par la
migration `0072` : l'effacement est silencieux et complet. Le garde-fou du
script ne contrôle que l'inventaire. Un logiciel candidat ne peut pas embarquer,
dans son image de production, un effacement fiscal en une commande.

**Déjà corrigé — ✅ 2026-08-29 (partiel)**

| Correction appliquée | Emplacement |
|---|---|
| Refus inconditionnel du mode réel quand `ENVIRONMENT=production` (code retour 3), avec message renvoyant vers la restauration de sauvegarde ou un environnement clone. Le `--dry-run` reste autorisé (lecture seule). | `scripts/go_live_reset.py` — garde ajoutée avant l'affichage du plan |
| Correction du carve-out `events_log` sous PostgreSQL : `events_log` référençant `clients` et `transactions`, le `CASCADE` le tronquait **en entier**, carve-out `product.created` compris. Les lignes préservées sont désormais snapshotées dans une table temporaire `_events_keep ON COMMIT DROP` avant le `TRUNCATE`, puis réinsérées. | `scripts/go_live_reset.py`, branche `dialect == "postgresql"` |

**Reste à faire.**

| # | Action | Couche |
|---|---|---|
| B-1.a | Retirer les tables fiscales de `TABLES_TO_WIPE` — ou, mieux, **supprimer le script** : son unique usage légitime (go-live du 03/06/2026) est consommé. | Code / ops |
| B-1.b | Si le script est conservé, ajouter une seconde garde indépendante de l'environnement : `SELECT count(*) FROM transactions WHERE hash_chain <> ''` > 0 → abandon. Une variable d'environnement mal positionnée ne doit pas suffire à ouvrir la porte. | Code |
| B-1.c | Migration dédiée posant des triggers **`BEFORE TRUNCATE`** (niveau instruction) sur `transactions`, `transaction_items`, `payments`, `z_reports`, `fiscal_closures`, `cash_drawers` : c'est la seule barrière côté base qui couvre ce cas. | Base (nouvelle migration Alembic) |
| B-1.d | Mettre à jour la section « Reset pré-ouverture (go-live 1.0) » de `CLAUDE.md` et ajouter une entrée `docs/CHANGELOG.md`. | Documentation |

**Critère d'acceptation.** Sur une base de recette contenant au moins une vente
signée : (1) `python scripts/go_live_reset.py --confirm` s'arrête avec un code
retour non nul et n'écrit rien ; (2) `TRUNCATE TABLE transactions;` exécuté
manuellement en `psql` échoue avec un message `NF525:` ; (3) un test automatisé
couvre les deux cas (lié à B-4).

**Effort : M** · **Dépendances :** B-1.c doit être livrée avant que B-4 puisse
tester le refus de `TRUNCATE`.

---

#### B-2 — Le compte applicatif PostgreSQL est propriétaire et superutilisateur

**Constat.** L'API se connecte avec `POSTGRES_USER`
(`docker/docker-compose.prod.yml:28-31`), qui est le rôle d'amorçage de l'image
`pgvector/pgvector:pg16` — donc **superutilisateur du cluster et propriétaire
des tables**. `ALTER TABLE transactions DISABLE TRIGGER ALL`,
`SET session_replication_role = 'replica'`, `DROP TRIGGER` et `TRUNCATE` sont à
la portée permanente de l'identité applicative. Aucun rôle applicatif dégradé
n'est créé, ni par Alembic ni par `scripts/bootstrap_database.py`.

**Pourquoi c'est bloquant.** Un certificateur teste l'inaltérabilité **avec les
droits dont dispose réellement l'exploitant**. En l'état, les triggers protègent
contre l'erreur, pas contre l'intention : ils ne sont pas opposables.

**Correction.**

| # | Action | Couche |
|---|---|---|
| B-2.a | Créer deux rôles : `vintiz_owner` (propriétaire des tables, utilisé **uniquement** par Alembic au déploiement) et `vintiz_app` (non-superutilisateur, non-propriétaire, `NOINHERIT`). | Base |
| B-2.b | Sur `vintiz_app` : `GRANT SELECT, INSERT, UPDATE` sur les tables métier ; `GRANT SELECT, INSERT` seulement sur `transactions`, `transaction_items`, `payments`, `z_reports`, `fiscal_closures` ; `REVOKE DELETE, TRUNCATE` explicitement sur ces cinq tables. Prévoir les `UPDATE` légitimes restants (pose du `hash_chain` à la signature, `client_id`) par colonne : `GRANT UPDATE (hash_chain, fiscal_signature_version, client_id) ON transactions`. | Base |
| B-2.c | Pointer le `DATABASE_URL` de l'API sur `vintiz_app` ; n'utiliser `vintiz_owner` que dans l'étape `alembic upgrade head` de `scripts/deploy.sh:227-233` (variable dédiée `DATABASE_MIGRATION_URL`). | Ops / déploiement |
| B-2.d | Documenter la matrice de droits et la liste nominative des détenteurs d'un accès `psql` en production (pièce D-5 du dossier). | Documentation |

**Critère d'acceptation.** Connecté en `vintiz_app` : `ALTER TABLE transactions
DISABLE TRIGGER ALL` → `must be owner of table` ; `TRUNCATE transactions` →
refusé ; `DELETE FROM payments WHERE …` → refusé ; `SET session_replication_role
= 'replica'` → `permission denied to set parameter`. Une vente complète
(encaissement espèces + CB) passe sans erreur avec ce rôle, ainsi qu'une clôture
Z et une clôture mensuelle. Procès-verbal joint au dossier.

**Effort : M** · **Dépendances :** aucune côté code ; nécessite une fenêtre de
maintenance et une sauvegarde préalable. À livrer **avant** B-4 (le test de
B-4 doit s'exécuter avec le rôle dégradé pour avoir une valeur probante).

---

#### B-3 — Signature v1 non clefée, couvrant six semaines d'exploitation réelle

**Constat.** `FiscalService.verify_chain_integrity` accepte encore le format v1
(`apps/api/app/services/fiscal.py:204-211`) : un `sha256("numéro|total|date|hash_précédent")`
**sans clé**, qui ne couvre ni les lignes, ni les paiements, ni le caissier. La
migration `0072` a posé `fiscal_signature_version … DEFAULT 1` pour l'existant.
Toutes les transactions du **03/06/2026 au 15/07/2026** — les six premières
semaines d'exploitation — portent donc une empreinte que quiconque peut
recalculer sans secret. Même constat pour les Z (`fiscal.py:436-458`).

**Correction.** On ne réécrit pas le passé (ce serait précisément l'altération
que la loi interdit) : on l'**ancre**.

| # | Action | Couche |
|---|---|---|
| B-3.a | Produire une **clôture périodique de scellement** de type `perpetual` (le type existe déjà, `apps/api/app/services/fiscal_closure.py:52-58`) couvrant du 03/06/2026 au 15/07/2026 inclus : elle place l'intégralité des lignes v1 sous un manifest HMAC v2 chaîné et sous un SHA-256 d'archive. | Exploitation (appel `POST /api/admin/fiscal-closures`) |
| B-3.b | Archiver le SHA-256 de cette clôture **hors ligne** : impression signée par la responsable boutique, copie chez l'expert-comptable, horodatage daté. C'est ce document qui donne date certaine à l'ancrage. | Ops / documentation |
| B-3.c | Documenter explicitement au dossier que les transactions antérieures au 15/07/2026 relèvent d'un **régime de preuve dégradé, scellé a posteriori** — ne pas prétendre l'inverse. | Documentation (`DOSSIER_CERTIFICATION_NF525.md` §3.1) |
| B-3.d | Fixer et inscrire au code la **date de retrait** de la branche v1 de `verify_chain_integrity` (proposition : au terme du délai de reprise fiscale portant sur l'exercice 2026), avec un commentaire daté. | Code |
| B-3.e | Traiter au passage un effet de bord identifié au dossier : `verify_chain_integrity` recalcule tout avec la clé **courante** — une rotation de `FISCAL_SIGNING_KEY` invaliderait en bloc l'historique. Prévoir un porte-clés versionné (`key_id` persisté sur la transaction) ou interdire formellement la rotation par procédure (pièce D-4). | Code ou procédure |

**Critère d'acceptation.** `GET /api/admin/fiscal-closures/integrity` renvoie
valide ; la clôture de scellement existe, son archive se télécharge, son
SHA-256 recalculé hors ligne correspond à l'en-tête `X-Archive-SHA256` ; le
document d'ancrage est signé et daté ; le dossier ne revendique aucune propriété
cryptographique forte sur la période v1.

**Effort : M** (dont B-3.e seul peut valoir M) · **Dépendances :** la clôture
de scellement échoue si la chaîne est rompue ou si un tiroir est resté ouvert
(`fiscal_closure.py:71-93`) — donc à faire après vérification d'intégrité.

---

#### B-4 — Aucune preuve automatisée de l'inaltérabilité

**Constat.** La suite `pytest` de la CI s'exécute sur **SQLite**
(`.github/workflows/ci.yml`, step « Tests », `DATABASE_URL: sqlite+aiosqlite:…`),
où les triggers PostgreSQL n'existent pas. `apps/api/tests/test_migration_0072.py`
ne vérifie que la *forme* des instructions SQL (nombre de `CREATE TRIGGER`,
absence de point-virgule hors corps de fonction), jamais leur *effet*. Les 7
tests de `apps/api/tests/test_nf525_chain.py` utilisent des `MagicMock` dont
`int(fiscal_signature_version)` vaut 1 : ils valident le chemin **v1 déprécié**.
Le point 3 de la recette de `docs/COMPLIANCE_NF525.md:159-160` (« prouver qu'une
altération SQL est refusée ») reste une intention non exécutée.

**Correction.** Ajouter un **job CI dédié** sur le service PostgreSQL déjà
déclaré dans `.github/workflows/ci.yml` (`image: pgvector/pgvector:pg16`), qui,
après `alembic upgrade head`, exécute une classe de tests d'inaltérabilité —
idéalement **sous le rôle dégradé de B-2**, pour que le test reflète les droits
réels de production.

Scénarios minimaux à couvrir :

| Test | Attendu |
|---|---|
| `UPDATE transactions SET total_ttc = …` sur une vente signée | `NF525: modification transaction signee interdite` |
| `DELETE FROM transactions` sur une vente signée | `NF525: suppression transaction signee interdite` |
| `INSERT INTO transaction_items` rattaché à une vente signée | `NF525: lignes/paiements d une transaction signee immuables` |
| `UPDATE`/`DELETE` sur `payments` d'une vente signée | idem |
| `UPDATE z_reports SET total_sales = 0` | `NF525: modification donnees scellees Z interdite` |
| `DELETE FROM z_reports` | `NF525: suppression Z interdite` |
| `UPDATE` et `DELETE` sur `fiscal_closures` | `NF525: cloture fiscale immuable` |
| `UPDATE cash_drawers SET opened_at = …` sur un tiroir clôturé | `NF525: periode tiroir cloturee immuable` |
| `TRUNCATE transactions` | refusé (**après** livraison de B-1.c) |
| Bout en bout : vente → altération d'une ligne en base par un rôle privilégié → `verify_chain_integrity` | renvoie `signature_mismatch` |

Compléter par des tests de signature **v2 réelle** (non `MagicMock`) :
`apps/api/tests/test_fiscal_v2.py` n'en compte aujourd'hui que deux.

**Critère d'acceptation.** Le job CI est vert sur `main`, échoue si un trigger
est retiré (test de mutation : commenter un `CREATE TRIGGER` doit faire rougir
la CI), et son journal d'exécution est joignable au dossier comme preuve.

**Effort : M** · **Dépendances :** B-1.c (test `TRUNCATE`), B-2 (exécution sous
rôle dégradé — sinon le test reste faisable mais moins probant).

---

#### B-5 — Réimpressions non identifiées comme duplicata

**Constat initial.** Aucune occurrence de « DUPLICATA » dans le code. Le chemin
réseau `POST /api/pos/transactions/{id}/print` traçait une réimpression sans la
marquer ; le chemin **effectivement utilisé en boutique** (tablette Android,
WebUSB → `GET /api/pos/transactions/{id}/escpos`) rendait des octets strictement
identiques à l'original, sans aucune trace, autant de fois que voulu. Deux
tickets rigoureusement indiscernables pouvaient donc circuler.

**Déjà corrigé — ✅ 2026-08-29**

| Correction appliquée | Emplacement |
|---|---|
| Compteur d'émissions serveur `_count_receipt_prints()` : compte les entrées d'audit `receipt.reprint` **et** `receipt.escpos` de la transaction. La 1ʳᵉ émission est l'original, toute suivante un duplicata numéroté. | `apps/api/app/api/pos/router.py` |
| Le chemin réseau passe `duplicata_number=prior_prints or None` à `escpos_service.print_receipt` et journalise `copy_number` + `duplicata` dans l'`AuditLog`. | `apps/api/app/api/pos/router.py` |
| Le chemin WebUSB `GET /escpos` **écrit désormais** un `AuditLog action="receipt.escpos"` (avec `copy_number` et `duplicata`) et passe le même `duplicata_number` au rendu, avant de rendre les octets. La décision est côté serveur : le client ne choisit pas. | `apps/api/app/api/pos/router.py` |
| Rendu : bandeau centré, gras, double hauteur `* DUPLICATA n.X *` inséré juste après l'en-tête du ticket. | `apps/api/app/services/escpos_service.py`, `build_receipt(..., duplicata_number)` |
| Le commentaire trompeur affirmant que « NF525 n'oblige pas à versionner les réimpressions » a été supprimé et remplacé par l'énoncé correct. | `apps/api/app/api/pos/router.py` |

**Reliquats à traiter.**

| # | Reliquat | Couche | Effort |
|---|---|---|---|
| B-5.a | Deux autres canaux d'émission du ticket ne sont ni comptés ni marqués : `GET /api/pos/transactions/{id}/receipt` (rendu texte, `apps/api/app/api/pos/router.py:2626`) et `POST /api/pos/transactions/{id}/resend` (envoi e-mail/SMS). Il faut y appliquer le même compteur et faire porter la mention duplicata par `ReceiptService.generate_receipt_text` (`apps/api/app/services/receipt.py:54`). | Code | S |
| B-5.b | Le compteur repose sur `audit_logs`, table aujourd'hui **librement modifiable et supprimable** (écart M-3). Tant que M-3 n'est pas traité, le compteur de copies n'est pas inaltérable. Cible : table dédiée `receipt_prints` (transaction, séquence, opérateur, canal réseau/WebUSB/texte/e-mail, horodatage) protégée par trigger, ou chaînage de `audit_logs`. | Code + base | M |

**Critère d'acceptation.** Imprimer trois fois le même ticket par des canaux
différents produit : un original non marqué, puis « DUPLICATA n.1 », puis
« DUPLICATA n.2 » ; `GET /api/admin/audit-logs?entity=transaction&action=receipt.escpos`
montre les trois émissions avec leur `copy_number` et l'opérateur ; aucun canal
ne permet d'obtenir une copie non marquée.

**Effort restant : S** (B-5.a) **+ M** (B-5.b) · **Dépendances :** B-5.b dépend
de M-3.

---

### 3.2 Écarts majeurs

---

#### M-1 — Ventilation TVA figée à 20 % et `tva_service` non branché

**Constat.** `total_ht = total_ttc / 1.20` en dur
(`apps/api/app/services/pos.py:336-338`) ; `TransactionItem.tva_rate` n'est
**jamais renseigné** à la vente (`pos.py:405-417`) et retombe sur le défaut
20,00 (`apps/api/app/models/pos.py:180-182`). Le service
`apps/api/app/services/tva_service.py`, qui gère correctement les cinq taux
français et l'agrégation multi-taux, **n'est appelé nulle part** dans le flux de
vente. `Product.tva_rate` (`apps/api/app/models/product.py:116`) est donc ignoré.
Le ticket affiche un taux issu de la **configuration boutique courante**
(`apps/api/app/services/escpos_service.py:382-384`,
`apps/api/app/services/receipt.py:152`), pas de la transaction : une
réimpression après changement de configuration afficherait un autre taux que
l'original.

**Portée réelle.** En vente de seconde main au taux normal, l'incidence
comptable actuelle est nulle. L'écart devient **une erreur de déclaration** dès
la première vente à 5,5 % ou 10 % (livre, produit alimentaire, prestation) et il
est de toute façon **structurellement disqualifiant** : le référentiel attend
une ventilation par taux portée par la transaction.

**Correction.**

| # | Action | Couche |
|---|---|---|
| M-1.a | Dans `PosService.create_transaction`, résoudre le taux **par ligne** : `Product.tva_rate` → `PermanentItem.tva_rate` → défaut de configuration ; poser la valeur sur `TransactionItem.tva_rate`. | Code (`services/pos.py`) |
| M-1.b | Calculer HT et TVA via `tva_service.compute_line_totals` + `aggregate_totals` au lieu de la division en dur. | Code |
| M-1.c | Répercuter dans le remboursement : `apps/api/app/services/refund.py:244-257` recopie déjà `discount_percent`, il doit recopier `tva_rate`. | Code |
| M-1.d | Rendre les tickets multi-taux, en lisant les taux **depuis les lignes de la transaction** (`receipt.py:148-152`, `escpos_service.py:380-386`) et non depuis la configuration courante. | Code |
| M-1.e | Vérifier la ventilation dans le FEC (`services/accounting_service.py`) et l'export de chaîne. | Code |
| M-1.f | Le payload signé v2 contient déjà `tva_rate` par ligne : aucun changement de version de signature n'est nécessaire, mais la recette doit vérifier qu'une vente multi-taux se vérifie correctement. | Recette |

**Critère d'acceptation.** Une vente comportant une ligne à 20 %, une à 10 % et
une à 5,5 % produit : des `TransactionItem.tva_rate` distincts en base, un
`total_tva` égal à la somme des TVA par ligne (au centime), un ticket affichant
un bloc de ventilation par taux, un FEC équilibré avec les bons comptes de TVA,
et une chaîne fiscale valide. La réimpression du ticket après modification du
taux de configuration boutique affiche **les taux d'origine**.

**Effort : L** · **Dépendances :** aucune, mais toucher au calcul des totaux
impose une recette POS complète (espèces, CB, mixte, remise, coupon, avoir,
remboursement partiel).

---

#### M-2 — Une vente peut échapper définitivement à toute clôture Z

**Constat.** `PosService.close_drawer` (`apps/api/app/services/pos.py:695-792`)
ne prend **aucun verrou**, et `generate_z_report` en prend un **différent** de
celui des ventes : `pg_advisory_xact_lock(5252027)` (`services/fiscal.py:246-248`)
contre `5252026` pour les ventes (`services/pos.py:86-90`). Une vente engagée
avant la fermeture mais validée après le calcul du Z porte un `created_at`
**dans** la fenêtre du tiroir et échappe pourtant aux totaux. Pire : elle est
ensuite classée « couverte » par `_classify_window` (`services/fiscal.py:504-517`)
et **ne peut plus être régularisée**. La vente devient définitivement invisible
de toute clôture journalière.

**Correction.**

| # | Action | Couche |
|---|---|---|
| M-2.a | Prendre `pg_advisory_xact_lock(5252026)` — **le même** que les ventes — en tête de `PosService.close_drawer`, avant de figer `closed_at`. Le Z devient strictement postérieur à toute vente de la période. | Code |
| M-2.b | Ajouter au Z un contrôle de cohérence : `count(transactions dans la fenêtre) == transaction_count` ; en cas d'écart, refuser la clôture ou lever une alerte tracée (dépend de M-6). | Code |
| M-2.c | Vérifier le même point sur le chemin de garde 23 h 59 (`close_open_drawers`, `services/fiscal.py:581-648`) — il prend déjà `5252026`, ce qui confirme que c'est le bon verrou. | Code |

**Critère d'acceptation.** Test d'intégration concurrent : ouvrir une
transaction longue (verrou pris) puis lancer une clôture Z en parallèle ; la
clôture attend, et le Z produit **contient** la vente. Le compteur du Z égale
le décompte des ventes de la fenêtre.

**Effort : M** · **Dépendances :** M-6 pour l'alerte de M-2.b.

---

#### M-3 — Le journal des événements techniques n'est ni inaltérable ni complet

**Constat.** `audit_logs` est une table ordinaire
(`apps/api/app/models/audit.py:11-22`) : **aucun** hash, **aucun** chaînage,
**aucun** trigger d'immuabilité, aucune signature — elle est librement
modifiable et supprimable, y compris par l'application. Son contenu est par
ailleurs partiel : il couvre des entités métier (`services/audit.py:42-61`) mais
pas les événements techniques attendus (démarrage/arrêt du système, changement
de version, panne d'impression, passage en mode dégradé, échec de clôture,
changement d'heure).

**Correction.**

| # | Action | Couche |
|---|---|---|
| M-3.a | Ajouter à `audit_logs` un chaînage minimal : colonnes `previous_hash` et `hash` (HMAC sur `{user, action, entity, entity_id, data, created_at, previous_hash}`, même clé fiscale), plus un trigger `BEFORE UPDATE OR DELETE` refusant toute mutation. | Base (migration) + code |
| M-3.b | Élargir les événements journalisés : démarrage/arrêt de l'API avec version et révision DB (`apps/api/app/main.py:62-103`), échec d'impression, échec des crons fiscaux (`apps/api/app/jobs.py:571`, `:606`, `:639`), entrée et sortie de mode dégradé, résultat de chaque contrôle d'intégrité. | Code |
| M-3.c | Verser `audit_logs` dans le snapshot d'archive de clôture (`apps/api/app/services/fiscal_export.py:46-121`). | Code |
| M-3.d | Exposer le journal au contrôleur : `GET /api/admin/audit-logs` existe déjà (manager only) ; ajouter la vérification de chaîne du journal à l'endpoint d'intégrité. | Code |

**Critère d'acceptation.** `UPDATE audit_logs SET data = …` et
`DELETE FROM audit_logs` sont refusés par la base ; la chaîne du journal se
vérifie ; un redémarrage d'API, une panne d'impression simulée et un échec de
clôture apparaissent bien dans le journal ; l'archive de clôture contient le
journal de la période.

**Effort : L** · **Dépendances :** débloque B-5.b (compteur de duplicata
inaltérable) et M-6 (journalisation des contrôles).

---

#### M-4 — Mode dégradé non maîtrisé

**Constat.** Trois défauts cumulés dans `apps/web/src/lib/offline-queue.ts` :

1. La file hors ligne ne transporte **pas** l'horodatage de la vente
   (`offline-queue.ts:76-93`). Au rejeu, `created_at` prend le `now()` du
   serveur (`apps/api/app/models/base.py:15-19`) : une vente encaissée à 14 h 00
   et rejouée à 18 h 00 est datée 18 h 00 — et peut basculer de journée fiscale.
2. Le `drain` **supprime définitivement** une entrée de la file sur toute
   réponse 4xx (`offline-queue.ts:159-169`) : argent encaissé en boutique,
   écriture perdue, aucune trace serveur.
3. Rien ne marque une transaction comme « saisie en mode dégradé » :
   `client_uuid` est posé sur **toutes** les ventes POS, en ligne comme hors
   ligne, il ne discrimine rien.

**Correction.**

| # | Action | Couche |
|---|---|---|
| M-4.a | Ajouter au payload deux champs : `offline_captured_at` (ISO, horloge tablette) et `offline` (booléen). | Front + API |
| M-4.b | Persister les deux champs sur `Transaction`, **les inclure dans le payload signé** (`apps/api/app/services/fiscal.py:94-177`) et les protéger par le trigger d'inaltérabilité. Conserver `created_at` comme date d'enregistrement serveur : les deux dates coexistent et sont exposées sur le ticket et dans l'export. | Code + base |
| M-4.c | Ne plus supprimer une entrée sur 4xx : la déplacer vers un magasin « échecs à régulariser » et exposer un écran de reprise manager. | Front |
| M-4.d | Journaliser côté serveur, au rejeu, un événement technique `offline.replayed`. | Code (dépend M-3) |
| M-4.e | Écrire la procédure d'exploitation « que faire quand la caisse est hors ligne » (pièce D-7). | Documentation |

**Critère d'acceptation.** Une vente saisie hors ligne à 14 h 00 et rejouée à
18 h 00 porte les deux dates, est marquée `offline=true`, se vérifie
cryptographiquement, et la mention figure sur le ticket. Une réponse 4xx au
rejeu laisse la vente visible dans un écran de reprise ; aucune perte
silencieuse. L'ajout de `offline_captured_at` au payload signé impose un
**bump de `FISCAL_SIGNATURE_VERSION` à 3** et une branche de compatibilité en
vérification.

**Effort : L** · **Dépendances :** M-3 (journalisation) ; à coordonner avec M-5
si les deux modifient le payload signé — **une seule montée de version de
signature pour les deux**.

---

#### M-5 — Le Z ne porte pas de cumul perpétuel et ses montants de caisse restent mutables

**Constat.** Le payload signé du Z (`apps/api/app/services/fiscal.py:341-358`)
ne comporte **aucun grand total perpétuel** — NF525 attend un cumul non remis à
zéro sur la clôture journalière ; il n'existe aujourd'hui qu'au niveau des
clôtures périodiques (`services/fiscal_closure.py:132-193`). Par ailleurs le
trigger `vintiz_protect_closed_drawer_period`
(`apps/api/alembic/versions/0072_security_loyalty_nf525.py:191-209`) ne protège
que `opened_at` et `closed_at` : `opening_amount`, `closing_amount`,
`expected_amount`, les décomptes de billets et `closing_note` restent
**modifiables après émission du Z**, alors que l'écart de caisse est un élément
de contrôle. Ces montants ne figurent pas non plus dans le payload signé.

**Correction.**

| # | Action | Couche |
|---|---|---|
| M-5.a | Ajouter au payload signé du Z un bloc `total_perpetual` (mêmes agrégats que `fiscal_closure.py:142-156`, calculés jusqu'à `closed_at`) **et** les trois montants de caisse. | Code |
| M-5.b | Étendre le trigger `vintiz_protect_closed_drawer_period` à `opening_amount`, `closing_amount`, `expected_amount`, `opening_breakdown`, `closing_breakdown`, `closing_note` dès qu'un Z référence le tiroir. | Base (migration) |
| M-5.c | Monter `FISCAL_SIGNATURE_VERSION` à 3 et ajouter la branche de compatibilité dans `verify_z_chain_integrity` (`services/fiscal.py:385-472`). | Code |

**Critère d'acceptation.** Un Z fraîchement produit contient un cumul perpétuel
cohérent avec la dernière clôture périodique et les trois montants de caisse ;
`UPDATE cash_drawers SET closing_amount = …` sur un tiroir dont le Z est émis
est refusé par la base ; les Z antérieurs restent vérifiables via la branche de
compatibilité.

**Effort : M** · **Dépendances :** à grouper avec M-4.b (une seule montée de
version de signature).

---

#### M-6 — Contrôle d'intégrité non automatisé et clôtures qui échouent en silence

**Constat.** Aucun `verify_chain_integrity` dans `apps/api/app/jobs.py` : le
contrôle n'existe qu'à la demande (`apps/api/app/api/admin/fiscal_closures.py:61-70`)
et à chaque clôture périodique. Une rupture de chaîne survenue le 2 du mois peut
n'être découverte que le 1er du mois suivant. Les trois crons fiscaux
(`jobs.py:555-572` garde 23 h 59, `:575-607` mensuel, `:610-640` annuel) avalent
leurs exceptions dans un `logger.exception` et **ne notifient personne** : un
tiroir resté ouvert le 1er à 00 h 15 fait échouer silencieusement la clôture
mensuelle.

**Correction.**

| # | Action | Couche |
|---|---|---|
| M-6.a | Ajouter un cron quotidien `run_daily_fiscal_integrity_check` appelant `verify_chain_integrity`, `verify_z_chain_integrity` et `FiscalClosureService.verify_chain`, journalisant le résultat au journal technique (M-3). | Code (`jobs.py`) |
| M-6.b | Envoyer une **alerte e-mail** via `email_gateway` en cas d'invalidité — réutiliser `_send_discrepancy_alert` de `services/accounting_service.py:724` comme modèle. | Code |
| M-6.c | Faire de même sur l'échec de chacun des trois crons fiscaux : plus aucune exception avalée sans notification. | Code |
| M-6.d | Ajouter une relance automatique de la clôture mensuelle si un tiroir ouvert l'a fait échouer, après passage de la garde 23 h 59. | Code |

**Critère d'acceptation.** Rupture simulée (altération d'une ligne par un rôle
privilégié en base de recette) → e-mail d'alerte reçu sous 24 h et événement au
journal. Clôture mensuelle forcée en échec (tiroir laissé ouvert) → alerte, puis
clôture rattrapée automatiquement.

**Effort : M** · **Dépendances :** M-3 pour la journalisation.

---

#### M-7 — Verrouillage intangible du Z resté manuel

**Constat.** Le mécanisme est complet et idempotent
(`apps/api/app/services/fiscal.py:766-828` : PDF figé + SHA-256 persistés), mais
il est **purement manuel** : `close_drawer` (`apps/api/app/api/pos/router.py:1082-1164`)
ne l'appelle pas. En pratique, les Z ne sont donc pas verrouillés.

**Correction.** Appeler `lock_z_report` immédiatement après `generate_z_report`
dans les trois chemins : fermeture de caisse (`api/pos/router.py:1108-1140`),
garde 23 h 59 (`services/fiscal.py:641-647`), et flux de régularisation
(`api/pos/router.py:1345-1360`).

**Critère d'acceptation.** Après toute fermeture de caisse — manuelle,
automatique ou par régularisation — le Z porte un PDF figé et un SHA-256
persistés ; l'appel est idempotent (double fermeture → un seul verrouillage).

**Effort : S** · **Dépendances :** aucune. **C'est le meilleur rapport
effet/effort du plan.**

---

### 3.3 Écarts mineurs

| Réf. | Constat | Correction | Critère d'acceptation | Effort |
|---|---|---|---|---|
| **m-1** | L'e-mail du rapport Z au comptable affirme « Vintiz — Conforme NF525 / article 88 CGI » (`apps/api/app/services/fiscal.py:881`, `:892`), ce que `docs/COMPLIANCE_NF525.md:175-176` interdit explicitement. | Remplacer par « version candidate à la certification NF525 ». Ajouter un test de non-régression sur l'absence de la chaîne « Conforme NF525 » dans le code. | `grep -ri "conforme nf525" apps/` ne remonte plus rien hors documentation historique. | S |
| **m-2** | Auto-déclaration périmée : `docs/COMPLIANCE_NF525.md:4` et `:137` annoncent 1.1.1 / révision 0072 alors que le code est en 1.1.5 / 0076. | Réaligner version, révision et périmètre ; ajouter un tableau d'historique des versions fiscales et de leur qualification (fiscale / non fiscale). | Le document cite les mêmes valeurs que `apps/api/app/version.py` ; un test lit les deux et échoue en cas de divergence. | S |
| **m-3** | `docs/CHANGELOG.md:3` s'arrête à 1.1.2 ; trois versions (1.1.3, 1.1.4, 1.1.5) sont déployées sans entrée. | Compléter rétroactivement, en qualifiant chaque version « fiscale » ou « non fiscale ». | Une entrée par version déployée ; la version du code a toujours son entrée. | S |
| **m-4** | Deux mécanismes de numérotation concurrents : `alembic/versions/0025_transaction_number_seq.py:39-43` pose un `DEFAULT nextval()` que l'application n'utilise jamais (`services/pos.py:361-364`) ; la séquence reste figée. Idem `invoice_number_seq`. Un `INSERT` omettant la colonne casserait la numérotation. | Retirer le `DEFAULT` par migration (option retenue par défaut : l'allocation `MAX+1` sous verrou est le bon mécanisme et il est justifié en commentaire), et documenter le choix. | `information_schema.columns` ne montre plus de `column_default` sur `transactions.transaction_number` ; un test vérifie qu'un `INSERT` sans numéro échoue plutôt que d'inventer une valeur. | S |
| **m-5** | Journées de caisse bornées en UTC (`apps/api/app/api/pos/router.py:1274-1282`, `_day_bounds_utc`) alors que le planificateur travaille en `Europe/Paris` (`apps/api/app/main.py:93`). En heure d'été, la « journée » régularisée court de 02 h 00 à 01 h 59 locales. | Borner avec `ZoneInfo("Europe/Paris")` puis convertir, comme le font déjà `jobs.py:585-591` et `:620-625`. | Test sur une date d'été et une date d'hiver : les bornes correspondent à 00 h 00 → 23 h 59 min 59 s **locales**. | S |
| **m-6** | Anonymisation RGPD invisible de l'audit : `apps/api/app/services/rgpd.py:279-283` fait un `update()` Core en masse, qui ne traverse pas les listeners ORM (`services/audit.py:171-180`). | Écrire un `AuditLog action="rgpd.anonymize"` explicite par transaction touchée, ou passer par l'ORM. | Une demande de suppression client laisse une trace nominative par écriture fiscale touchée. | S |
| **m-7** | Sauvegardes purgées à 30 jours par défaut (`apps/api/app/models/database_backup.py:51`) et stockées sur le **même volume** que l'application (`BACKUP_DIR=data/backups` sur `vintiz_data`, `docker/docker-compose.prod.yml:77-79`). Aucune copie hors site. | Porter la rétention à la durée légale pour les dumps de fin de mois ; automatiser une copie hors site (au minimum les archives de clôture annuelle) avec vérification du SHA-256 après transfert. | Un dump de fin de mois de plus de 30 jours existe encore ; une archive annuelle est présente hors site et son SHA-256 est vérifié ; procès-verbal de relecture joint. | M |

### 3.4 Écarts documentaires (D-1 à D-10)

Les dix pièces manquantes sont décrites, avec leur statut, dans
`docs/DOSSIER_CERTIFICATION_NF525.md` §5. Elles constituent l'essentiel du
lot 3 et sont **bloquantes pour le dépôt du dossier**, même une fois le code
irréprochable.

---

## 4. Séquencement en lots

### Lot 1 — Rendre l'inaltérabilité opposable *(écarts bloquants)*

**Contenu :** B-1 (reliquats a → d), B-2, B-3, B-4, B-5 (reliquats a, b*).
*\* B-5.b peut glisser en lot 2 s'il est traité avec M-3.*

**Ordre conseillé :** B-2 (rôles) → B-1.c (trigger `TRUNCATE`) → B-1.a/b →
B-4 (tests, exécutés sous le rôle dégradé) → B-3 (scellement rétroactif) →
B-5.a.

**Définition de « terminé » :**

- [ ] Aucun script du dépôt ne peut effacer une écriture fiscale ; le refus est
      prouvé par un test automatisé.
- [ ] L'identité utilisée par l'application ne peut ni `TRUNCATE`, ni `DELETE`,
      ni désactiver un trigger sur les cinq tables fiscales ; procès-verbal signé.
- [ ] Un job CI dédié, sur PostgreSQL, échoue si l'un des triggers est retiré.
- [ ] La période 03/06 → 15/07/2026 est scellée par une clôture `perpetual`
      dont le SHA-256 est archivé hors ligne et signé.
- [ ] Aucun canal d'émission de ticket ne rend une copie indiscernable de
      l'original ; les copies sont numérotées et tracées.
- [ ] `docs/CHANGELOG.md` et `docs/COMPLIANCE_NF525.md` reflètent l'état réel.

**Charge estimée : 4 × M + 1 × S ≈ 12 à 18 jours-personne.**

---

### Lot 2 — Fiabiliser le fonctionnement courant *(écarts majeurs)*

**Contenu :** M-1 à M-7.

**Ordre conseillé :** M-7 (une heure, effet immédiat) → M-2 (verrou de clôture)
→ M-3 (journal technique inaltérable, socle des autres) → M-6 (surveillance) →
M-4 + M-5 **groupés** (une seule montée de `FISCAL_SIGNATURE_VERSION` à 3) →
M-1 (TVA, le plus lourd, à isoler dans sa propre recette).

**Définition de « terminé » :**

- [ ] Aucune vente ne peut échapper à une clôture Z ; prouvé par un test de
      concurrence.
- [ ] Tout Z est verrouillé (PDF + SHA-256) sans intervention humaine.
- [ ] Le Z porte un cumul perpétuel et les montants de caisse, tous scellés et
      immuables.
- [ ] Le journal des événements techniques est chaîné, immuable, complet
      (démarrage, version, panne d'impression, échec de clôture, mode dégradé,
      contrôle d'intégrité) et versé aux archives.
- [ ] Une rupture de chaîne déclenche une alerte sous 24 heures.
- [ ] Une vente hors ligne porte sa date de saisie **et** sa date
      d'enregistrement, est marquée comme telle, et n'est jamais perdue
      silencieusement.
- [ ] La TVA est ventilée par taux, portée par la ligne de vente, et le ticket
      restitue les taux d'origine même après changement de configuration.
- [ ] La recette POS complète (11 scénarios, cf. dossier §4) est repassée et
      son procès-verbal signé.

**Charge estimée : 3 × L + 3 × M + 1 × S ≈ 25 à 35 jours-personne.**

---

### Lot 3 — Documenter et clore *(écarts mineurs + dossier)*

**Contenu :** m-1 à m-7, D-1 à D-10.

**Ordre conseillé :** m-1 à m-6 (une journée pour l'ensemble, à faire tôt car
m-1 et m-2 sont des écarts de **discours** visibles par un tiers) → m-7 → D-2
(avis juridique — à lancer **dès le début du lot 1**, délai externe) → D-1
(devis et calendrier organisme) → D-3 à D-10.

**Définition de « terminé » :**

- [ ] Plus aucune mention « conforme NF525 » nulle part hors documentation
      historique datée.
- [ ] `docs/COMPLIANCE_NF525.md` et `docs/CHANGELOG.md` sont à jour et le
      restent (contrôle automatisé).
- [ ] Les dix pièces D-1 à D-10 sont produites, datées et signées.
- [ ] Le dossier `docs/DOSSIER_CERTIFICATION_NF525.md` est complet, avec ses
      annexes, et la version candidate est figée par un tag Git dont le SHA de
      build correspond à celui exposé par `/api/health`.
- [ ] Décision de voie prise et documentée : certificat d'organisme (voie A) ou
      attestation individuelle (voie B).

**Charge estimée : 7 × S + 1 × M pour le code ≈ 5 à 8 jours-personne ; la
production documentaire (D-1 à D-10) représente 10 à 15 jours-personne
supplémentaires, plus les délais externes (avis juridique, audit).**

---

### Vue d'ensemble

| Lot | Contenu | Charge interne | Délai externe |
|---|---|---|---|
| 1 | 4 bloquants + reliquats | 12–18 j·p | — |
| 2 | 7 majeurs | 25–35 j·p | — |
| 3 | 7 mineurs + 10 pièces | 15–23 j·p | avis juridique (2–6 sem.), audit organisme (2–4 mois) |
| **Total** | | **≈ 52 à 76 jours-personne** | **≈ 4 à 7 mois calendaires** de bout en bout |

Le chemin critique n'est pas le code : c'est **l'avis juridique** (voie A ou B)
et, en voie A, le **délai d'instruction de l'organisme**. Les deux se lancent
en parallèle du lot 1.

---

## 5. Ce qui ne doit pas être fait pendant le plan

- **Ne pas exécuter `scripts/go_live_reset.py` en production**, même en cas de
  besoin apparent de « repartir propre ». La garde ajoutée le 29/08/2026 le
  refuse ; ne pas la contourner en modifiant `ENVIRONMENT`.
- **Ne pas faire tourner de rotation de `FISCAL_SIGNING_KEY`** avant traitement
  de B-3.e : `verify_chain_integrity` recalcule tout avec la clé courante, une
  rotation invaliderait en bloc l'historique vérifiable.
- **Ne pas restaurer une sauvegarde par-dessus une base en service** sans
  procès-verbal : la restauration réécrit des écritures scellées.
- **Ne pas employer la mention « conforme NF525 »** dans un e-mail, un devis, un
  ticket, le site ou une réponse à un tiers.
- **Ne pas déployer une évolution touchant le payload signé, les triggers, la
  numérotation, les clôtures, les remboursements ou l'archivage** sans passer
  par la procédure de §7.

---

## 6. Risque en exploitation pendant la mise en conformité

### 6.1 Nature du risque

Le logiciel est **en service et encaisse réellement** depuis le 03/06/2026. La
mise en conformité s'étale sur plusieurs mois. Un contrôle de l'administration
peut donc intervenir avant la fin du plan. Il faut distinguer deux choses :

| | |
|---|---|
| **Ce qui est sanctionnable aujourd'hui** | L'absence de **justificatif** (certificat ou attestation). L'amende de 7 500 € par logiciel sanctionne l'incapacité à produire l'un des deux, pas le résultat d'un audit technique. |
| **Ce qui est réparable** | L'assujetti dispose d'un délai de **60 jours** après la mise en demeure pour se mettre en conformité. Une amende renouvelée n'est due que si la situation n'est pas régularisée à l'issue de ce délai. |

### 6.2 Position à tenir en cas de contrôle avant la fin du plan

**Ne rien affirmer qui ne soit vérifiable.** Le pire scénario n'est pas
« logiciel imparfait en cours de correction », c'est « déclaration de conformité
contredite par le code ». Le dépôt est aujourd'hui honnête sur ce point
(`docs/COMPLIANCE_NF525.md` ne revendique pas la conformité) : **c'est un atout,
il faut le préserver.**

Les cinq éléments à présenter, dans cet ordre :

1. **Le statut, sans détour.** Le logiciel est en cours de mise en conformité ;
   il n'est ni certifié, ni couvert par une attestation à ce jour. La démarche
   est engagée, documentée et datée.
2. **Le présent plan**, avec ses lots, ses critères d'acceptation et son
   avancement réel à la date du contrôle. Un plan daté, chiffré et suivi
   démontre la bonne foi bien mieux qu'un discours.
3. **L'audit du 29/08/2026**, produit spontanément. Un assujetti qui a fait
   auditer son propre logiciel, en a publié les écarts et les corrige dans un
   ordre motivé n'est pas dans la situation que le texte vise (la dissimulation
   de recettes).
4. **Les preuves techniques déjà disponibles** — c'est le cœur de la
   démonstration, et il est solide :
   - la chaîne de signature HMAC-SHA256 v2 se vérifie de bout en bout
     (`GET /api/admin/fiscal-closures/integrity`) ;
   - les clôtures Z, mensuelles et annuelles existent, sont scellées, chaînées
     et archivées avec leur SHA-256 ;
   - le FEC est réellement produit, aux 18 colonnes DGFiP, avec équilibre
     débit/crédit imposé (`GET /api/accounting/exports/{id}/fec`) ;
   - aucune correction ne se fait par réécriture : uniquement par transaction
     inverse liée et signée ;
   - aucune purge fiscale planifiée n'existe.
5. **Les réserves, énoncées avant qu'on ne les découvre** : la période
   03/06 → 15/07/2026 relève d'un régime de preuve dégradé (signature v1),
   scellée a posteriori par une clôture `perpetual` dont le SHA-256 est archivé
   hors ligne ; les droits de base de données sont en cours de restriction ;
   la ventilation TVA est aujourd'hui monotaux à 20 %, ce qui correspond à
   l'intégralité des ventes réalisées mais doit être généralisé.

### 6.3 Mesures compensatoires à mettre en place immédiatement

En attendant les lots, ces mesures **de procédure** réduisent le risque à coût
quasi nul et se déclarent au contrôleur :

| Mesure | Détail | Quand |
|---|---|---|
| Registre des accès `psql` production | Liste nominative des personnes disposant d'un accès direct à la base ; toute session est consignée (date, motif, requêtes). Compense B-2 tant qu'il n'est pas livré. | Immédiat |
| Vérification d'intégrité hebdomadaire manuelle | Appel de `GET /api/admin/fiscal-closures/integrity`, résultat imprimé, daté et classé. Compense M-6. | Immédiat |
| Verrouillage manuel des Z | Appel explicite du verrouillage après chaque fermeture de caisse, tant que M-7 n'est pas livré. | Immédiat |
| Archivage hors site mensuel | Copie manuelle de l'archive de clôture mensuelle sur un support externe, SHA-256 vérifié et consigné. Compense m-7 et A-6. | Chaque début de mois |
| Gel du script de reset | Le script est déjà refusé en production ; consigner par écrit qu'aucune exécution n'a eu lieu depuis le 03/06/2026, et le vérifier au journal. | Immédiat |
| Journal papier des réimpressions | Tant que B-5.b n'est pas livré, consigner les demandes de duplicata au cahier de caisse (date, ticket, motif). | Immédiat |

### 6.4 Ce qu'il ne faut surtout pas faire en cas de contrôle

- Ne pas produire d'attestation individuelle signée « pour faire bonne mesure ».
  Une attestation inexacte engage la responsabilité du signataire et transforme
  une non-conformité réparable en fausse déclaration.
- Ne pas corriger des données de caisse « pour qu'elles soient présentables ».
  Toute écriture est chaînée : une retouche est détectable et bien plus grave
  que l'écart qu'elle prétend masquer.
- Ne pas s'appuyer sur le fait que le logiciel est « développé en interne » pour
  affirmer qu'il échappe à l'obligation : l'obligation porte sur l'assujetti qui
  encaisse, pas sur le statut de l'auteur.

---

## 7. Gouvernance du plan

| Question | Réponse retenue |
|---|---|
| Qui décide qu'un changement est « fiscal » ? | Toute modification touchant le payload signé, les triggers, la numérotation, les clôtures, les remboursements, l'archivage ou les scripts d'exploitation qui les touchent. La liste fait foi ; en cas de doute, le changement est réputé fiscal. |
| Qui valide un changement fiscal ? | Revue à deux, dont le responsable du plan. Entrée obligatoire au `CHANGELOG` avec la mention « fiscale », et bump de `APP_VERSION`. |
| Comment l'avancement est-il suivi ? | Le tableau de bord du §2.2 est mis à jour à chaque livraison, avec la date. Chaque case cochée d'un « terminé » de lot renvoie à une preuve (test CI, procès-verbal, document). |
| Que se passe-t-il si un écart nouveau apparaît ? | Il est ajouté au tableau §2.2 avec sa gravité et son lot, jamais traité hors plan. |
| Quand le plan est-il clos ? | À la remise du certificat d'organisme (voie A) ou à la signature de l'attestation individuelle appuyée sur un dossier complet (voie B) — les lots 1 et 2 étant clos dans les deux cas. |

---

## Annexe — Correspondance audit → plan

| Réf. audit | Exigences de la matrice concernées | Réf. plan |
|---|---|---|
| B-1 | I-9, C-9, T-14 | §3.1 B-1 |
| B-2 | I-5, I-8 | §3.1 B-2 |
| B-3 | I-1, I-4 | §3.1 B-3 |
| B-4 | T-11, T-12 | §3.1 B-4 |
| B-5 | T-2, T-10 | §3.1 B-5 |
| M-1 | T-9, T-10 | §3.2 M-1 |
| M-2 | S-9, C-1 | §3.2 M-2 |
| M-3 | T-1 | §3.2 M-3 |
| M-4 | T-4, S-10 | §3.2 M-4 |
| M-5 | C-3, T-8 | §3.2 M-5 |
| M-6 | T-6, T-13 | §3.2 M-6 |
| M-7 | T-7 | §3.2 M-7 |
| m-1 | T-14 | §3.3 |
| m-2, m-3 | T-3, T-14 | §3.3 |
| m-4 | S-3 | §3.3 |
| m-5 | S-11 | §3.3 |
| m-6 | C-10 | §3.3 |
| m-7 | C-11, A-6 | §3.3 |
| D-1…D-10 | pièces du dossier | `DOSSIER_CERTIFICATION_NF525.md` §5 |

Exigences restées **non couvertes par un écart** parce qu'elles sont déjà
conformes : I-1 (v2), I-2, I-3, I-6, I-7, I-11, I-12, S-1, S-2, S-4, S-6, S-7,
S-8, C-1, C-2, C-4, C-5, C-6, C-7, C-8, C-12, A-1, A-2, A-3, A-4, T-5.
Restent à traiter hors plan technique : **S-5** (identité du caissier absente du
ticket imprimé — correction triviale à intégrer au lot 2 avec M-1, même
fichier), **A-5** et **A-6** (procédures d'archivage à arbitrer avec le
certificateur), **A-7** (positionner clairement le FEC comme export DGFiP et
l'export `vintiz-nf525-export` comme preuve de chaîne, pas comme format normé).
