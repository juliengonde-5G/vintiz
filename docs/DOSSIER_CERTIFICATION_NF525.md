# Dossier de certification fiscale — Vintiz POS

> **Document de travail — squelette du dossier à présenter.**
> Ce document n'est ni un certificat, ni une attestation. Il rassemble les
> éléments qu'un organisme accrédité (voie A) ou qu'un signataire d'attestation
> individuelle (voie B) doit examiner. Les mécanismes décrits ci-dessous sont
> **qualifiés selon l'audit du 29/08/2026** : ce qui est en cours de correction
> est signalé comme tel et renvoie à `docs/PLAN_CONFORMITE_NF525.md`.

| | |
|---|---|
| Date de rédaction | 29 août 2026 |
| Version décrite | `APP_VERSION = 1.2.0` — `apps/api/app/version.py:3` |
| Révision de schéma | `0076` (branche de travail) / `0075` (`main`) — `apps/api/app/version.py:4` |
| Version de signature fiscale | `2` — `apps/api/app/version.py:5` |
| Statut | **Candidat — non certifié.** Lots 1 et 2 du plan de conformité non clos. |
| Plan de correction | `docs/PLAN_CONFORMITE_NF525.md` |
| Auto-déclaration antérieure | `docs/COMPLIANCE_NF525.md` (à réaligner — écart m-2) |

---

## 1. Présentation du logiciel

### 1.1 Identification

