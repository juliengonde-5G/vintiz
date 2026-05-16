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

@Composable
fun PosScreen(
    onLogout: () -> Unit,
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
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(
                                    MaterialTheme.colorScheme.surfaceVariant,
                                    RoundedCornerShape(8.dp),
                                )
                                .padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(line.name, fontWeight = FontWeight.Medium)
                                Text(
                                    "${line.quantity} × ${line.unitPrice.format()}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            Text(line.lineTotal.format())
                            Spacer(Modifier.width(8.dp))
                            TextButton(onClick = { viewModel.removeLine(index) }) { Text("×") }
                        }
                    }
                }

                HorizontalDivider(Modifier.padding(vertical = 12.dp))

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

                Button(
                    onClick = {
                        when (state.selectedMethod) {
                            PaymentMethod.Cash -> viewModel.payCash(state.cart.subtotal.cents)
                            PaymentMethod.Card -> viewModel.payCard()
                            else -> { /* cheque / avoir à venir */ }
                        }
                    },
                    enabled = !state.cart.isEmpty && !state.paymentInProgress,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (state.paymentInProgress) "Paiement en cours…" else "Encaisser")
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
}

private fun PaymentMethod.label(): String = when (this) {
    PaymentMethod.Cash -> "Espèces"
    PaymentMethod.Card -> "CB"
    PaymentMethod.Cheque -> "Chèque"
    PaymentMethod.Credit -> "Avoir"
}
