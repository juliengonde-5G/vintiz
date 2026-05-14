# SumUp — runbook intégration Vintiz

Audit + intégration conforme à la spec officielle :
- [OpenAPI 3.0](https://github.com/sumup/sumup-openapi/blob/main/openapi.yaml)
- [Cloud API guide](https://developer.sumup.com/terminal-payments/cloud-api)
- [Readers API](https://developer.sumup.com/api/readers)

Objectif **ZERO défaut** sur les paiements CB : aucun cas où le client est
débité sans que la vente Vintiz soit validée, ni l'inverse.

## Architecture

```
Tablette POS Vintiz                          api.sumup.com
   │ (PWA Chrome Android)                          │
   │                                               │
   │ 1. POST /api/pos/payments/cb/initiate         │
   ├──────────────────────────────────────────────►│
   │                                               │
   │ 2. POST /v0.1/merchants/{m}/readers/{r}/checkout
   │                                               │ ──► SumUp Solo
   │                                               │     (Wi-Fi / 4G)
   │ 3. POLL /api/pos/payments/cb/{id}/status      │
   ├──────────────────────────────────────────────►│
   │                                               │
   │ 4. status=PAID + transaction_id+auth_code     │
   │◄──────────────────────────────────────────────┤
   │                                               │
   │ 5. POST /api/pos/transactions (commit sale)   │
```

## Endpoints SumUp consommés

| Endpoint | Méthode Vintiz | Usage |
|---|---|---|
| `POST /v0.1/checkouts` | `create_checkout` (fallback sans reader) | Paiement par lien |
| `GET  /v0.1/checkouts/{id}` | `get_checkout_status` | Polling toutes les 2 s |
| `DELETE /v0.1/checkouts/{id}` | `cancel_checkout` | Annule un checkout non payé |
| `POST /v0.1/merchants/{m}/readers/{r}/checkout` | `_push_to_reader` | Push paiement sur Solo |
| `GET  /v0.1/merchants/{m}/readers/{r}` | `ping_reader` (pairing) | Bandeau POS |
| `GET  /v0.1/merchants/{m}/readers/{r}/status` | `ping_reader` (live) | Bandeau POS |
| `POST /v0.1/merchants/{m}/readers/{r}/terminate` | `terminate_reader_checkout` | Annulation mid-paiement |
| `POST /v1.0/merchants/{m}/payments/{id}/refunds` | `refund_transaction` | Remboursement CB |
| `GET  /v2.1/merchants/{m}/transactions` | `get_transaction` | Réconciliation post-paiement |

## Configuration

### Production (clés live)

Dans `/settings > Paiement` (ou `.env` au boot) :

```env
SUMUP_API_KEY=sup_sk_…                    # Secret key, commence par sup_sk_ (sans _test_)
SUMUP_MERCHANT_CODE=M…                    # 8 chars, visible dans l'app SumUp
SUMUP_READER_ID=rdr_…                     # ID du TPE Solo (récupéré via GET /readers)
SUMUP_RETURN_URL=                         # Optionnel : webhook après paiement
SUMUP_AFFILIATE_APP_ID=fr.vintiz.pos      # Optionnel : pour traçabilité avancée
SUMUP_AFFILIATE_KEY=                      # Créer sur developer.sumup.com/affiliate-keys
```

### Sandbox (clés test)

Les clés SumUp test sont préfixées `sup_sk_test_`. Le service détecte
automatiquement le mode test et le remonte au front via
`is_sandbox: true` dans `GET /api/pos/payments/cb/config`. Le bandeau
POS affiche alors **"Mode test SumUp"** en orange.

Pour obtenir des clés test : [developer.sumup.com → API Keys → Create
test key](https://developer.sumup.com/api-keys).

## Mode dégradé

Cas où SumUp Cloud est injoignable ou le Solo offline :

| Situation | Comportement | Action manager |
|---|---|---|
| Cloud SumUp injoignable au boot | Banner rouge POS, bouton CB désactivé | Encaisser en espèces/chèque |
| Solo offline (Wi-Fi coupé) | Banner orange POS via `ping_reader` | Vérifier le Wi-Fi du Solo / rappairer |
| Solo busy (READER_BUSY 422) | Toast "Le TPE traite déjà un paiement" | Redémarrer le Solo (bouton power 10 s) |
| Checkout timeout (60 s SumUp) | Le checkout passe à FAILED | Nouvelle tentative |
| Tablette perd le réseau pendant le polling | Le checkout reste PENDING côté SumUp | Récupérer via `GET /v2.1/.../transactions?foreign_transaction_id=<our_uuid>` une fois le réseau revenu |

## Traçabilité (NF525 + remboursement)

Chaque paiement CB persiste sur la `Payment` row :
- `sumup_checkout_id` (ID interne du checkout, jamais réutilisé)
- `sumup_transaction_id` (UUID, **requis pour le remboursement**)
- `sumup_transaction_code` (code court visible sur l'app SumUp et le relevé bancaire — ex : `TEENSK4W2K`)
- `sumup_auth_code` (code d'autorisation banque)
- `sumup_card_brand` (VISA, MASTERCARD, …)
- `sumup_card_last4` (4 derniers chiffres, affichés sur le ticket)
- `sumup_refunded_amount` (cumulatif sur remboursements partiels)
- `sumup_environment` (`production` / `sandbox`)

Le ticket de caisse affiche `CB Visa ****1234` au lieu de juste `CARD`.

## Remboursement

Quand `refund_method == "card"` côté `/transactions/{id}/refund`, le
serveur :
1. Crée la transaction de remboursement (NF525 hash chain).
2. Récupère le `sumup_transaction_id` du paiement CB original.
3. Appelle `POST /v1.0/merchants/{m}/payments/{id}/refunds` avec
   le montant à rembourser.
4. Met à jour `Payment.sumup_refunded_amount`.

Réponse `/transactions/{id}/refund` enrichie d'un champ `sumup_refund` :

```json
{
  "id": "…",
  "transaction_number": 1234,
  "total_ttc": 25.0,
  "refund_method": "card",
  "sumup_refund": {
    "ok": true,
    "status": "refunded",
    "message": "Remboursement SumUp effectué (25.0 EUR)"
  }
}
```

Cas d'échec gérés explicitement :
- `NOT_FOUND` → "Transaction introuvable côté SumUp"
- `CONFLICT` → "Pas dans un état remboursable (déjà remboursée, expirée, ou non finalisée)"
- `NOT_ENOUGH_BALANCE` → "Solde SumUp insuffisant — voir l'app SumUp"
- Paiement non tracé → bandeau jaune "À reverser manuellement via l'app SumUp"

## Annulation mid-paiement (Terminate)

Quand le client change d'avis pendant que le TPE affiche "Insérez votre
carte" :

```
POST /api/pos/payments/cb/terminate
→ { ok: true, status: "terminated", message: "Annulation envoyée au TPE" }
```

Pré-requis SumUp :
- Solo firmware ≥ 3.3.28.0
- Le TPE doit être en attente cardholder (WAITING_FOR_CARD / PIN /
  SIGNATURE). Si la carte a déjà été tapée, terminate est rejeté
  (réponse 422) et le paiement va à son terme.

## Mapping des erreurs

`_ERROR_CODES_FR` dans `sumup_service.py` mappe les codes SumUp aux
messages cashier :

| error_code | Message FR |
|---|---|
| `READER_BUSY` | Le TPE traite déjà un paiement — patientez ou redémarrez |
| `READER_OFFLINE` | TPE hors ligne — vérifiez le Wi-Fi/4G du Solo |
| `READER_NOT_FOUND` | TPE inconnu — vérifiez SUMUP_READER_ID |
| `CONFLICT` | Transaction pas remboursable dans son état actuel |
| `NOT_ENOUGH_BALANCE` | Solde SumUp insuffisant |
| `NOT_FOUND` | Transaction introuvable côté SumUp |

HTTP statuses génériques aussi traduits (401, 403, 404, 409, 422, 429, 5xx).

## PCI-DSS

`redact_sumup_error()` nettoie les payloads d'erreur avant persistance
ou logging :
- PAN (13-19 digits consécutifs) → `<PAN_REDACTED>`
- CVV/CVC/CSC → `<CVV_REDACTED>`
- Bearer tokens → `<TOKEN_REDACTED>`
- API keys (`sup_sk_…`, `sk_live_…`, etc.) → `<API_KEY_REDACTED>`
- JWT 3-segments → `<JWT_REDACTED>`

Conforme PCI-DSS req. 3 (interdiction stockage PAN/CVV en clair) et au
principe RGPD de minimisation.

## Affiliate Key (optionnel mais recommandé)

Pour activer la traçabilité avancée (récupérer un paiement par notre
UUID via `foreign_transaction_id`) :

1. Console SumUp → [Affiliate Keys](https://developer.sumup.com/affiliate-keys)
2. Créer une nouvelle Affiliate Key avec scope `payments`
3. Renseigner dans `/settings > Paiement` :
   - `SUMUP_AFFILIATE_APP_ID` = `fr.vintiz.pos` (libre, à mémoriser)
   - `SUMUP_AFFILIATE_KEY` = la clé fournie par SumUp

Sans ces deux valeurs, le service fonctionne quand même mais on perd la
capacité de récupérer un paiement orphelin via son foreign id.

## À ne jamais faire

❌ Confirmer une vente côté Vintiz sans avoir vu le checkout passer à PAID
   au polling — sinon les commandes peuvent ne pas matcher la base SumUp.

❌ Annuler un checkout déjà PAID (`cancel_checkout` refuse explicitement).

❌ Rembourser en cash un paiement CB sans appeler `refund_transaction`
   côté SumUp — c'est exactement le bug que ce code corrige.

❌ Logger ou persister le body d'erreur SumUp brut — toujours passer par
   `redact_sumup_error()`.

❌ Utiliser une clé `sup_sk_test_` en prod — le bandeau orange POS le
   signale, à honorer.
