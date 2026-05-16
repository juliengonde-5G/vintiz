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
        _state.update { it.copy(client = client) }
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

    fun payCash(tenderedCents: Long) {
        val total = _state.value.cart.subtotal
        val tendered = Money(tenderedCents)
        if (tendered.cents < total.cents) {
            _state.update { it.copy(error = "Montant insuffisant") }
            return
        }
        val split = PaymentSplit(total).add(PaymentLeg(PaymentMethod.Cash, total))
        commit(split, change = split.computeChange(tendered))
    }

    fun payCard() {
        val total = _state.value.cart.subtotal
        if (total.cents <= 0) return
        val foreignTxId = UUID.randomUUID().toString()
        _state.update { it.copy(paymentInProgress = true) }
        viewModelScope.launch {
            val outcome = terminal.pay(total, foreignTxId, "Vente Vintiz")
            when (outcome) {
                is PaymentOutcome.Paid -> {
                    val split = PaymentSplit(total).add(
                        PaymentLeg(PaymentMethod.Card, total, checkoutId = outcome.checkoutId)
                    )
                    commit(split, change = Money.ZERO)
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

    private fun commit(split: PaymentSplit, change: Money) {
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
        )
        viewModelScope.launch {
            when (val r = pos.commit(req)) {
                is VintizResult.Success -> _state.update {
                    PosUiState(lastTransactionId = r.value.id, lastChange = change)
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
    val lastTransactionId: String? = null,
    val lastChange: Money = Money.ZERO,
    val error: String? = null,
)

