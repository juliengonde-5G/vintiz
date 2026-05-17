package fr.vintiz.feature.pos

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.Money
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.clients.ClientDto
import fr.vintiz.data.clients.ClientsRepository
import fr.vintiz.data.inventory.InventoryRepository
import fr.vintiz.data.inventory.ProductDto
import fr.vintiz.data.loyalty.CouponPreviewDto
import fr.vintiz.data.loyalty.LoyaltyRepository
import fr.vintiz.data.personalshopper.PersonalShopperRepository
import fr.vintiz.data.personalshopper.PosCompanionDto
import fr.vintiz.data.pos.PosRepository
import fr.vintiz.data.pos.dto.CreateTransactionRequest
import fr.vintiz.data.pos.dto.PaymentDto
import fr.vintiz.data.pos.dto.TransactionItemDto
import fr.vintiz.domain.inventory.BarcodeNormalizer
import fr.vintiz.domain.pos.Cart
import fr.vintiz.domain.pos.CartLine
import fr.vintiz.domain.pos.PaymentLeg
import fr.vintiz.domain.pos.PaymentMethod
import fr.vintiz.domain.pos.PaymentSplit
import fr.vintiz.hardware.api.NfcService
import fr.vintiz.hardware.api.PaymentOutcome
import fr.vintiz.hardware.api.PaymentTerminalService
import fr.vintiz.hardware.api.ScannerService
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

