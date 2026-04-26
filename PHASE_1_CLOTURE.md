# Phase 1 — Clôture (26 avril 2026)

> **Branche** : `claude/audit-action-plan-GHnWJ`
> **Période** : 26 avril 2026 (single-session sprint)
> **Statut** : ✅ tous les tickets backend + UI livrés, 93/93 tests verts.
> **Action restante** : signature de l'attestation éditeur NF525 + test cycle
> simulé D-30 (humain uniquement).

---

## 1. Tickets livrés (10/10 + 1 fermé en faux positif)

| ID | Titre | Backend | UI | Tests | Migration |
|---|---|:---:|:---:|:---:|:---:|
| P1-001 | NF525 chaînage SHA-256 + export DGFiP | ✅ | n/a | 17 | — |
| P1-002 | PIN cashier 4 chiffres bcrypt | ✅ | ✅ | 17 | 0002 |
| P1-007 | RGPD CRM (consents, export, deletion) | ✅ | ✅ | 12 | 0004 |
| P1-008 | Multi-photos produit + upload binaire | ✅ | ✅ | 11 | 0005 |
| P1-009 | Split payment (libellé cumulable) | ✅ | ✅ | — | — |
| P1-010 | Refund / avoir POS + ticket 80mm | ✅ | ✅ | 9 + 6 | 0003 + 0006 |
| P1-013 | AuditLog via SQLAlchemy event listeners | ✅ | n/a | 7 | — |
| P1-014 | `cashier_id` Transaction / Drawer / Z report | ✅ | ✅ | — | 0002 |
| P1-015 | Export XML/JSON DGFiP (clôt P1-001) | ✅ | n/a | 6 | — |
| P1-016 | `Client.avoir_credit` + ledger | ✅ | ✅ | (couvert P1-010) | 0003 |
| P2-009 | Bug scoring (formule incorrecte) | ✅ Fermé faux positif | — | 14 | — |

**Tickets reportés Phase 2** : P2-010 (`category_trend` dynamique — couplé à
`ai_trend`).

---

## 2. Surface de code livrée

### Modèles SQLAlchemy

```
apps/api/app/models/
├── client.py        +AvoirTransaction +AvoirTxType +Consent +ConsentPurpose
│                    +Client.avoir_credit +Client.deletion_requested_at
├── pos.py           +Transaction.cashier_id +Transaction.original_transaction_id
│                    +Transaction.refund_reason +CashDrawer.cashier_id
│                    +ZReport.cashier_id +PaymentMethod.avoir
├── product.py       +ProductPhoto (cascade delete-orphan, ordre + primary)
└── user.py          +User.pin_hash (nullable, bcrypt)
```

### Services

```
apps/api/app/services/
├── audit.py         (NEW) before_flush + after_flush listeners,
│                    7 entités tracées, hash redaction
├── cashier.py       (NEW) PIN bcrypt 4 chiffres, timing-constant lookup
├── fiscal_export.py (NEW) snapshot période + encodeurs XML / JSON DGFiP
├── photo.py         (NEW) invariants 1-primary + ordre contigu + miroir
│                    Product.photo_url
├── refund.py        (NEW) RefundService cash/card/cheque/avoir,
│                    over-refund guard, NF525-chained
├── rgpd.py          (NEW) consent ledger + portable export +
│                    soft/hard delete, purge cron 30j
├── pos.py           +avoir checkout (debit ledger + balance decrement)
├── fiscal.py        +cashier_id sur Z reports
└── receipt.py       +template ticket retour 80mm
```

### API REST

```
/api/admin/
  GET  /audit-logs                 (manager only, filtres entity/action/user_id)
  GET  /fiscal-export?from=&to=&format=xml|json   (manager only)

/api/inventory/products/{id}/
  GET    /photos
  POST   /photos                    (URL)
  POST   /photos/upload             (multipart, 5 MB max, jpg/png/webp)
  POST   /photos/{pid}/primary
  POST   /photos/reorder
  DELETE /photos/{pid}

/api/pos/
  POST /transactions/{id}/refund    (cash/card/cheque/avoir)
  POST /cashier/login               (PIN)
  POST /cashier/set-pin             (manager only)
  POST /cashier/clear-pin           (manager only)
  GET  /cashier/list                (manager only)

/api/crm/clients/{id}/
  GET  /avoir
  GET  /consents
  POST /consents
  GET  /data-export
  POST /deletion-request
  POST /deletion-cancel

/api/crm/account/                   (PUBLIC, email-based)
  GET  /data-export?email=
  POST /deletion-request            body: { email }
  POST /deletion-cancel             body: { email }
```

### Frontend

```
apps/web/
├── components/cashier/CashierPinModal.tsx    (NEW) clavier 4 chiffres,
│                                              auto-submit, dismissible
├── components/inventory/PhotoGallery.tsx     (NEW) carousel + reorder + upload
├── components/pos/RefundModal.tsx            (NEW) sélection items,
│                                              méthode, motif, ticket 80mm
├── app/admin/page.tsx                        +bouton "Rembourser" par ligne
├── app/admin/users/page.tsx                  (NEW) gestion PIN
├── app/inventory/[id]/page.tsx               PhotoGallery
├── app/pos/page.tsx                          PIN obligatoire au mount,
│                                              avoir checkout, label cumulable
└── components/layout/Sidebar.tsx             +entrée Utilisateurs

apps/site/
├── app/account/data/page.tsx                 (NEW) export JSON public,
│                                              demande/annulation suppression
├── app/cgv/page.tsx                          réécrit (avoir, split, fidélité)
└── app/confidentialite/page.tsx              réécrit (RGPD complet, NF525,
                                                sous-traitants, art. 22)
```

