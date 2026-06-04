# Audit VINTIZ — Contre-audit Claude & analyse d'écarts avec Codex

**Date :** 04/06/2026
**Périmètre :** lecture statique du dépôt local `vintiz` (apps/api FastAPI, apps/web admin, apps/site vitrine).
**Méthode :** 4 audits indépendants menés en parallèle (commercial, technique, comptable, juridique/RGPD), chacun chargé de vérifier les affirmations de l'audit Codex avec preuve `fichier:ligne`.
**Document de référence comparé :** `AUDIT_DIRECTION_2026_06_04.md` (Codex).

---

## A. Résumé exécutif

### Verdict de convergence

Mon contre-audit **confirme intégralement** l'audit de Codex. Les **24 affirmations factuelles** vérifiées (6 techniques, 6 comptables, 7 juridiques + autres) sont **toutes CONFIRMÉES** par preuve code, à deux nuances mineures près (tailles de fichiers à ±1 %, `app_config.json` gitignoré). Aucune affirmation de Codex n'a été infirmée.

Au-delà de la confirmation, mon audit **étend et aggrave** le diagnostic sur 3 points et **ajoute des angles morts** que Codex n'avait pas couverts (pilotage commercial par vendeur, détection de fraude caisse, modèle dépôt-vente, bug bloquant `deletion-request`).

### Les 3 risques critiques (consensus des deux audits)

| Risque | Codex | Claude | Statut |
|---|---|---|---|
| **Données client publiques par simple email** (`/api/crm/account/*` sans JWT) | Critique | **Critique — aggravé** | Confirmé + le front n'envoie même pas le JWT ; faille de rôle back-office en plus |
| **Panier POS non validé serveur** (prix/remise/quantité libres) | Critique | **Critique** | Confirmé : `CartItem` sans aucune contrainte Pydantic |
| **TVA codée en dur à 20 %** (`tva_service` jamais appelé) | Majeure | **Critique — relevé** | Confirmé : non-conformité fiscale réelle, je relève la criticité |

### Niveau d'urgence

**Identique à Codex : urgence élevée.** Exploitation boutique possible sous vigilance avec équipe restreinte de confiance ; **blocage de toute ouverture publique de l'espace client et de toute généralisation multi-utilisateur** avant correction des critiques #1, #2, #3.

---

## B. Tableau d'analyse d'écarts (Codex ↔ Claude)

### B.1 — Points confirmés à l'identique

| Réf. Codex | Sujet | Mon verdict | Preuve complémentaire |
|---|---|---|---|
| #1 Critique | `/account/*` & `lookup_client` publics par email | **CONFIRMÉ** | Liste exhaustive route par route établie : 20+ endpoints `account.py` sans `get_current_client` ; `lookup-brief` et `clients/{id}/brief` aussi non authentifiés |
| #2 Critique | Panier POS prix/remise/quantité non bornés | **CONFIRMÉ** | `CartItem` (`pos/router.py:41-50`) : zéro `ge/le/gt` ; `unit_price` écrase `product.sale_price` (`pos.py:117`) |
| #3 Majeure | TVA 20 % en dur, `tva_service` non branché | **CONFIRMÉ — relevé en Critique** | `pos.py:150-152`, `tva_rate` jamais persisté `pos.py:219-228` ; `tva_service` n'a d'usage que dans les tests |
| #4 Majeure | `/drawer/current` imports cassés | **CONFIRMÉ** | `ModuleNotFoundError` reproduit ; `pos/router.py:829-830` ; aucun test ne couvre la route → 500 quotidien |
| #5 Majeure | CI non bloquante + `deploy needs: []` | **CONFIRMÉ** | `ci.yml` `|| true`/`echo` partout ; `deploy.yml` `needs: []` avec commentaire trompeur |
| #6 Majeure | Rôles trop grossiers | **CONFIRMÉ — étendu** | Refund/drawer/Z en `get_current_user` ; **+ faille back-office** : export/suppression RGPD accessibles à tout user authentifié |
| #7 Majeure | Hash-chain ordonné par `created_at` | **CONFIRMÉ** | `fiscal.py:50-59`, `:67-69` ; risque collision même seconde sous replay offline |
| #8 Moyenne | JWT en localStorage | **CONFIRMÉ** | `api.ts:29,61` (manager) ; `login/page.tsx:44,137` (client) ; token renvoyé en corps JSON, pas en cookie |
| #9 Moyenne | Fichiers monolithiques | **CONFIRMÉ** | `pos/router.py`=2854, `admin/router.py`=2621, `crm/router.py`=1585, `pos/page.tsx`=3628, `settings/page.tsx`=2544 |
| #10 Moyenne | Secrets UI en clair (JSON) | **CONFIRMÉ — nuancé** | `app_config.py` `json.dump` clair ; **mais** `data/` est gitignoré → pas de fuite Git, risque = disque VPS au repos |
| #11 Moyenne | Doc SumUp contradictoire | **CONFIRMÉ** | Doc « JWT cookie 1h » contredite par localStorage ; docs d'audit concurrentes à la racine |
| #12 Mineure | Tests non exécutables sans deps | **CONFIRMÉ** | ~88 fichiers de test (~900 fonctions) existent mais non joués en CI bloquante |