@HiltViewModel
class PosViewModel @Inject constructor(
    private val inventory: InventoryRepository,
    private val clients: ClientsRepository,
    private val pos: PosRepository,
    private val loyalty: LoyaltyRepository,
    private val personalShopper: PersonalShopperRepository,
    private val terminal: PaymentTerminalService,
    private val scanner: ScannerService,
    private val nfc: NfcService,
) : ViewModel() {

    private val _state = MutableStateFlow(PosUiState())
    val state: StateFlow<PosUiState> = _state.asStateFlow()

    init {
        // Tout scan code-barres (HID ou caméra) ajoute le produit au panier.
        scanner.scans()
            .onEach { onBarcodeScanned(it.code) }
            .launchIn(viewModelScope)

        // Tap NFC → résolution carte fidélité.
        nfc.tags()
            .onEach { tag -> resolveNfc(tag.uid) }
            .launchIn(viewModelScope)
    }

    fun onSearchChange(q: String) {
        _state.update { it.copy(searchQuery = q) }
        if (q.length < 2) {
            _state.update { it.copy(searchResults = emptyList()) }
            return
        }
        viewModelScope.launch {
            when (val r = inventory.search(q)) {
                is VintizResult.Success -> _state.update { it.copy(searchResults = r.value) }
                is VintizResult.Failure -> _state.update { it.copy(error = r.error.message) }
            }
        }
    }

    /** Appelée par le HID scanner ET le scan caméra ET la doublure de saisie manuelle. */
    fun onBarcodeScanned(raw: String) {
        val normalized = BarcodeNormalizer.normalize(raw)
        if (normalized.isEmpty()) return
        viewModelScope.launch {
            when (val r = inventory.byBarcode(normalized)) {
                is VintizResult.Success -> addProduct(r.value)
                is VintizResult.Failure -> _state.update {
                    it.copy(error = "Code-barres non reconnu : $normalized")
                }
            }
        }
    }

    private fun resolveNfc(uid: String) {
        viewModelScope.launch {
            when (val r = clients.byNfcUid(uid)) {
                is VintizResult.Success -> selectClient(r.value)
                is VintizResult.Failure -> _state.update {
                    it.copy(error = "Carte non reconnue : $uid")
                }
            }
        }
    }

    fun addProduct(p: ProductDto) {
        _state.update {
            it.copy(
                cart = it.cart.add(
                    CartLine(
                        productId = p.id,
                        name = p.name,
                        unitPrice = Money(p.price_cents),
                    )
                ),
                searchQuery = "",
                searchResults = emptyList(),
                error = null,
            )
        }
    }

    fun removeLine(index: Int) {
        _state.update { it.copy(cart = it.cart.removeAt(index)) }
    }

    fun updateQuantity(index: Int, qty: Int) {
        if (qty < 1) return
        _state.update {
            it.copy(cart = it.cart.updateAt(index) { line -> line.copy(quantity = qty) })
        }
    }

    fun applyDiscount(index: Int, percent: Int) {
        if (percent !in 0..100) return
        _state.update {
            it.copy(cart = it.cart.updateAt(index) { line -> line.copy(discountPercent = percent) })
        }
    }

    fun selectClient(client: ClientDto?) {
        _state.update { it.copy(client = client, companion = null) }
        if (client != null) refreshCompanion()
    }

    /**
     * Recharge le panneau Companion (gain points, coupons appliquables,
     * alertes RFM, upsells) à chaque évolution du panier ou changement
     * de client. Tolérant aux erreurs : un Companion KO n'empêche pas
     * la vente.
     */
    fun refreshCompanion() {
        val clientId = _state.value.client?.id ?: return
        viewModelScope.launch {
            val productIds = _state.value.cart.lines.mapNotNull { it.productId }
            when (val r = personalShopper.companion(
                clientId = clientId,
                cartTotalCents = _state.value.cart.subtotal.cents,
                items = productIds,
            )) {
                is VintizResult.Success -> _state.update { it.copy(companion = r.value) }
                is VintizResult.Failure -> _state.update {
                    it.copy(companion = null, companionError = r.error.message)
                }
            }
        }
    }

    fun trackCompanionClick(productId: String) {
        val clientId = _state.value.client?.id ?: return
        viewModelScope.launch { personalShopper.logClick(clientId, productId) }
    }

    /**
     * Fermeture de la modal ticket post-vente — efface le
     * `lastTransactionId` pour que le PosScreen retrouve un panier
     * vide prêt pour la vente suivante.
     */
    fun dismissReceipt() {
        _state.value = PosUiState()
    }

    fun lookupClient(q: String) {
        if (q.isBlank()) return
        viewModelScope.launch {
            when (val r = clients.identify(q)) {
                is VintizResult.Success -> _state.update { it.copy(clientCandidates = r.value) }
                is VintizResult.Failure -> _state.update { it.copy(error = r.error.message) }
            }
        }
    }

    fun pickPaymentMethod(method: PaymentMethod) {
        _state.update { it.copy(selectedMethod = method) }
    }

    fun onCouponCodeChange(v: String) {
        _state.update { it.copy(couponCode = v.uppercase().trim(), couponPreview = null, error = null) }
    }

    fun validateCoupon() {
        val code = _state.value.couponCode
        val total = _state.value.cart.subtotal.cents
        if (code.isBlank() || total <= 0) return
        viewModelScope.launch {
            when (val r = loyalty.validateCoupon(code, total, _state.value.client?.id)) {
                is VintizResult.Success -> _state.update { it.copy(couponPreview = r.value) }
                is VintizResult.Failure -> _state.update {
                    it.copy(couponPreview = null, error = r.error.message)
                }
            }
        }
    }

    fun clearCoupon() {
        _state.update { it.copy(couponCode = "", couponPreview = null) }
    }

    /**
     * Reste à payer après application du `pendingCreditCents` (jambe
     * avoir partielle). Si pas de pending credit → effectiveTotal.
     */
    private val remainingTotal: Money
        get() = Money(
            (_state.value.effectiveTotal.cents - _state.value.pendingCreditCents)
                .coerceAtLeast(0)
        )

    /** Construit un PaymentSplit qui intègre le pendingCredit si présent. */
    private fun splitWithPendingCredit(secondLeg: PaymentLeg): PaymentSplit {
        val total = _state.value.effectiveTotal
        val split = PaymentSplit(total)
        val pending = _state.value.pendingCreditCents
        return if (pending > 0) {
            split.add(PaymentLeg(PaymentMethod.Credit, Money(pending))).add(secondLeg)
        } else {
            split.add(secondLeg)
        }
    }

    fun payCash(tenderedCents: Long) {
        val remaining = remainingTotal
        val tendered = Money(tenderedCents)
        if (tendered.cents < remaining.cents) {
            _state.update { it.copy(error = "Montant insuffisant") }
            return
        }
        val split = splitWithPendingCredit(PaymentLeg(PaymentMethod.Cash, remaining))
        commit(split, change = Money(tendered.cents - remaining.cents), paidByCash = true)
    }

    fun payCard() {
        val remaining = remainingTotal
        if (remaining.cents <= 0) return
        val foreignTxId = UUID.randomUUID().toString()
        _state.update { it.copy(paymentInProgress = true) }
        viewModelScope.launch {
            val outcome = terminal.pay(remaining, foreignTxId, "Vente Vintiz")
            when (outcome) {
                is PaymentOutcome.Paid -> {
                    val split = splitWithPendingCredit(
                        PaymentLeg(PaymentMethod.Card, remaining, checkoutId = outcome.checkoutId),
                    )
                    commit(split, change = Money.ZERO, paidByCash = false)
                }
                is PaymentOutcome.Declined -> _state.update {
                    it.copy(paymentInProgress = false, error = "Paiement refusé : ${outcome.reason}")
                }
                is PaymentOutcome.Cancelled -> _state.update {
                    it.copy(paymentInProgress = false, error = "Paiement annulé")
                }
                is PaymentOutcome.Failed -> _state.update {
                    it.copy(paymentInProgress = false, error = outcome.message)
                }
            }
        }
    }

    /**
     * Paiement chèque — la référence (n° du chèque + banque éventuelle)
     * est journalisée sur le PaymentLeg mais ne contraint pas le commit.
     * Le serveur valide le format si une regex est configurée.
     */
    fun payCheque(reference: String) {
        val remaining = remainingTotal
        if (remaining.cents <= 0) return
        val ref = reference.trim()
        if (ref.isBlank()) {
            _state.update { it.copy(error = "Référence chèque requise") }
            return
        }
        val split = splitWithPendingCredit(
            PaymentLeg(PaymentMethod.Cheque, remaining, chequeRef = ref),
        )
        commit(split, change = Money.ZERO, paidByCash = false)
    }

    /**
     * Annule la jambe avoir en cours (revient à un panier classique).
     */
    fun clearPendingCredit() = _state.update { it.copy(pendingCreditCents = 0L, error = null) }

    /**
     * Paiement par avoir (store credit). Si le montant couvre le total,
     * on commit directement. Sinon, on stocke la jambe avoir dans
     * `pendingCreditCents` et le caissier complète avec cash/CB/chèque
     * sur le `remainingTotal` qui devient visible dans l'UI.
     */
    fun payCredit(amountCents: Long) {
        val total = _state.value.effectiveTotal
        if (total.cents <= 0) return
        if (_state.value.client == null) {
            _state.update { it.copy(error = "Cliente requise pour utiliser un avoir") }
            return
        }
        val amount = Money(amountCents.coerceIn(0, total.cents))
        if (amount.cents <= 0) {
            _state.update { it.copy(error = "Montant avoir invalide") }
            return
        }
        if (amount.cents < total.cents) {
            // Multi-leg : on stocke l'avoir partiel, l'UI affichera
            // "Reste à payer" sur la ligne Encaisser.
            _state.update {
                it.copy(
                    pendingCreditCents = amount.cents,
                    error = null,
                    selectedMethod = PaymentMethod.Cash,
                )
            }
            return
        }
        val split = PaymentSplit(total).add(PaymentLeg(PaymentMethod.Credit, amount))
        commit(split, change = Money.ZERO, paidByCash = false)
    }

    private fun commit(split: PaymentSplit, change: Money, paidByCash: Boolean) {
        val cart = _state.value.cart
        if (cart.isEmpty) return
        val req = CreateTransactionRequest(
            items = cart.lines.map {
                TransactionItemDto(
                    product_id = it.productId,
                    name = it.name,
                    unit_price_cents = it.unitPrice.cents,
                    quantity = it.quantity,
                    discount_percent = it.discountPercent,
                )
            },
            payments = split.legs.map {
                PaymentDto(
                    method = it.method.name.lowercase(),
                    amount_cents = it.amount.cents,
                    sumup_checkout_id = it.checkoutId,
                    cheque_ref = it.chequeRef,
                )
            },
            client_id = _state.value.client?.id,
            client_uuid = UUID.randomUUID().toString(),
            coupon_code = _state.value.couponPreview?.code,
        )
        viewModelScope.launch {
            when (val r = pos.commit(req)) {
                is VintizResult.Success -> _state.update {
                    PosUiState(
                        lastTransactionId = r.value.id,
                        lastChange = change,
                        lastPaidByCash = paidByCash,
                    )
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(
                        paymentInProgress = false,
                        error = "Vente enregistrée hors-ligne — sera renvoyée plus tard",
                    )
                }
            }
        }
    }
}