| Rubrique | Valeur |
|---|---|
| Nom du logiciel | **Vintiz POS** (module de caisse de la plateforme Vintiz) |
| Éditeur | *(raison sociale de l'exploitant — à compléter)* |
| Exploitant | Boutique Vintiz, Vernon (Eure), Normandie |
| Particularité | **L'éditeur et l'exploitant sont la même entité.** Le logiciel est développé en interne pour l'usage propre de la boutique. Ce point conditionne la voie de preuve admissible (§2.3). |
| Mise en service | 3 juin 2026, 10 h 00 |
| Version en service | 1.1.5 |
| Vérification de la version en service | `GET /api/health` renvoie `version`, `database_revision`, `fiscal_signature_version`, `build_sha`, `build_date` — `apps/api/app/main.py:245-255` |
| Refus de démarrage sur schéma incohérent | L'API refuse de démarrer si `alembic_version` ≠ `EXPECTED_DB_REVISION` — `apps/api/app/main.py:66-85` |

### 1.2 Architecture

| Couche | Technologie | Rôle fiscal |
|---|---|---|
| API | FastAPI (Python 3.11), SQLAlchemy asynchrone — `apps/api` | Porte **l'intégralité** de la logique fiscale : signature, chaînage, numérotation, clôtures, archives, exports |
| Base de données | PostgreSQL 16 (image `pgvector/pgvector:pg16`) | Porte les triggers d'inaltérabilité (migration `0072`) |
| Interface de caisse | Next.js 15 — `apps/web`, route `/pos` | Interface tactile uniquement. **Ne calcule ni ne signe aucune donnée fiscale** ; tout est recalculé et validé côté serveur |
| Site public | Next.js 15 — `apps/site` | Hors périmètre fiscal |
| Reverse-proxy | Caddy 2 (HTTPS) | Hors périmètre |
| Ordonnanceur | APScheduler intégré à l'API — `apps/api/app/jobs.py` | Porte les clôtures automatiques (journalière de garde, mensuelle, annuelle) |

### 1.3 Matériel d'encaissement

| Équipement | Référence | Rôle |
|---|---|---|
| Terminal de caisse | Tablette Android (Chrome) | Interface `/pos` |
| Imprimante ticket | MUNBYN 047P, ESC/POS 80 mm | Réseau (port 9100) ou USB-OTG via WebUSB |
| Tiroir-caisse | Safescan SD-4141, RJ-12 | Ouvert par impulsion `ESC p m` de l'imprimante |
| Terminal de paiement | SumUp Solo (Wi-Fi) | Encaissement CB, rapproché côté serveur |
| Douchette | Inateck BCST-35 / 160B, USB HID | Lecture de code-barres |
| Imprimante étiquettes | Zebra ZD421d, ZPL II | Hors périmètre fiscal |

### 1.4 Périmètre fiscal

**Dans le périmètre :**

- création des ventes, paiements et remboursements — `/api/pos` ;
- encaissement CB SumUp et rapprochement des tentatives ;
- tickets, factures, lignes et moyens de paiement ;
- tiroirs de caisse et clôtures Z ;
- clôtures mensuelles et annuelles, archives et manifests ;
- exports : FEC (`/api/accounting`) et export de chaîne (`/api/admin/fiscal-export`) ;
- signature et chaînage — `apps/api/app/services/fiscal.py`, `fiscal_closure.py`,
  `fiscal_export.py`, `accounting_service.py` ;
- triggers de la migration `apps/api/alembic/versions/0072_security_loyalty_nf525.py` ;
- clé `FISCAL_SIGNING_KEY` et sa procédure de conservation ;
- scripts d'exploitation touchant ces données — `scripts/deploy.sh`,
  `scripts/go_live_reset.py`, `scripts/backup.sh`.

**Hors périmètre :** CRM, inventaire, moteur de recommandation, IA, site
vitrine, marketing — **sauf** lorsqu'ils figent une donnée dans une vente
(libellé d'article, remise, coupon, taux de TVA du produit, moyen de paiement).
Ces données, une fois recopiées sur la ligne de vente, sont scellées avec elle.

---

## 2. Cadre réglementaire et voie de preuve

### 2.1 L'obligation

Article **286-I-3° bis du CGI** : le logiciel de caisse doit satisfaire aux
conditions d'**inaltérabilité, sécurisation, conservation et archivage** des
données. Commentaire administratif applicable : **BOI-TVA-DECLA-30-10-30**
(version du 25 mars 2026).

### 2.2 Les deux modes de preuve

| Voie | Pièce produite | Référence |
|---|---|---|
| **A** | Certificat délivré par un organisme accrédité (référentiel **NF525** d'Infocert/AFNOR Certification, ou référentiel du **LNE**) | Certificat nominatif, par version |
| **B** | Attestation individuelle du représentant légal de l'**éditeur** | Modèle **BOI-LETTRE-000242** (§6 du présent document) |

### 2.3 Position de Vintiz

Vintiz développe le logiciel **pour son propre usage**. La doctrine réserve
l'attestation individuelle à celui qui exerce une **activité réelle d'édition**
de logiciels ou de systèmes de caisse ; à défaut, le logiciel développé en
interne par l'assujetti doit être **certifié par un organisme accrédité**.

En conséquence :

- **la voie A (certification externe) est la position par défaut retenue** ;
- **la voie B n'est ouverte que si un avis juridique écrit** établit que
  l'exception d'activité réelle d'édition est applicable (pièce **D-2**) ;
- **le contenu technique du présent dossier est le même dans les deux cas**.

---

## 3. Mécanismes par pilier

Légende de la colonne « Statut » :
**Conforme** = vérifié par l'audit du 29/08/2026 · **En cours** = écart identifié,
correction planifiée (référence du plan) · **À arbitrer** = point à trancher avec
le certificateur.

### 3.1 Pilier Inaltérabilité

#### Ce qui est en place

**Signature de chaque écriture.** Chaque vente et chaque remboursement reçoit une
signature **HMAC-SHA256** calculée par `FiscalService.sign_transaction`
(`apps/api/app/services/fiscal.py:40-50`). Le payload
(`fiscal.py:94-177`) est canonicalisé strictement — JSON trié, séparateurs sans
espace, montants normalisés en `Decimal` quantifié, dates ISO en UTC à la
microseconde, ordre des lignes et paiements déterministe — et couvre :

- l'en-tête : numéro, type, date, opérateur (`user_id`), caissier
  (`cashier_id`), référence d'idempotence, vente d'origine en cas de
  remboursement, indicateur de régularisation ;
- les totaux HT, TVA, TTC, les données de facture et le modèle de ticket ;
- **chaque ligne** : article, libellé figé, quantité, prix, remise, total,
  caractère promotionnel, taux de TVA ;
- **chaque paiement** : méthode, montant appliqué, montant remis en espèces,
  références SumUp masquées ;
- le **hash précédent** et la version de signature.

**Chaînage.** La racine de chaîne est la valeur `"0"`, renvoyée lorsqu'aucune
transaction signée n'existe (`fiscal.py:63`) ; la vérification repart de la même
valeur (`fiscal.py:190`). Chaque signature intègre le hash de la précédente.

**Clé de signature distincte.** `FISCAL_SIGNING_KEY` est indépendante de la clé
JWT applicative. En production, l'API **refuse de démarrer** sans clé stable
d'au moins 32 caractères (`apps/api/app/core/config.py:145-158`).

**Verrous en base.** La migration `0072`
(`apps/api/alembic/versions/0072_security_loyalty_nf525.py`) installe cinq
fonctions et leurs triggers :

| Trigger | Table protégée | Message d'erreur | Ligne |
|---|---|---|---|
| `trg_protect_signed_transaction` | `transactions` | `NF525: suppression transaction signee interdite` / `NF525: modification transaction signee interdite` | `:82-124` |
| `trg_protect_transaction_items`, `trg_protect_payments` | `transaction_items`, `payments` | `NF525: lignes/paiements d une transaction signee immuables` | `:126-150` |
| `trg_protect_z_report` | `z_reports` | `NF525: suppression Z interdite` / `NF525: modification donnees scellees Z interdite` | `:152-189` |
| `trg_protect_closed_drawer_period` | `cash_drawers` | `NF525: periode tiroir cloturee immuable` | `:191-209` |
| `trg_protect_fiscal_closure` | `fiscal_closures` | `NF525: cloture fiscale immuable` | `:211-223` |

La migration **refuse son `downgrade`** : `downgrade()` lève une `RuntimeError`
et renvoie vers une restauration de sauvegarde (`0072_…py:232-240`).

**Corrections par opération inverse uniquement.** Un remboursement est une
**nouvelle** transaction de type `refund`, numérotée, liée par
`original_transaction_id` et `original_transaction_item_id`
(`apps/api/app/services/refund.py:227-257`), signée à son tour. Les quotas de
remboursement partiel cumulés sont contrôlés (`refund.py:79-120`). Aucun chemin
d'annulation destructive n'est employé.

**Duplicata de ticket.** Depuis le **29/08/2026**, toute émission de ticket est
comptée côté serveur et toute émission postérieure à la première porte un
bandeau `* DUPLICATA n.X *` : compteur `_count_receipt_prints`
(`apps/api/app/api/pos/router.py`), rendu par
`escpos_service.build_receipt(..., duplicata_number)`
(`apps/api/app/services/escpos_service.py`), trace `AuditLog` `receipt.reprint`
(chemin réseau) et `receipt.escpos` (chemin WebUSB tablette) avec `copy_number`
et `duplicata`.

#### Qualification

| Exigence | Statut | Renvoi |
|---|---|---|
| Signature de chaque ticket incluant la signature précédente | **Conforme** (signature v2) | — |
| Genesis connu et stable | **Conforme** | — |
| Clé de signature distincte, obligatoire en production | **Conforme** | — |
| Détection d'une altération des lignes et paiements | **En cours** — complète pour la v2 ; **nulle** pour les écritures v1 du 03/06 au 15/07/2026 (empreinte SHA-256 **non clefée** ne couvrant ni les lignes ni les paiements, `fiscal.py:204-211`) | Plan **B-3** |
| Interdiction de modification d'une vente signée au niveau base | **En cours** — le trigger ne s'arme que si `hash_chain <> ''` (une ligne jamais signée reste modifiable) et reste contournable par le rôle propriétaire | Plan **B-2** |
| Immuabilité des lignes et paiements d'une vente signée | **Conforme** | — |
| Immuabilité des Z et des clôtures périodiques | **Conforme** | — |
| Inaltérabilité opposable à l'identité utilisée par l'application | **Non conforme** — le compte applicatif est superutilisateur et propriétaire (`docker/docker-compose.prod.yml:28-31`) | Plan **B-2** |
| Absence de suppression physique d'écriture fiscale dans le code | **En cours** — `scripts/go_live_reset.py` refuse désormais le mode réel en production (correctif du 29/08/2026) ; les tables fiscales restent dans sa liste et aucun trigger `BEFORE TRUNCATE` n'existe | Plan **B-1** |
| Corrections par opération inverse tracée | **Conforme** | — |
| Migration fiscale non réversible en place | **Conforme** | — |
| Réimpression identifiée comme duplicata numéroté | **Conforme sur les deux chemins d'impression** (correctif du 29/08/2026) ; **en cours** sur le rendu texte et l'envoi e-mail/SMS, et le compteur repose sur une table encore mutable | Plan **B-5.a**, **B-5.b** |

**Réserve à porter au dossier :** une donnée reste modifiable après signature —
`POST /api/pos/transactions/{id}/client` réécrit `client_id` sur une vente
signée (`apps/api/app/api/pos/router.py:951-990`). Ce champ n'est ni signé ni
protégé par le trigger. C'est un choix documenté (rattachement d'un ticket à une
cliente identifiée après coup) ; la mutation **est** journalisée
(`apps/api/app/services/audit.py:43`). À déclarer explicitement au certificateur
plutôt qu'à laisser découvrir.

---

### 3.2 Pilier Sécurisation

#### Ce qui est en place

**Numérotation continue sans trou.** Le numéro de transaction est alloué en
`MAX+1` **sous verrou consultatif transactionnel** `pg_advisory_xact_lock(5252026)`
(`apps/api/app/services/pos.py:86-90`, `:359-364`). Ce choix — délibéré et
commenté — évite le trou qu'une séquence SQL laisserait après un rollback.
`transaction_number` porte une contrainte d'unicité
(`apps/api/app/models/pos.py:49-51`). Même dispositif pour les remboursements
(`refund.py:156-171`, `:218-222`).

**Aucun numéro consommé en cas d'échec de paiement.** `get_db` effectue un
`rollback` sur exception (`apps/api/app/core/database.py:28-37`) ; le
remboursement CB lève une erreur **avant** signature si le prestataire n'a pas
confirmé (`api/pos/router.py:2849-2864`).

**Identification de l'opérateur.** `cashier_id` est forcé à l'utilisateur
authentifié à défaut de code caissier explicite, contrôlé actif
(`api/pos/router.py:395-427`), et **inclus dans le payload signé**
(`services/fiscal.py:119-120`). Même chose pour `user_id`.

**Encaissement CB adossé au prestataire.** Rien de ce que le navigateur affirme
n'est retenu (`api/pos/router.py:165-283`) : relecture serveur du checkout
SumUp, rapprochement de la tentative, du checkout, du montant et de la référence
d'idempotence, statut `PAID` exigé, tous les champs SumUp du payload client
écrasés par la réponse du prestataire, clé de test refusée en production
(`:196-200`).

**Plafond légal des espèces.** Blocage par défaut au-delà du plafond du
CMF L.112-6, dérogation réservée au manager, motif d'au moins dix caractères,
trace `AuditLog action="cash_cap_override"` (`api/pos/router.py:324-393`).

**Contrôle de cohérence des règlements.** Refus en cas de sous-paiement, de
non-espèces dépassant le total, ou de dépassement non adossé à des espèces
(rendu monnaie) — `services/pos.py:340-357`. Le montant remis (`tendered_amount`)
est distinct du montant fiscalement encaissé (`:441-453`).

**Idempotence du rejeu.** Double contrôle — hors verrou puis **re-contrôle sous
le verrou** — plus un court-circuit au niveau du routeur qui évite de rappeler
le prestataire (`services/pos.py:70-102`, `api/pos/router.py:296-314`,
`:2777-2792`). Contrainte d'unicité sur `client_uuid`
(`apps/api/app/models/pos.py:78-80`).

#### Qualification

| Exigence | Statut | Renvoi |
|---|---|---|
| Numérotation séquentielle ininterrompue | **Conforme** | — |
| Pas de numéro consommé lors d'un échec de paiement | **Conforme** | — |
| Un seul mécanisme de numérotation | **En cours** — la migration `0025` a posé un `DEFAULT nextval()` jamais utilisé, séquence dormante | Plan **m-4** |
| Identification de l'opérateur en base | **Conforme** | — |
| Identification de l'opérateur sur le ticket imprimé | **Non conforme** — ni le caissier ni l'opérateur n'apparaissent sur le ticket (`services/receipt.py:104-152`, `services/escpos_service.py:340-380`) | Plan, annexe (S-5) |
| Encaissement CB adossé au prestataire | **Conforme** | — |
| Plafond légal des espèces | **Conforme** | — |
| Contrôle de cohérence des règlements | **Conforme** | — |
| Sérialisation de la clôture Z vis-à-vis des ventes | **Non conforme** — `close_drawer` ne prend aucun verrou et le Z en prend un différent de celui des ventes ; une vente peut échapper définitivement à toute clôture | Plan **M-2** |
| Horodatage fiable | **En cours** — `created_at` = horloge serveur (`models/base.py:15-19`), signé et protégé ; mais aucune source de temps sûre et l'horodatage d'une vente hors ligne est celui du rejeu | Plan **M-4** |
| Frontière des journées de caisse | **En cours** — journées bornées en UTC alors que la boutique travaille en `Europe/Paris` | Plan **m-5** |
| Idempotence du rejeu (anti-double encaissement) | **Conforme** | — |

---

### 3.3 Pilier Conservation

#### Ce qui est en place

**Clôture journalière (Z).** Produite à la fermeture du tiroir
(`services/fiscal.py:227-383`, `api/pos/router.py:1108-1118`) : totaux ventes /
remboursements / net, comptage, bornes de numérotation, dernier hash de
transaction, ventilation par moyen de paiement, chaînage `previous_hash` et HMAC.

**Garde de caisse oubliée.** Cron à 23 h 59 `Europe/Paris`
(`apps/api/app/jobs.py:555-572`, `:647-652`) : le tiroir est fermé à l'instant
présent, `closing_amount=None` (comptage non rejoué, signalé dans
`closing_note`), le Z est scellé normalement, verrou pris avant lecture
(`services/fiscal.py:581-648`).

**Clôture mensuelle.** Cron le 1er du mois à 00 h 15 `Europe/Paris` sur le mois
civil précédent (`jobs.py:575-607`, `:653-658`), idempotente par contrainte
d'unicité de période (`services/fiscal_closure.py:59-69`).

**Clôture annuelle.** Cron le 1er janvier à 00 h 30 `Europe/Paris` sur l'année
précédente (`jobs.py:610-640`, `:659-664`).

**Grand total et total perpétuel.** `grand_total_period` et `total_perpetual`
(ventes, remboursements, net, nombre de transactions depuis l'origine) sont
intégrés au manifest signé des clôtures périodiques
(`services/fiscal_closure.py:132-193`).

**Chaînage des clôtures.** `sequence_number` unique, `previous_hash`, HMAC du
manifest, contrôle de chaîne et revérification du SHA-256 de l'archive
(`fiscal_closure.py:158-245`).

**Refus de clôturer sur chaîne rompue.** Erreur `409 fiscal_chain_invalid` si la
chaîne des transactions ou des Z est cassée ; erreur également si un tiroir est
resté ouvert (`fiscal_closure.py:71-93`).

**Aucune purge fiscale.** Aucun cron ne purge `transactions`, `payments`,
`z_reports` ou `fiscal_closures`. La suppression RGPD **anonymise**
(`client_id → NULL`) au lieu de supprimer (`apps/api/app/services/rgpd.py:269-283`) :
l'obligation fiscale de conservation prime sur l'effacement.

**Protection des produits référencés.** La suppression définitive d'un produit
est refusée dès qu'il apparaît dans une ligne de vente
(`apps/api/app/api/inventory/router.py:1187-1202`) ; le libellé est de toute
façon figé sur la ligne (`models/pos.py:158`).

#### Qualification

| Exigence | Statut | Renvoi |
|---|---|---|
| Clôture journalière (Z) | **Conforme** | — |
| Garde de clôture pour caisse oubliée | **Conforme** | — |
| Cumul perpétuel sur la clôture journalière | **Non conforme** — le payload du Z ne comporte aucun grand total perpétuel (`services/fiscal.py:341-358`) ; il n'existe qu'au niveau périodique | Plan **M-5** |
| Clôture mensuelle | **Conforme** | — |
| Clôture annuelle | **Conforme** | — |
| Grand total de période et total perpétuel sur les clôtures | **Conforme** | — |
| Chaînage et signature des clôtures | **Conforme** | — |
| Refus de clôturer sur chaîne rompue | **Conforme** | — |
| Absence de purge des données fiscales | **Conforme** — sous réserve de l'écart B-1 (script d'effacement) | Plan **B-1** |
| Journalisation de l'anonymisation RGPD | **En cours** — l'anonymisation passe par un `update()` en masse invisible des écouteurs d'audit | Plan **m-6** |
| Conservation en ligne 6 ans | **En cours** — les écritures ne sont jamais purgées, mais les **sauvegardes** sont purgées à 30 jours et stockées sur le même volume que l'application ; aucune copie hors site automatisée | Plan **m-7** |
| Protection des suppressions de produits référencés | **Conforme** | — |
| Robustesse des clôtures automatiques | **En cours** — les trois crons fiscaux avalent leurs exceptions sans notifier personne | Plan **M-6** |
| Contrôle d'intégrité automatisé | **En cours** — contrôle à la demande et à chaque clôture périodique, mais aucune vérification quotidienne ni alerte | Plan **M-6** |
| Verrouillage intangible du Z (art. 88 CGI) | **En cours** — mécanisme complet et idempotent (`services/fiscal.py:766-828`) mais **jamais appelé automatiquement** | Plan **M-7** |
| Immuabilité des montants de caisse après Z | **En cours** — le trigger ne protège que `opened_at` et `closed_at` | Plan **M-5** |

---

### 3.4 Pilier Archivage

#### Ce qui est en place

**Archive figée par clôture, en format ouvert.** Chaque clôture produit un
snapshot JSON canonique compressé gzip avec `mtime=0` — donc **reproductible
bit à bit** — accompagné d'une notice en français, contenant les transactions,
lignes, paiements et Z de la période (`services/fiscal_closure.py:116-127`,
`services/fiscal_export.py:46-121`).

**Scellement.** SHA-256 de l'archive gzip **et** manifest HMAC chaîné
(`fiscal_closure.py:125-127`, `:191-206`). `verify_chain` recontrôle les deux
(`:232-243`).

**Traçabilité de version.** `software_version = APP_VERSION` est figé dans le
snapshot **et** dans le manifest signé (`fiscal_closure.py:19-21`, `:120`, `:173`).

**Restitution.** Téléchargement réservé au manager, avec les en-têtes
`X-Archive-SHA256` et `X-Closure-Hash` exposés pour contrôle hors ligne
(`apps/api/app/api/admin/fiscal_closures.py:73-93`).

**Export comptable FEC.** Le FEC est réellement produit, aux **18 colonnes
DGFiP**, généré par clôture et stocké (`services/accounting_service.py:53-61`,
`:641-678` ; `apps/api/app/models/accounting.py:114-119`). L'**équilibre
débit/crédit est imposé** : le service lève `FECImbalanceError` plutôt que
d'écrire un FEC déséquilibré (`accounting_service.py:583-637`).

#### Qualification

| Exigence | Statut | Renvoi |
|---|---|---|
| Archive figée par clôture, en format ouvert | **Conforme** | — |
| Scellement de l'archive | **Conforme** | — |
| Traçabilité de version dans l'archive | **Conforme** | — |
| Téléchargement et restitution de l'archive | **Conforme** | — |
| Purge d'archive tracée | **À arbitrer** — aucune purge d'archive n'existe, donc rien à tracer ; aucune procédure de purge maîtrisée n'est décrite non plus | Certificateur |
| Archivage sur support externe | **À arbitrer / en cours** — aucun mécanisme applicatif ; la duplication externe est renvoyée à l'exploitant, sans procès-verbal de relecture au dépôt | Plan **m-7**, pièce **D-6** |
| Export DGFiP / FEC | **En cours de qualification** — le FEC est conforme aux 18 colonnes et équilibré ; en revanche `/api/admin/fiscal-export` produit un format **propriétaire** (`vintiz-nf525-export`) qui doit être présenté comme **preuve de chaîne**, non comme export normé | Plan, annexe (A-7) |

---

### 3.5 Journal des événements

**État actuel.** `audit_logs` (`apps/api/app/models/audit.py:11-22`,
`apps/api/app/services/audit.py:42-61`) journalise les mutations d'entités
métier : transactions, rapports Z, tiroirs, produits, utilisateurs, clientes,
comptes de fidélité, ainsi que les dérogations au plafond espèces et, depuis le
29/08/2026, les émissions de ticket.

**Écart à déclarer sans détour :** la table est **ordinaire** — aucun hash,
aucun chaînage, aucun trigger d'immuabilité, aucune signature. Elle est
librement modifiable et supprimable. Son contenu ne couvre pas non plus les
événements techniques attendus (démarrage/arrêt du système, changement de
version, panne d'impression, passage en mode dégradé, échec de clôture,
changement d'heure). → Plan **M-3**.

**Conséquence à assumer :** tant que M-3 n'est pas livré, le compteur de
duplicata (§3.1) s'appuie sur une table mutable. Le mécanisme fonctionne, sa
valeur probante est limitée. → Plan **B-5.b**.

---

### 3.6 Mode dégradé (hors ligne)

**Écart à déclarer.** La caisse dispose d'une file hors ligne
(`apps/web/src/lib/offline-queue.ts`) présentant trois défauts cumulés : la file
ne transporte pas l'horodatage de la vente (au rejeu, la date est celle du
rejeu, `:76-93`) ; une entrée est **définitivement supprimée** sur toute réponse
4xx (`:159-169`) ; rien ne marque une transaction comme saisie en mode dégradé.
→ Plan **M-4**.

À la date de rédaction, aucune vente hors ligne perdue n'a été constatée. Le
registre d'exploitation (pièce **D-7**) doit consigner tout épisode hors ligne
jusqu'à la livraison de M-4.

---

## 4. Mode opératoire de recette

Cette section décrit les tests qu'un auditeur peut **rejouer lui-même**, sur un
environnement de recette portant les mêmes migrations que la production. Chaque
test indique le résultat attendu **à la date de rédaction** — certains attendus
changeront à la livraison des lots, la colonne le précise.

### 4.1 Préparation

```bash
# Environnement de recette, base migrée au head
cd apps/api && python -m alembic upgrade head
# Vérifier la version en service
curl -s https://<hôte>/api/health
# → {"version":"1.1.5","database_revision":"0076","fiscal_signature_version":2,"build_sha":"…"}
```

Jeu d'essai minimal à saisir avant les tests : une vente espèces avec rendu
monnaie, une vente CB, une vente mixte, une vente avec remise, une vente avec
coupon, une facture B2B, un remboursement partiel puis total, une fermeture de
caisse avec Z, une clôture mensuelle.

### 4.2 Test 1 — Refus d'altération d'une vente signée

Se connecter en `psql` avec **l'identité utilisée par l'application** (le point
est essentiel : c'est ce que le certificateur doit tester).

| # | Commande | Attendu aujourd'hui | Attendu après lot 1 |
|---|---|---|---|
| 1.1 | `UPDATE transactions SET total_ttc = total_ttc + 10 WHERE id = '<uuid signé>';` | `NF525: modification transaction signee interdite` | idem |
| 1.2 | `DELETE FROM transactions WHERE id = '<uuid signé>';` | `NF525: suppression transaction signee interdite` | idem |
| 1.3 | `UPDATE transaction_items SET quantity = 99 WHERE transaction_id = '<uuid signé>';` | `NF525: lignes/paiements d une transaction signee immuables` | idem |
| 1.4 | `INSERT INTO transaction_items (…) VALUES (… '<uuid signé>' …);` | même refus | idem |
| 1.5 | `DELETE FROM payments WHERE transaction_id = '<uuid signé>';` | même refus | idem |
| 1.6 | `UPDATE z_reports SET total_sales = 0 WHERE id = '<uuid>';` | `NF525: modification donnees scellees Z interdite` | idem |
| 1.7 | `DELETE FROM z_reports WHERE id = '<uuid>';` | `NF525: suppression Z interdite` | idem |
| 1.8 | `UPDATE fiscal_closures SET closure_hash = 'x' WHERE id = '<uuid>';` | `NF525: cloture fiscale immuable` | idem |
| 1.9 | `DELETE FROM fiscal_closures WHERE id = '<uuid>';` | même refus | idem |
| 1.10 | `UPDATE cash_drawers SET opened_at = now() WHERE id = '<tiroir clôturé>';` | `NF525: periode tiroir cloturee immuable` | idem |
| 1.11 | `UPDATE cash_drawers SET closing_amount = 0 WHERE id = '<tiroir clôturé>';` | ⚠️ **accepté** — écart M-5 | refusé |
| 1.12 | `ALTER TABLE transactions DISABLE TRIGGER ALL;` | ⚠️ **accepté** — écart B-2 (rôle superutilisateur) | `must be owner of table` |
| 1.13 | `SET session_replication_role = 'replica';` | ⚠️ **accepté** — écart B-2 | `permission denied to set parameter` |
| 1.14 | `TRUNCATE TABLE transactions;` | ⚠️ **accepté** — écart B-1.c | refusé par trigger `BEFORE TRUNCATE` |

Les lignes marquées ⚠️ sont les écarts que le plan corrige au lot 1 ; elles
doivent être **montrées** à l'auditeur, pas contournées.

### 4.3 Test 2 — Vérification de chaîne

```http
GET /api/admin/fiscal-closures/integrity        (manager)
```

Attendu : chaînes des transactions, des Z et des clôtures déclarées valides.

**Test de détection.** Altérer une ligne de vente en base **avec un rôle
privilégié** (`UPDATE transaction_items SET total_price = total_price + 1` après
`ALTER TABLE … DISABLE TRIGGER`), puis relancer l'appel : la vérification doit
signaler un `signature_mismatch` sur la transaction concernée.

**Limite à déclarer :** la détection est complète pour les signatures **v2**.
Pour les écritures du 03/06 au 15/07/2026 (signature **v1**, non clefée, ne
couvrant ni les lignes ni les paiements), la vérification ne prouve rien sur le
contenu des lignes. → Plan **B-3**.

### 4.4 Test 3 — Clôtures

| # | Action | Attendu |
|---|---|---|
| 3.1 | Fermer la caisse depuis `/pos` (`POST /api/pos/drawer/close`) | Un Z est produit : totaux, comptage, bornes de numérotation, dernier hash, ventilation par moyen de paiement, `previous_hash` et HMAC |
| 3.2 | Laisser un tiroir ouvert et attendre 23 h 59 (ou déclencher le job) | Le tiroir est fermé, `closing_amount` vide, mention explicite dans `closing_note`, Z scellé |
| 3.3 | `POST /api/admin/fiscal-closures` sur un mois clos | Clôture créée, avec `grand_total_period`, `total_perpetual`, `sequence_number`, `previous_hash`, HMAC |
| 3.4 | Rejouer 3.3 sur la même période | Refus (contrainte d'unicité de période) — la clôture est idempotente |
| 3.5 | Tenter une clôture alors qu'un tiroir est ouvert | `409` |
| 3.6 | Tenter une clôture sur une chaîne rompue | `409 fiscal_chain_invalid` |
| 3.7 | Vérifier la présence d'un cumul perpétuel **sur le Z** | ⚠️ **absent aujourd'hui** — écart M-5 |
| 3.8 | Vérifier que le Z est verrouillé (PDF + SHA-256) après fermeture | ⚠️ **non automatique aujourd'hui** — écart M-7 |

### 4.5 Test 4 — Archives et exports

| # | Action | Attendu |
|---|---|---|
| 4.1 | `GET /api/admin/fiscal-closures/{id}/archive` | Archive JSON gzip téléchargée, en-têtes `X-Archive-SHA256` et `X-Closure-Hash` présents |
| 4.2 | Recalculer le SHA-256 hors ligne : `sha256sum archive.json.gz` | Identique à l'en-tête `X-Archive-SHA256` |
| 4.3 | Décompresser sur un poste **sans Vintiz** et lire le JSON | Notice en français, transactions, lignes, paiements et Z de la période, `software_version` figé |
| 4.4 | Rapprocher les totaux de l'archive avec les Z de la période et la comptabilité | Concordance au centime |
| 4.5 | `GET /api/accounting/exports/{export_id}/fec` | FEC aux 18 colonnes DGFiP, équilibré débit/crédit |
| 4.6 | `GET /api/accounting/fec/day/{date}` | FEC de la journée |
| 4.7 | `GET /api/admin/fiscal-export?from=…&to=…&format=json` | Export de **chaîne** au format propriétaire `vintiz-nf525-export` — à présenter comme preuve d'intégrité, **non** comme export normé |

### 4.6 Test 5 — Duplicata de ticket

| # | Action | Attendu |
|---|---|---|
| 5.1 | Encaisser une vente, imprimer le ticket (première émission) | Ticket **sans** mention duplicata |
| 5.2 | `POST /api/pos/transactions/{id}/print` (réseau MUNBYN) | Bandeau `* DUPLICATA n.1 *` en tête de ticket |
| 5.3 | `GET /api/pos/transactions/{id}/escpos` (WebUSB tablette) | Bandeau `* DUPLICATA n.2 *` — le compteur est commun aux deux chemins |
| 5.4 | `GET /api/admin/audit-logs?entity=transaction&entity_id={id}` | Trois entrées `receipt.reprint` / `receipt.escpos` avec `copy_number` et l'opérateur |
| 5.5 | `GET /api/pos/transactions/{id}/receipt` (rendu texte) | ⚠️ **ni compté ni marqué aujourd'hui** — écart B-5.a |
| 5.6 | `POST /api/pos/transactions/{id}/resend` (e-mail / SMS) | ⚠️ **ni compté ni marqué aujourd'hui** — écart B-5.a |

### 4.7 Test 6 — Remboursement

| # | Action | Attendu |
|---|---|---|
| 6.1 | Rembourser partiellement une vente | **Nouvelle** transaction de type `refund`, numérotée, liée à l'originale, signée. La vente d'origine est inchangée |
| 6.2 | Rembourser à nouveau au-delà du reste | Refus (quota de remboursement cumulé) |
| 6.3 | Vérifier la chaîne après remboursement | Valide |

### 4.8 Test 7 — Numérotation

| # | Action | Attendu |
|---|---|---|
| 7.1 | Encaisser trois ventes successives | Numéros strictement consécutifs |
| 7.2 | Provoquer un échec de paiement CB (montant non confirmé par le prestataire) | Aucune transaction créée, **aucun numéro consommé** : la vente suivante prend le numéro attendu |
| 7.3 | Rejouer le même `client_uuid` | La même transaction est renvoyée, pas une seconde vente |

### 4.9 Test 8 — À rejouer après chaque lot

Après livraison d'un lot, l'ensemble des tests 1 à 7 est rejoué et le
procès-verbal daté et signé (pièce **D-6**).

---

## 5. Pièces à joindre au dossier

### 5.1 Pièces déjà disponibles

| Réf. | Pièce | Emplacement | Statut |
|---|---|---|---|
| P-1 | Auto-déclaration technique (position réglementaire, périmètre, description des quatre piliers, réserves assumées, trame de recette) | `docs/COMPLIANCE_NF525.md` | **Disponible — à réaligner** (version et révision périmées, écart m-2) |
| P-2 | Audit de conformité point par point, 46 exigences | Rapport d'audit du 29/08/2026 | Disponible |
| P-3 | Plan de mise en conformité, lots et critères d'acceptation | `docs/PLAN_CONFORMITE_NF525.md` | Disponible |
| P-4 | Recette de déploiement de la version fiscale | `docs/RECETTE_POST_DEPLOIEMENT_1.1.1.md` | Disponible — à actualiser pour 1.1.5 |
| P-5 | Journal des versions | `docs/CHANGELOG.md` | **Incomplet** — s'arrête à 1.1.2 (écart m-3) |
| P-6 | Documentation d'architecture et de déploiement | `docs/ARCHITECTURE.md`, `docs/DEPLOIEMENT.md` | Disponible |
| P-7 | Manuel d'exploitation boutique | `docs/MANUEL_BOUTIQUE.md` | Disponible — ne couvre pas le volet fiscal (voir D-8) |

### 5.2 Pièces manquantes à produire

Ces dix pièces sont **bloquantes pour le dépôt du dossier**, indépendamment de
l'état du code.

| Réf. | Pièce | Contenu attendu | Responsable | Statut |
|---|---|---|---|---|
| **D-1** | Engagement de certification | Devis, organisme retenu (LNE ou Infocert/AFNOR), calendrier d'audit, version candidate soumise. En voie B : attestation signée (§6). | Direction | 🔴 à produire |
| **D-2** | Avis juridique sur le statut d'éditeur | Avis écrit d'un avocat fiscaliste : Vintiz est-elle « éditeur » au sens de la doctrine, ou simple assujettie développant pour ses propres besoins ? Conditionne la voie A ou B. **À lancer en premier — délai externe.** | Direction | 🔴 à produire |
| **D-3** | Nomenclature des composants et périmètre versionné | Liste des modules du périmètre fiscal avec leur empreinte, tag Git de la version candidate, SHA de build correspondant (comparable à `/api/health`), politique de gestion des évolutions fiscales (qui qualifie, qui valide, qui informe le certificateur). | Technique | 🔴 à produire |
| **D-4** | Procédure de gestion de `FISCAL_SIGNING_KEY` | Génération, dépôt sous scellé, liste nominative des porteurs, procédure de rotation **et son effet sur la vérifiabilité des chaînes antérieures** (point non traité par le code : la vérification recalcule tout avec la clé courante — cf. plan B-3.e), procédure d'accès en cas de contrôle. | Technique + Direction | 🔴 à produire |
| **D-5** | Dossier d'architecture de sécurité de la base | Matrice des rôles PostgreSQL, droits accordés et révoqués sur les tables fiscales, liste nominative des détenteurs d'un accès `psql` en production, journalisation de ces accès. **C'est la pièce qui répond à l'écart B-2.** | Technique | 🔴 à produire |
| **D-6** | Procès-verbaux de recette signés | Jeu d'essai documenté (espèces avec rendu, CB, mixte, coupon, facture B2B, remboursement partiel puis total, caisse oubliée, mode hors ligne), tentative d'altération SQL refusée, téléchargement et vérification d'archive sur un poste tiers, test de restauration complète. Chaque PV daté et signé par la responsable boutique. | Boutique + Technique | 🔴 à produire |
| **D-7** | Procédures d'exploitation et d'incident | Que faire si : la chaîne est signalée rompue ; une clôture mensuelle a échoué ; une vente hors ligne a été perdue ; l'imprimante est indisponible ; le TPE est hors service ; la base doit être restaurée. Aujourd'hui aucune de ces procédures n'est écrite. | Boutique + Technique | 🔴 à produire |
| **D-8** | Manuel utilisateur fiscal | Chapitre destiné à l'exploitant **et au contrôleur** : produire un export, lire une archive, vérifier l'empreinte d'un ticket (les 16 premiers caractères du hash figurent sur le ticket — `services/receipt.py:171`, `services/escpos_service.py:430-432`), justifier un écart de caisse, obtenir un duplicata. Avec captures d'écran. | Boutique | 🔴 à produire |
| **D-9** | Registre des durées de conservation | Table par table : donnée, base légale, durée, mode de purge, preuve d'archivage. À articuler avec la politique RGPD existante (`services/rgpd.py:40-45`, fenêtre de 30 jours) pour montrer que l'obligation fiscale de 6 ans prime sur l'effacement. | Direction | 🔴 à produire |
| **D-10** | Politique de mise à jour du parc | Comment la boutique est informée d'un déploiement, comment la version en service est vérifiée (`/api/health` l'expose déjà), comment un retour arrière est décidé — sachant que la migration `0072` **refuse** le `downgrade` et impose une restauration de sauvegarde. | Technique | 🔴 à produire |

---

## 6. Modèle d'attestation individuelle

> ## ⛔ NE PAS SIGNER EN L'ÉTAT
>
> Ce modèle est fourni **pré-rempli à titre de préparation**. Il ne peut être
> signé qu'une fois réunies **les trois conditions suivantes** :
>
> 1. **L'avis juridique (pièce D-2) conclut que Vintiz peut emprunter la voie de
>    l'attestation individuelle.** À défaut, la voie applicable est la
>    certification par organisme accrédité et ce modèle est sans objet.
> 2. **Les lots 1 et 2 du plan de conformité sont clos**, avec leurs critères
>    d'acceptation vérifiés et leurs procès-verbaux signés
>    (`docs/PLAN_CONFORMITE_NF525.md` §4).
> 3. **Les pièces D-3 à D-10 sont produites et datées.**
>
> Signer avant ces trois conditions expose le signataire à une déclaration
> inexacte engageant sa responsabilité personnelle — ce qui est beaucoup plus
> grave que la non-conformité qu'il s'agissait de couvrir. Une non-conformité se
> régularise ; une fausse déclaration, non.

### 6.1 Modèle (fondé sur le modèle BOI-LETTRE-000242)

```text
ATTESTATION INDIVIDUELLE DE CONFORMITÉ
Logiciel ou système de caisse — article 286-I-3° bis du code général des impôts

Je soussigné(e) ......................................................... ,
agissant en qualité de représentant(e) légal(e) de :

  Dénomination sociale : ...............................................
  Forme juridique      : ...............................................
  Siège social         : ...............................................
  SIREN                : ...............................................

atteste que le logiciel ou système de caisse désigné ci-après :

  Nom commercial        : Vintiz POS
  Version               : 1.1.5
  Révision de schéma    : 0076
  Version de signature  : 2
  Empreinte de version  : SHA de build ........................ (tag Git ..............)
  Date de mise à disposition / de mise en service : 3 juin 2026

satisfait aux conditions d'inaltérabilité, de sécurisation, de conservation et
d'archivage des données en vue du contrôle de l'administration fiscale, prévues
au 3° bis du I de l'article 286 du code général des impôts.

Cette attestation est délivrée pour la version mentionnée ci-dessus. Toute
évolution portant sur l'enregistrement, la signature, la numérotation, les
clôtures, les corrections, l'archivage ou l'export des données de règlement
donnera lieu à la délivrance d'une nouvelle attestation.

Je m'engage à conserver, et à présenter à toute réquisition de
l'administration, la documentation technique et les éléments de preuve
justifiant du respect de ces quatre conditions, dont la liste figure en annexe.

Fait à ......................... , le ......... / ......... / .................

Nom, qualité et signature du représentant légal :


                                   (cachet de l'entreprise)
```

### 6.2 Annexe obligatoire à l'attestation — pièces justificatives

À joindre systématiquement, sous peine de rendre l'attestation ininvocable :

| # | Pièce | Référence |
|---|---|---|
| 1 | Description des mécanismes par pilier | §3 du présent document |
| 2 | Mode opératoire de recette et procès-verbaux signés | §4 du présent document, pièce D-6 |
| 3 | Nomenclature des composants et empreinte de version | Pièce D-3 |
| 4 | Procédure de gestion de la clé de signature | Pièce D-4 |
| 5 | Matrice des droits sur la base de données | Pièce D-5 |
| 6 | Procédures d'exploitation et d'incident | Pièce D-7 |
| 7 | Registre des durées de conservation | Pièce D-9 |
| 8 | Politique de mise à jour du parc | Pièce D-10 |
| 9 | Avis juridique sur le statut d'éditeur | Pièce D-2 |

### 6.3 Réserves à faire figurer tant que les lots 1 et 2 ne sont pas clos

Si — et seulement si — un besoin impérieux conduisait à produire un document
avant la clôture des lots, **il ne peut s'agir d'une attestation de conformité**
mais d'une **déclaration d'avancement**, sans valeur d'attestation au sens de
l'article 286-I-3° bis. Cette déclaration doit énoncer :

1. que le logiciel **n'est pas certifié** et **n'est pas couvert par une
   attestation individuelle** à la date de sa rédaction ;
2. que les écarts identifiés par l'audit du 29/08/2026 sont **publiés,
   priorisés et en cours de correction**, avec le plan daté à l'appui ;
3. que les écritures de la période du **3 juin au 15 juillet 2026** relèvent
   d'un régime de preuve dégradé (signature de première génération, non clefée),
   scellé a posteriori par une clôture périodique dont l'empreinte SHA-256 est
   archivée hors ligne ;
4. que les mesures compensatoires de procédure décrites au plan
   (`PLAN_CONFORMITE_NF525.md` §6.3) sont effectivement appliquées et
   consignées ;
5. la date prévisionnelle de clôture de chaque lot.

---

## 7. Journal des versions fiscales

*(à compléter — pièce D-3 ; le `CHANGELOG` doit être réaligné au préalable,
écart m-3)*

| Version | Date | Révision DB | Signature | Qualification | Objet fiscal |
|---|---|---|---|---|---|
| 1.0.0 | 03/06/2026 | — | v1 | Fiscale | Mise en production initiale |
| 1.1.1 | 16/07/2026 | 0072 | v2 | **Fiscale** | Signature HMAC v2, triggers d'inaltérabilité, clôtures périodiques |
| 1.1.2 | 16/07/2026 | 0072 | v2 | Non fiscale | Transparence IA, révocation du profilage |
| 1.1.3 | *(à documenter)* | 0073 | v2 | *(à qualifier)* | *(à documenter)* |
| 1.1.4 | *(à documenter)* | 0074 | v2 | *(à qualifier)* | *(à documenter)* |
| 1.1.5 | *(à documenter)* | 0075 → 0076 | v2 | *(à qualifier)* | *(à documenter)* |

**Règle de qualification.** Est « fiscale » toute version modifiant le payload
signé, les triggers, la numérotation, les clôtures, les remboursements,
l'archivage ou les scripts d'exploitation qui touchent ces données. Une version
fiscale impose une revue avec le certificateur avant déploiement et peut
nécessiter un nouveau certificat ou une nouvelle attestation.

---

## 8. Ce que le dossier ne doit pas affirmer

Rappel destiné aux rédacteurs des versions ultérieures de ce document :

- **Ne pas écrire « conforme NF525 ».** La mention admise est « version
  candidate à la certification NF525 ». Un e-mail de rapport Z envoyé au
  comptable porte encore la mention interdite
  (`apps/api/app/services/fiscal.py:881`, `:892`) — écart m-1, à corriger.
- **Ne pas présenter l'export `vintiz-nf525-export` comme un export normé.**
  C'est un format propriétaire, utile comme preuve de chaîne. L'export DGFiP,
  c'est le FEC.
- **Ne pas revendiquer une protection cryptographique sur la période
  03/06 → 15/07/2026** au-delà de ce que le scellement a posteriori garantit.
- **Ne pas décrire les triggers comme une barrière absolue** tant que le compte
  applicatif est superutilisateur : ils protègent aujourd'hui contre l'erreur,
  pas contre l'intention.
- **Ne pas laisser un chiffre de version dans ce document diverger de
  `apps/api/app/version.py`.** C'est l'erreur qui a rendu
  `docs/COMPLIANCE_NF525.md` caduc en quatre versions.
