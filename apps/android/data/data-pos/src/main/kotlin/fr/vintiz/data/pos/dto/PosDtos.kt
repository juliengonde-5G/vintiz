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

@JsonClass(generateAdapter = true)
data class DrawerOpenRequest(val opening_amount_cents: Long)

@JsonClass(generateAdapter = true)
data class DrawerCloseRequest(val closing_amount_cents: Long)

@JsonClass(generateAdapter = true)
data class DrawerResponse(
    val id: String,
    val status: String,
    val opening_amount_cents: Long,
    val closing_amount_cents: Long? = null,
)