data class PosUiState(
    val cart: Cart = Cart(),
    val searchQuery: String = "",
    val searchResults: List<ProductDto> = emptyList(),
    val client: ClientDto? = null,
    val clientCandidates: List<ClientDto> = emptyList(),
    val selectedMethod: PaymentMethod = PaymentMethod.Cash,
    val paymentInProgress: Boolean = false,
    val couponCode: String = "",
    val couponPreview: CouponPreviewDto? = null,
    val companion: PosCompanionDto? = null,
    val companionError: String? = null,
    val lastTransactionId: String? = null,
    val lastChange: Money = Money.ZERO,
    val lastPaidByCash: Boolean = false,
    /** Jambe avoir partielle déjà acceptée, en attente d'une 2e méthode. */
    val pendingCreditCents: Long = 0L,
    val error: String? = null,
) {
    /**
     * Total panier ajusté par le coupon **côté affichage uniquement**.
     * Le serveur recalcule au commit et fait foi (NF525).
     */
    val effectiveTotal: Money
        get() = couponPreview?.let { Money(it.new_total_cents) } ?: cart.subtotal

    /** Reste à payer pour la 2e méthode quand un avoir partiel est posé. */
    val remainingAfterCredit: Money
        get() = Money((effectiveTotal.cents - pendingCreditCents).coerceAtLeast(0))
}

