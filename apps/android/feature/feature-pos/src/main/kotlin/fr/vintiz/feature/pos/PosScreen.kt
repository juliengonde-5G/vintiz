package fr.vintiz.feature.pos

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import fr.vintiz.core.common.Money
import fr.vintiz.domain.pos.PaymentMethod
import fr.vintiz.feature.receipt.ReceiptDialog

@Composable
fun PosScreen(
    viewModel: PosViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    Scaffold { padding ->
        Row(modifier = Modifier.fillMaxSize().padding(padding)) {
            // Colonne gauche : recherche + résultats
            Column(modifier = Modifier.weight(0.55f).fillMaxHeight().padding(16.dp)) {
                Text("Caisse", style = MaterialTheme.typography.headlineMedium)
                state.client?.let { c ->
                    Text(
                        "Cliente : ${c.first_name} ${c.last_name} • ${c.loyalty_points} pts",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = state.searchQuery,
                    onValueChange = viewModel::onSearchChange,
                    label = { Text("Chercher produit ou scanner") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(state.searchResults, key = { it.id }) { product ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp)),
                            onClick = { viewModel.addProduct(product) },
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth().padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(product.name, style = MaterialTheme.typography.titleMedium)
                                    Text(
                                        product.barcode ?: product.id.take(8),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Text(
                                    Money(product.price_cents).format(),
                                    style = MaterialTheme.typography.titleMedium,
                                )
                            }
                        }
                    }
                }
            }

            HorizontalDivider(
                modifier = Modifier.fillMaxHeight().width(1.dp),
                color = MaterialTheme.colorScheme.outlineVariant,
            )

            // Colonne droite : panier + paiement + companion
            Column(modifier = Modifier.weight(0.45f).fillMaxHeight().padding(16.dp)) {
                state.client?.let { c ->
                    ClientCompanionPanel(
                        client = c,
                        cartSubtotalCents = state.cart.subtotal.cents,
                    )
                    Spacer(Modifier.height(12.dp))
                }
                Text("Panier", style = MaterialTheme.typography.headlineMedium)
                Spacer(Modifier.height(12.dp))
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    items(state.cart.lines.size) { index ->
                        val line = state.cart.lines[index]
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(
                                    MaterialTheme.colorScheme.surfaceVariant,
                                    RoundedCornerShape(8.dp),
                                )
                                .padding(12.dp),
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(line.name, fontWeight = FontWeight.Medium)
                                    Text(
                                        "${line.quantity} × ${line.unitPrice.format()}" +
                                            if (line.discountPercent > 0)
                                                " · -${line.discountPercent}%" else "",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Text(line.lineTotal.format())
                                Spacer(Modifier.width(8.dp))
                                TextButton(onClick = { viewModel.removeLine(index) }) { Text("×") }
                            }
                            var showDiscount by remember { mutableStateOf(false) }
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                TextButton(onClick = { showDiscount = !showDiscount }) {
                                    Text(if (line.discountPercent > 0) "-${line.discountPercent}%" else "-%")
                                }
                                if (showDiscount) {
                                    listOf(0, 5, 10, 15, 20, 30).forEach { p ->
                                        AssistChip(
                                            onClick = {
                                                viewModel.applyDiscount(index, p)
                                                showDiscount = false
                                            },
                                            label = { Text(if (p == 0) "0" else "-$p%") },
                                        )
                                        Spacer(Modifier.width(4.dp))
                                    }
                                }
                            }
                        }
                    }
                }

                HorizontalDivider(Modifier.padding(vertical = 12.dp))

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    AssistChip(
                        onClick = viewModel::addBag,
                        label = { Text("+ Sac (0,20 €)") },
                    )
                }

                CouponBar(
                    code = state.couponCode,
                    preview = state.couponPreview,
                    onCodeChange = viewModel::onCouponCodeChange,
                    onValidate = viewModel::validateCoupon,
                    onClear = viewModel::clearCoupon,
                )

                Spacer(Modifier.height(8.dp))

                Row(modifier = Modifier.fillMaxWidth()) {
                    Text("Total", modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.titleLarge)
                    Text(
                        state.effectiveTotal.format(),
                        style = MaterialTheme.typography.headlineMedium,
                    )
                }

                if (state.pendingCreditCents > 0) {
                    Spacer(Modifier.height(4.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "Avoir appliqué : -${fr.vintiz.core.common.Money(state.pendingCreditCents).format()}",
                            modifier = Modifier.weight(1f),
                            color = MaterialTheme.colorScheme.primary,
                        )
                        TextButton(onClick = viewModel::clearPendingCredit) {
                            Text("Annuler avoir")
                        }
                    }
                    Row(modifier = Modifier.fillMaxWidth()) {
                        Text("Reste à payer", modifier = Modifier.weight(1f))
                        Text(state.remainingAfterCredit.format(),
                            style = MaterialTheme.typography.titleLarge,
                            color = MaterialTheme.colorScheme.primary)
                    }
                }

                Spacer(Modifier.height(16.dp))

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    PaymentMethod.entries.forEach { method ->
                        AssistChip(
                            onClick = { viewModel.pickPaymentMethod(method) },
                            label = { Text(method.label()) },
                        )
                    }
                }

                Spacer(Modifier.height(12.dp))

                var chequeDialog by remember { mutableStateOf(false) }
                var creditDialog by remember { mutableStateOf(false) }
                var cashDialog by remember { mutableStateOf(false) }

                Button(
                    onClick = {
                        when (state.selectedMethod) {
                            PaymentMethod.Cash -> cashDialog = true
                            PaymentMethod.Card -> viewModel.payCard()
                            PaymentMethod.Cheque -> chequeDialog = true
                            PaymentMethod.Credit -> creditDialog = true
                        }
                    },
                    enabled = !state.cart.isEmpty && !state.paymentInProgress,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (state.paymentInProgress) "Paiement en cours…" else "Encaisser")
                }

                if (cashDialog) {
                    CashTenderDialog(
                        totalCents = state.remainingAfterCredit.cents,
                        onConfirm = { tendered ->
                            cashDialog = false
                            viewModel.payCash(tendered)
                        },
                        onDismiss = { cashDialog = false },
                    )
                }

                if (chequeDialog) {
                    ChequeDialog(
                        onConfirm = { ref ->
                            chequeDialog = false
                            viewModel.payCheque(ref)
                        },
                        onDismiss = { chequeDialog = false },
                    )
                }
                if (creditDialog) {
                    CreditDialog(
                        defaultAmountCents = state.effectiveTotal.cents,
                        clientLabel = state.client?.let {
                            "${it.first_name} ${it.last_name} (${it.loyalty_points} pts)"
                        },
                        onConfirm = { amount ->
                            creditDialog = false
                            viewModel.payCredit(amount)
                        },
                        onDismiss = { creditDialog = false },
                    )
                }

                state.error?.let { err ->
                    Spacer(Modifier.height(8.dp))
                    Text(err, color = MaterialTheme.colorScheme.error)
                }

                state.lastTransactionId?.let {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Vente OK — ticket $it",
                        color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    if (state.lastChange.cents > 0) {
                        Text(
                            "Rendu monnaie : ${state.lastChange.format()}",
                            style = MaterialTheme.typography.titleMedium,
                        )
                    }
                }
            }
        }
    }

    // Modal ticket post-vente — s'ouvre dès qu'une transaction vient
    // d'être validée. Le ReceiptViewModel injecté est un autre Hilt
    // ViewModel : il télécharge les bytes ESC/POS pré-signés serveur
    // et les envoie à l'imprimante MUNBYN (USB ou TCP selon config).
    // Le kick tiroir est automatique si la vente était en espèces.
    state.lastTransactionId?.let { txId ->
        ReceiptDialog(
            transactionId = txId,
            paidByCash = state.lastPaidByCash,
            onDismiss = viewModel::dismissReceipt,
        )
    }
}

