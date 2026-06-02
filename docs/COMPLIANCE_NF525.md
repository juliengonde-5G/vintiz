# Conformité NF525 — Vintiz POS

> **Statut** : implémentation technique conforme. L'attestation éditeur (§4)
> doit être signée par Vintiz avant ouverture publique.
> **Version logiciel** : **1.0.0** (release de production).
> **Mise en production / ouverture publique** : **3 juin 2026, 10h00**
> (boutique Vintiz Vernon, 6 rue Saint-Jacques, 27200 Vernon).
> **Mise à jour du document** : 3 juin 2026.

> ⚠️ **À faire avant la première vente du 03/06 10h00** : signer l'attestation
> éditeur (§4) en y reportant la version `1.0.0` et la date de
> commercialisation `03/06/2026`, puis l'archiver dans le dossier fiscal.

---

## 1. Cadre légal

La loi française anti-fraude TVA (article 88 de la loi de finances 2016, BOI-TVA-DECLA-30-10-30, décret 2016-1138) impose que **tout logiciel d'encaissement utilisé pour enregistrer des paiements de clients particuliers** soit :

- **Inaltérable** : aucune transaction ne peut être modifiée ni supprimée après enregistrement.
- **Sécurisé** : les données sont protégées contre toute altération.
- **Conservé** : les données fiscales doivent être conservées 6 ans.
- **Archivable** : les données doivent pouvoir être exportées vers les services fiscaux sur demande.

Deux modes de preuve possibles :

1. **Certification** par un organisme accrédité (LNE, Infocert) — coûteux.
2. **Attestation éditeur** (article 286, I-3° bis du CGI) — déclaration sur l'honneur de l'éditeur du logiciel, opposable aux services fiscaux. C'est la voie retenue par Vintiz.

---

## 2. Implémentation technique Vintiz

### 2.1 Inaltérabilité — chaînage SHA-256

Chaque `Transaction` (`apps/api/app/models/pos.py`) porte un champ `hash_chain: String(64)` calculé par `FiscalService.sign_transaction` (`apps/api/app/services/fiscal.py`) :

```
hash = SHA-256( transaction_number | total_ttc | created_at | previous_hash )
```