**Bilan : 12/12 anomalies Codex confirmées.** Divergences uniquement sur la **criticité de la TVA** (Codex Majeure → je la passe Critique : c'est un risque fiscal direct) et **deux imprécisions factuelles mineures** sans impact sur le fond.

### B.2 — Points que MON audit ajoute (angles morts de Codex)

| # | Criticité | Nature | Anomalie | Preuve | Pourquoi ça compte |
|---|---|---|---|---|---|
| N1 | **Critique** | Sécurité front | Le front n'envoie **jamais** le JWT : l'espace client s'identifie sur `localStorage["vintiz_account_email"]` éditable | `account/historique/page.tsx:55-58`, idem selection/fidelite/offres/rgpd | Le magic-link ne protège **rien** — aggrave #1 Codex |
| N2 | **Critique** | Bug bloquant | `NameError: timedelta` sur `deletion-request` (import manquant) | `account.py:21` vs `:341,350` | 500 sur la route ; révèle l'absence de test/CI sur ces routes |
| N3 | **Majeure** | Contrôle interne | **Aucun reporting par vendeur/caissier** alors que `cashier_id` est stocké | `reporting/router.py:61-238` (aucun `group_by cashier_id`) | Impossible de piloter une équipe ni de repérer un caissier atypique |
| N4 | **Majeure** | Fraude | **Points/bons fidélité non repris au remboursement** | `services/refund.py` (aucun débit `LoyaltyTransaction`), gain `pos.py:733-761` | Acheter → gagner points/bon → se faire rembourser en avoir = gain conservé |
| N5 | **Majeure** | Anti-fraude | **Aucune détection d'anomalies de caisse** (écarts récurrents, refunds/remises atypiques par caissier) | données présentes (`PaymentAttempt`, `CashMovement`, `cashier_id`) mais jamais croisées | Manipulations invisibles ; `store_ops_audit.py` ne couvre que les fiches produit |
| N6 | **Majeure** | Contrôle interne | **Remises sans audit log** (seuls reprice et override cash sont tracés) | `grep AuditLog` sur `pos/router.py` → uniquement `cash_cap_override` et `receipt.reprint` | Toute remise jusqu'à 30 % (UI) sans trace ni validation |
| N7 | **Élevée** | RGPD | Séparation des rôles back-office absente : un cashier peut **exporter/supprimer** le dossier RGPD de tout client | `crm/router.py:1034,1051,992,291` (que `get_current_user`) | Droits RGPD critiques accessibles sans rôle manager |
| N8 | **Moyenne** | Fiscal | `report_number` du Z via `MAX+1` (pas de séquence) | `fiscal.py:131-134` | Collision/trou possible sous clôtures concurrentes |
| N9 | **Moyenne** | Fiscal | `close_drawer` ne verrouille pas le Z (`lock_z_report` manuel only) | `pos/router.py:727-809` vs `fiscal.py:207-269` | Intangibilité NF525 dépend d'un clic manager optionnel |
| N10 | **Moyenne** | RGPD | Backups PostgreSQL **non chiffrés au repos**, PII en clair, téléchargeables | `database_backup.py`, `/admin/database/backups/{id}/download` | Fuite massive si volume compromis |
| N11 | **Moyenne** | RGPD | nom/prénom en clair dans audit logs (conservés 6 ans) | `audit.py:48,91-125` (seuls email/tel hashés) | Sur-conservation de PII identifiante |
| N12 | **Moyenne** | Métier | GMROI/marge non fiables (`purchase_price=0`), **pas de modèle dépôt-vente** (déposant, commission, reversement) | `models/product.py:101-103`, `retail_kpis.py:226-232` | Modèle économique seconde-main mal couvert si consignation |
| N13 | **Moyenne** | RGPD | Pas de purge automatique des **clients inactifs** (durée max de conservation) | `rgpd.py` (seul `loyalty_expires_at` 24 m) | Non-conformité art. 5-1-e |
| N14 | **Faible** | Métier | Objectifs CA par zone définis mais **non confrontés au réalisé** | `zones` vs `reporting/router.py` (pas de jointure) | Merchandising par zone non piloté au résultat |
| N15 | **Faible** | Fiscal | Fenêtre Z `opened_at` strict (la close utilise `-1s`) | `fiscal.py:113` vs `pos.py:532` | Vente de la 1ʳᵉ seconde potentiellement hors Z |
| N16 | **Faible** | Fiscal | Export fiscal sans `tva_rate` par ligne | `fiscal_export.py:116-129` | Contrôleur ne peut pas auditer la TVA par taux |
| N17 | **Faible** | Hygiène repo | Binaires lourds (PDF 11 Mo, jpeg 2,8 Mo) + docs d'audit redondantes à la racine | racine du dépôt | Poids/bruit, à sortir en LFS/assets |

### B.3 — Points où je nuance Codex

| Sujet | Position Codex | Ma nuance |
|---|---|---|
| Secrets `app_config.json` | "Secrets UI en clair sur disque" | Exact, **mais** `data/` est gitignoré → pas de fuite Git. Le risque réel = disque VPS au repos + dumps de backup non chiffrés (cf. N10) |
| Tailles de fichiers | admin 2583, page 3615 | Réel : admin **2621**, page **3628**. Ordre de grandeur juste, conclusion identique |
| Criticité TVA | Majeure | **Critique** : risque fiscal direct (TVA collectée fausse, FEC erroné, redressement) |

---

## C. Synthèse par domaine

### C.1 Métier / commercial
Outil **très complet** sur le parcours vente/retour/avoir/encaissement, la fidélisation et l'automatisation merchandising/prédictif. **Faiblesses concentrées sur le pilotage humain classique** : aucune lecture par vendeur (N3), pas de détection d'anomalies de caisse (N5), marge/dépôt-vente non couverts (N12). Les données existent mais ne sont pas croisées.

### C.2 Technique
Architecture monorepo claire mais **routers monolithiques** et **CI/CD non protectrice** (cause systémique : un bug 1-ligne comme `drawer/current` atteint la prod). **Schéma DB ambigu** (`create_all` au boot + migrations non rejouables sur base vierge). Bonne suite de tests, mais non bloquante.

### C.3 Comptable / fiscal
Socle NF525 sérieux (idempotence, séquences, FEC équilibré avec assert anti-déséquilibre, hash-chain, export DGFiP). **Deux failles compromettent la conformité réelle** : TVA mono-taux de fait (critique) et panier non validé serveur (critique). Plus : Z non verrouillé automatiquement (N9), hash ordonné par `created_at` (#7), `report_number` via MAX+1 (N8).

### C.4 Juridique / RGPD
Briques RGPD **bien conçues** (consent ledger probatoire, suppression 30 j + anonymisation, magic-link anti-énumération, webhook Brevo protégé). **Mais l'authentification de l'espace client est un théâtre** : `get_current_client` existe et n'est branché nulle part, le front n'envoie pas le JWT. Toute personne connaissant un email peut lire/modifier/exporter/supprimer un dossier. Violation art. 5, 7, 17, 20, 32.

---

## D. Plan d'action proposé

> ⚠️ **Aucune ligne de code ne sera modifiée sans validation explicite.** Application en production. Le plan ci-dessous est une proposition d'ordonnancement à arbitrer.

### Lot 0 — Correctifs immédiats (0–3 jours, faible effort, fort impact)

| Action | Anomalie | Effort | Risque de régression |
|---|---|---|---|
| 0.1 Corriger les imports de `/drawer/current` (`app.models.pos`) + ajouter un test | #4 / N2 | < 1 h | Quasi nul |
| 0.2 Corriger le `NameError timedelta` dans `account.py` | N2 | Trivial | Nul |
| 0.3 **Gater toutes les routes `/account/*` de données derrière `get_current_client`** + supprimer le param `email` + faire envoyer le JWT par le front | #1 / N1 | Élevé | **Moyen** — change le parcours espace client (à tester soigneusement) |
| 0.4 Borner `CartItem` (Pydantic `quantity ge=1`, `discount_percent ge=0 le=…`), refuser `unit_price` arbitraire, refuser total ≤ 0 | #2 | Faible | Faible |
| 0.5 Rendre la CI bloquante (`pytest`, `ruff`, `tsc --noEmit`) + `deploy.needs` sur le CI | #5 | 0,5–1 j | Faible (mais peut révéler des échecs existants) |

### Lot 1 — Court terme (1–3 semaines)

- 1.1 **Brancher le calcul TVA multi-taux** (`tva_service`) dans `PosService` et `RefundService`, persister `TransactionItem.tva_rate` depuis `Product.tva_rate` (#3, N16, #8 commercial)
- 1.2 **Séparation des rôles** : créer `cashier / manager / compta / admin` ; réserver refund, ouverture/fermeture caisse, exports, données RGPD au bon rôle (#6, N7)
- 1.3 **Audit-logger toutes les remises** + override manager + motif au-delà d'un seuil (N6)
- 1.4 **Reprendre points/bons fidélité au remboursement** (N4)
- 1.5 Appeler `lock_z_report` dans le flux de fermeture (N9)
- 1.6 Migrer les tokens de `localStorage` vers cookie `httpOnly/Secure/SameSite` (#8)

### Lot 2 — Moyen terme (1–2 mois)

- 2.1 **Reporting par vendeur/caissier** + tableau d'**anomalies de caisse** (écarts cumulés, taux de refund cash, remises moyennes, seuils d'alerte) (N3, N5)
- 2.2 Ordonner hash-chain et périmètre Z par `transaction_number` ; créer `z_report_number_seq` (#7, N8, N15)
- 2.3 Chiffrer les dumps de backup + restreindre l'accès FS (N10)
- 2.4 Registre RGPD complet + purge des clients inactifs + revoir conservation nom/prénom audit (N11, N13)
- 2.5 Modèle dépôt-vente (déposant, commission, reversement) si applicable + GMROI conditionnel (N12)

### Lot 3 — Refontes structurantes (différable)

- 3.1 Découper `pos/router.py`, `admin/router.py`, `pos/page.tsx` en sous-domaines
- 3.2 Migration baseline Alembic unique + retrait de `create_all` au boot prod
- 3.3 Tests E2E critiques (vente cash/CB, refund partiel, avoir, clôture Z, export FEC, espace client magic-link)
- 3.4 Confrontation réalisé/objectif par zone (N14) ; nettoyage repo binaires/docs (N17)

### Points à surveiller avant toute généralisation

- Attestation NF525 humaine à signer/archiver (`docs/COMPLIANCE_NF525.md`)
- Preuve de restauration des backups + chiffrement
- Cartographie des accès (qui peut consulter/exporter clients, transactions, FEC, backups)
- Cohérence documentaire (SumUp prod-only, JWT cookie vs localStorage)

---

## E. Conclusion

Les deux audits **convergent fortement** : VINTIZ est fonctionnellement très avancé pour une boutique de seconde main, avec un socle fiscal et RGPD sérieux, mais **trois flux critiques restent insuffisamment verrouillés côté serveur** — confidentialité client, validation du panier POS, calcul TVA. Mon contre-audit valide l'intégralité du diagnostic Codex et y ajoute le **pilotage commercial par vendeur**, la **détection de fraude caisse**, la **reprise fidélité au remboursement** et un **bug bloquant** (`deletion-request`) que Codex n'avait pas relevés.

**Décision recommandée :** poursuivre l'exploitation boutique sous vigilance (équipe restreinte de confiance) ; **bloquer l'ouverture publique de l'espace client et toute généralisation** avant correction du Lot 0 (critiques #1/N1, #2, #4-drawer, et CI bloquante).