### Migrations Alembic

| # | Sujet | Idempotente |
|---|---|:---:|
| 0001 | `email_optin` / `sms_optin` | ✅ (déjà présente) |
| 0002 | `pin_hash` + `cashier_id` × 3 | ✅ |
| 0003 | `avoir_credit` + `original_transaction_id` + `avoir_transactions` | ✅ |
| 0004 | `consents` + `deletion_requested_at` | ✅ |
| 0005 | `product_photos` + backfill depuis `Product.photo_url` | ✅ |
| 0006 | `payment_method` enum +`avoir` | ✅ |

### Crons APScheduler

| ID | Fréquence | Sujet |
|---|---|---|
| `monthly_scoring` | 1er mercredi 06:00 | Recalcul score 6 composantes |
| `daily_rgpd_purge` | 03:00 | Hard-delete clients dont la fenêtre 30j est expirée |

---

## 3. Tests

```
93 tests / 93 verts (suite isolée --noconftest)

tests/test_audit_service.py        7  Event listeners
tests/test_cashier_pin.py          17 PIN bcrypt + auth
tests/test_fiscal.py               4  Hash chain (existant)
tests/test_fiscal_export.py        6  Export DGFiP XML / JSON
tests/test_nf525_chain.py          7  Falsification champ par champ
tests/test_photo_service.py        11 Invariants multi-photos
tests/test_receipt_refund.py       6  Template ticket retour
tests/test_refund_service.py       9  Refund cash/avoir + edge cases
tests/test_rgpd_service.py         12 Consents + export + purge
tests/test_scoring_formula.py      14 Bornes + pondération + buckets
```

---

## 4. Builds

```
apps/web (Next.js 14)        22 routes statiques + dynamiques, build green
apps/site (Next.js 14)       16 routes, build green
apps/api (FastAPI)           imports clean, lifespan ok, mount /uploads OK
```

---

## 5. Documentation produite

| Fichier | Sujet |
|---|---|
| `PLAN_ACTION_2026.md` | Plan complet 4 phases (mis à jour avec statut Phase 1) |
| `AUDIT_GROUND_TRUTH.md` | Écart audit V1/V2 vs réalité du code |
| `PHASE_1_CLOTURE.md` | Ce document |
| `docs/COMPLIANCE_NF525.md` | Cadre légal + impl. + template attestation §4 |
| `CLAUDE.md` | Mise à jour endpoints API |

---

## 6. Reste avant ouverture publique Vernon

### Bloquants (humain uniquement)

1. **Signature attestation éditeur NF525** — `docs/COMPLIANCE_NF525.md` §4.
   À imprimer en-tête Vintiz, signer par Julien Gondé, archiver dans le
   dossier fiscal. Document sans portée tant qu'il n'est pas signé.
2. **Test cycle simulé D-30 jours** — Sophie ouvre la caisse, traite 20
   transactions de tous types (vente simple, split payment, avoir, refund
   cash, refund avoir), ferme la caisse, génère le rapport ESS du jour.
   Si le cycle passe sans intervention humaine, le produit est prêt.

### Follow-ups facultatifs (non bloquants)

| Sujet | Justification du report |
|---|---|
| Magic-link sur endpoints publics RGPD | Énumération d'emails = risque mineur. À traiter si besoin pré-launch. |
| Bascule Scaleway Object Storage pour photos | Storage local OK pour MVP Vernon (1 boutique, < 10 k photos). |
| `category_trend` dynamique (P2-010) | Couplé à `ai_trend.py`, nature Phase 2. |
| Z report ventilation par cashier dans l'UI manager | API expose déjà `cashier_id`, simple évolution du tableau. |

---

## 7. Commits

```
20926f2 Phase 1 follow-ups: refund 80mm ticket, photo binary upload, enriched legal pages
86a1dc5 Sprint UI Phase 1: photo gallery, refund modal, avoir checkout, RGPD client
8974d09 Add NF525/DGFiP fiscal export endpoint and compliance documentation (P1-015 closes P1-001)
1d1082b Add multi-photo support per product (P1-008)
04b6742 RGPD-by-design CRM: consents, data export, soft/hard deletion (P1-007)
feada27 Add POS refund flow with cash / card / cheque / avoir settlement (P1-010 + P1-016)
8713662 Auto-populate AuditLog via SQLAlchemy event listeners (P1-013)
4b41fba Add POS cashier PIN UI: identification modal + admin management page
cf01e50 Add cashier PIN authentication and cashier_id traceability (P1-002 + P1-014)
2b84418 Add scoring formula and NF525 chain tampering tests (Phase 0bis)
8ba6162 Add AUDIT_GROUND_TRUTH.md revising the action plan against actual code
89eb6a9 Add PLAN_ACTION_2026.md consolidating audits V1 + V2
```

12 commits, ~7 700 lignes ajoutées sur la branche.

---

## 8. Phase suivante

**Phase 2 — fondations IA (4-6 semaines)** : event store partitionné, pgvector,
Personal Shopper v2, mapping IA. Ticket de tête : **P1-003** (schéma `events`
mensuel + instrumentation 16 event_types).

Voir `PLAN_ACTION_2026.md` §Phase 2 pour la liste complète.