private fun PaymentMethod.label(): String = when (this) {
    PaymentMethod.Cash -> "Espèces"
    PaymentMethod.Card -> "CB"
    PaymentMethod.Cheque -> "Chèque"
    PaymentMethod.Credit -> "Avoir"
}

@Composable
private fun ChequeDialog(onConfirm: (String) -> Unit, onDismiss: () -> Unit) {
    var ref by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Paiement chèque") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Numéro / référence du chèque (banque + n°).",
                    style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(
                    value = ref,
                    onValueChange = { ref = it },
                    label = { Text("Référence") },
                    singleLine = true,
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(ref) },
                enabled = ref.isNotBlank(),
            ) { Text("Valider") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Annuler") } },
    )
}

@Composable
private fun CreditDialog(
    defaultAmountCents: Long,
    clientLabel: String?,
    onConfirm: (Long) -> Unit,
    onDismiss: () -> Unit,
) {
    var input by remember { mutableStateOf(String.format("%.2f", defaultAmountCents / 100.0).replace(",", ".")) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Paiement par avoir") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(clientLabel ?: "Cliente non identifiée — sélectionner d'abord.",
                    style = MaterialTheme.typography.bodyMedium)
                Text("Solde réel vérifié côté serveur. Si insuffisant, refus.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it.replace(",", ".").filter { c -> c.isDigit() || c == '.' } },
                    label = { Text("Montant (€)") },
                    singleLine = true,
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val cents = (input.toDoubleOrNull()?.times(100))?.toLong() ?: 0L
                    onConfirm(cents)
                },
                enabled = clientLabel != null && (input.toDoubleOrNull() ?: 0.0) > 0.0,
            ) { Text("Valider") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Annuler") } },
    )
}

@Composable
private fun CashTenderDialog(
    totalCents: Long,
    onConfirm: (Long) -> Unit,
    onDismiss: () -> Unit,
) {
    val totalEur = totalCents / 100.0
    var tendered by remember(totalCents) {
        mutableStateOf(String.format("%.2f", totalEur).replace(",", "."))
    }
    val tenderedEur = tendered.replace(",", ".").toDoubleOrNull() ?: 0.0
    val changeEur = tenderedEur - totalEur
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Paiement espèces") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Total : %.2f €".format(totalEur),
                    style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(
                    value = tendered,
                    onValueChange = {
                        tendered = it.replace(",", ".").filter { c -> c.isDigit() || c == '.' }
                    },
                    label = { Text("Montant reçu (€)") },
                    singleLine = true,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    listOf(5.0, 10.0, 20.0, 50.0).forEach { p ->
                        AssistChip(
                            onClick = {
                                val v = kotlin.math.ceil(totalEur / p) * p
                                tendered = String.format("%.2f", v).replace(",", ".")
                            },
                            label = { Text("%.0f €".format(p)) },
                        )
                    }
                    AssistChip(
                        onClick = {
                            tendered = String.format("%.2f", totalEur).replace(",", ".")
                        },
                        label = { Text("Compte") },
                    )
                }
                when {
                    tenderedEur < totalEur -> Text(
                        "Manque %.2f €".format(totalEur - tenderedEur),
                        color = MaterialTheme.colorScheme.error,
                    )
                    changeEur > 0.0 -> Text(
                        "Rendu : %.2f €".format(changeEur),
                        style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    else -> Text("Compte juste", color = MaterialTheme.colorScheme.primary)
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm((tenderedEur * 100).toLong()) },
                enabled = tenderedEur >= totalEur,
            ) { Text("Valider") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Annuler") } },
    )
}
