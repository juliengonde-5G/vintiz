package fr.vintiz.feature.loyalty

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.text.KeyboardOptions
import androidx.hilt.navigation.compose.hiltViewModel
import fr.vintiz.core.common.Money

@Composable
fun LoyaltySubscribeScreen(
    onSubscribed: (cardId: String) -> Unit,
    viewModel: LoyaltySubscribeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.loadConfig() }

    state.createdCard?.let { card ->
        LaunchedEffect(card.id) { onSubscribed(card.id) }
    }

    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Adhésion fidélité", style = MaterialTheme.typography.headlineLarge)
            state.config?.let { cfg ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(
                            "Mode actuel : ${
                                when (cfg.mode) {
                                    "free" -> "Gratuite"
                                    "paid" -> "Payante (${Money(cfg.price_cents).format()})"
                                    "first_purchase" -> "Offerte au 1er achat (à partir de ${
                                        Money(cfg.threshold_cents).format()
                                    })"
                                    else -> cfg.mode
                                }
                            }",
                            style = MaterialTheme.typography.titleMedium,
                        )
                    }
                }
            }

            OutlinedTextField(
                value = state.firstName,
                onValueChange = viewModel::setFirstName,
                label = { Text("Prénom") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = state.lastName,
                onValueChange = viewModel::setLastName,
                label = { Text("Nom") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = state.email,
                onValueChange = viewModel::setEmail,
                label = { Text("Email") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = state.phone,
                onValueChange = viewModel::setPhone,
                label = { Text("Téléphone (optionnel)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                modifier = Modifier.fillMaxWidth(),
            )

            ConsentRow(
                checked = state.consentNewsletter,
                onToggle = viewModel::toggleNewsletter,
                label = "Newsletter (1-2 emails/mois)",
            )
            ConsentRow(
                checked = state.consentPersonalShopper,
                onToggle = viewModel::togglePersonalShopper,
                label = "Personal Shopper IA (recos basées sur les achats)",
            )
            ConsentRow(
                checked = state.consentTrendAlerts,
                onToggle = viewModel::toggleTrendAlerts,
                label = "Alertes tendance (produits matchant le goût)",
            )

            if (state.config?.mode == "paid") {
                Text("Méthode de paiement de l'adhésion :",
                    style = MaterialTheme.typography.titleSmall)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("cash" to "Espèces", "card" to "Carte").forEach { (key, label) ->
                        Button(
                            onClick = { viewModel.setPaymentMethod(key) },
                            enabled = state.paymentMethod != key,
                        ) { Text(label) }
                    }
                }
            }

            state.error?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
            }

            Button(
                onClick = viewModel::submit,
                enabled = !state.loading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (state.loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(20.dp),
                        strokeWidth = 2.dp,
                    )
                } else {
                    Text("Créer la carte")
                }
            }

            state.createdCard?.let { card ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("Carte créée ✓", style = MaterialTheme.typography.titleLarge,
                            color = MaterialTheme.colorScheme.primary)
                        Text("Numéro : ${card.membership_number}",
                            style = MaterialTheme.typography.headlineMedium)
                        Spacer(Modifier.height(4.dp))
                        Text("${card.first_name} ${card.last_name.uppercase()} — ${card.email}")
                    }
                }
            }
        }
    }
}

@Composable
private fun ConsentRow(checked: Boolean, onToggle: () -> Unit, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Checkbox(checked = checked, onCheckedChange = { onToggle() })
        Text(label, modifier = Modifier.weight(1f))
    }
}
