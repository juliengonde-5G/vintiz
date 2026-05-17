package fr.vintiz.data.pos.dto

import com.squareup.moshi.JsonClass

/**
 * Aligné sur `apps/api/app/api/pos/router.py:CreateTransactionRequest`
 * et `pos.py:create_transaction`. Le champ `client_uuid` est la **clé
 * d'idempotence** générée côté Android avant chaque POST — replay safe.
 */
@JsonClass(generateAdapter = true)
data class CreateTransactionRequest(
    val items: List<TransactionItemDto>,
    val payments: List<PaymentDto>,
    val client_id: String? = null,
    val cashier_id: String? = null,
    val client_uuid: String,
    val coupon_code: String? = null,
)

@JsonClass(generateAdapter = true)
data class TransactionItemDto(
    val product_id: String? = null,
    val name: String? = null,
    val unit_price_cents: Long? = null,
    val quantity: Int = 1,
    val discount_percent: Int = 0,
)

@JsonClass(generateAdapter = true)
data class PaymentDto(
    val method: String,
    val amount_cents: Long,
    val sumup_checkout_id: String? = null,
    val cheque_ref: String? = null,
)

@JsonClass(generateAdapter = true)
data class TransactionResponse(
    val id: String,
    val total_cents: Long,
    val status: String,
    val client_uuid: String? = null,
)

/**
 * Backend (apps/api/app/api/pos/router.py:333-368) attend un body
 * `{opening_amount: float EUR, cashier_id?: UUID}` et renvoie
 * `{drawer_id: str, opening_amount: float}`. Pas de cents, pas de
 * status. Le close renvoie un payload détaillé avec totals_by_method
 * + expected/diff.
 */
@JsonClass(generateAdapter = true)
data class DrawerOpenRequest(
    val opening_amount: Double,
    val cashier_id: String? = null,
)

@JsonClass(generateAdapter = true)
data class DrawerCloseRequest(
    val closing_amount: Double,
    val cashier_id: String? = null,
)

@JsonClass(generateAdapter = true)
data class DrawerResponse(
    val drawer_id: String,
    val opening_amount: Double = 0.0,
    val closing_amount: Double? = null,
    val status: String? = null,
    val opened_at: String? = null,
    val closed_at: String? = null,
)