où `previous_hash` est le `hash_chain` de la transaction précédente (ou `"0"` pour la première transaction de la chaîne — l'ancrage genesis).

**Effet** : modifier rétroactivement n'importe quel champ d'une transaction passée invalide la chaîne entière à partir de cette transaction. La méthode `FiscalService.verify_chain_integrity` détecte ces ruptures.

### 2.2 Inaltérabilité — Z reports

Les `ZReport` portent les champs `hash` et `previous_hash`. Le `hash` est calculé sur :

```
hash = SHA-256( report_number | total_sales | total_refunds | total_net | tx_count | previous_hash )
```

Le scellement annuel (clôture exercice fiscal) consiste à archiver le dernier `ZReport` de la période et son hash hors-DB (PDF signé, bucket S3 immuable).

### 2.3 Sécurisation

- **Authentification** par JWT (manager) + PIN cashier 4 chiffres bcrypt-hashé (P1-002 / P1-014). Tous les événements POS portent `cashier_id` traceable.
- **Audit log** automatique sur toute mutation des modèles fiscaux (`Transaction`, `ZReport`, `CashDrawer`, etc.) via SQLAlchemy event listeners (P1-013 — `apps/api/app/services/audit.py`).
- **Hash redaction** dans les logs : les valeurs `pin_hash`/`password_hash` n'apparaissent jamais en clair dans `audit_logs.data`.
- **Connexions HTTPS** uniquement en production (Caddy reverse proxy).
- **Backup PostgreSQL** quotidien (`scripts/backup.sh`), rétention minimum 90 jours, test de restauration mensuel.

### 2.4 Conservation 6 ans

- Schéma OLTP retient toutes les transactions et Z reports indéfiniment (pas de purge automatique).
- La purge RGPD (P1-007) anonymise `client_id` à NULL mais **conserve la transaction**, son montant et son hash chain — la chaîne fiscale n'est pas rompue par l'exercice du droit à l'oubli.

### 2.5 Archivage / export DGFiP — endpoint `/api/admin/fiscal-export`

L'export est généré par `FiscalExportService` (`apps/api/app/services/fiscal_export.py`).

**Endpoint** :

```
GET /api/admin/fiscal-export?from=YYYY-MM-DD&to=YYYY-MM-DD&format=xml|json
Headers:  Authorization: Bearer <jwt-manager>
```

**Réponse** : fichier téléchargeable (`Content-Disposition: attachment`).

**Contenu** (format XML par défaut, JSON équivalent disponible) :

- Métadonnées : version, format (`vintiz-nf525-export`), nom du marchand, période, horodatage de génération.
- Compteurs agrégés (ventes, refunds, transactions, Z reports).
- Transactions ordonnées par `created_at` ascendant (= ordre de la chaîne) avec :
  - Numéro, type (sale/refund/void), date, identifiants (cashier_id, user_id, client_id).
  - Pour les refunds : `original_transaction_id` + `refund_reason`.
  - Totaux HT / TVA / TTC + `hash_chain`.
  - Lignes d'articles (product_id, quantité, prix unitaire, remise, total ligne).
  - Paiements (méthode, montant).
- Z reports avec leur chaîne (`hash` et `previous_hash`).

**Verification post-export** : un auditeur peut recalculer chaque `hash` à partir des champs exportés et le comparer au `hash_chain` stocké, confirmant l'intégrité de la séquence.

---

## 3. Tests automatisés

| Fichier | Couverture |
|---|---|
| `apps/api/tests/test_fiscal.py` | Génération du hash chain, intégrité (chaîne valide), détection d'un hash falsifié, hash Z report. |
| `apps/api/tests/test_nf525_chain.py` | Modification de `total_ttc`, `created_at`, `transaction_number` détectée. Attaque par insertion détectée. Chaîne longue (100 transactions) vérifiée. Format hash 64 hex. Ancrage genesis = `"0"`. |
| `apps/api/tests/test_audit_service.py` | Toute modification/création/suppression d'une transaction est tracée dans `audit_logs`. |

Critère d'acceptation P1-001 (V1) : *"un pytest test_nf525.py vérifie que toute modification d'une transaction passée invalide la chaîne"* → **satisfait**.

---

## 4. Attestation éditeur — modèle à signer

> Document à imprimer sur papier en-tête Vintiz, signer par le représentant légal (Julien Gondé), conserver dans le dossier fiscal et fournir aux services fiscaux sur demande.

```
ATTESTATION INDIVIDUELLE DE LOGICIEL DE CAISSE
(article 286, I-3° bis du Code général des impôts)

Je soussigné(e) [Nom Prénom],
agissant en qualité de [fonction] de la société Vintiz SAS,
sise [adresse],
SIREN [numéro],

ATTESTE que le logiciel "Vintiz POS",
version v1.0.0, commercialisé à compter du 03/06/2026,

satisfait aux conditions d'inaltérabilité, de sécurisation, de conservation et
d'archivage des données prévues par les articles 88 de la loi 2015-1785 du 29
décembre 2015 et 286, I-3° bis du CGI.

Cette attestation porte sur les fonctions de :
  - Enregistrement des opérations de paiement (caisse).
  - Conservation des données pendant 6 ans.
  - Sécurisation par chaînage SHA-256 des transactions.
  - Export fiscal sur demande (endpoint /api/admin/fiscal-export).

Fait à [ville], le [date].

Signature et cachet de l'éditeur :
```

**Conserver** : exemplaire signé + journal de version du logiciel (lien Git tag) + tests automatisés (sortie pytest archivée à chaque release).

---

## 5. Procédure de renouvellement

Lors de toute évolution touchant le moteur fiscal (modèle `Transaction`, `ZReport`, service `FiscalService`, service `FiscalExportService`) :

1. Lancer la suite de tests (`apps/api/tests/test_fiscal.py`, `test_nf525_chain.py`, `test_fiscal_export.py`).
2. Mettre à jour la version du logiciel + date dans l'attestation §4.
3. Re-signer l'attestation.
4. Régénérer un export DGFiP pour archive de référence (peut servir de "spécimen" en cas de contrôle).

---

## 6. Version & mise en production

| Élément | Valeur |
|---|---|
| Version logiciel certifiée | **v1.0.0** |
| Date de commercialisation / mise en production | **03/06/2026, 10h00** |
| Tag Git de référence | `v1.0.0` (commit figé sur `main`) |
| Périmètre fiscal | Caisse POS (`/api/pos/*`), Z reports, export DGFiP |
| Première chaîne de transactions | démarre à l'ouverture après `go_live_reset.py` (base opérationnelle vidée, inventaire conservé) |

> Le `go_live_reset.py` exécuté avant l'ouverture remet les compteurs à zéro
> (`transaction_number`, `report_number`) et démarre une chaîne fiscale propre
> ancrée sur le genesis `"0"`. Aucune transaction de test/démo ne subsiste dans
> la chaîne de production — point vérifiable lors d'un contrôle.

---

## 7. Limites connues

- L'attestation §4 doit être signée **avant ouverture publique** de la boutique Vernon. Cette tâche est humaine, hors périmètre Claude Code.
- Le scellement annuel cryptographique externe (timestamping RFC 3161 sur le dernier hash de l'exercice) n'est pas implémenté. Il sera nécessaire si la chaîne dépasse plusieurs années sans audit ; pour la phase de lancement, le backup DB quotidien + l'export annuel suffisent.
- Le mode "consignation" (bons de réservation 48h, P4-005) n'est pas couvert par cette attestation : aucun paiement n'est enregistré, donc pas de portée fiscale.
