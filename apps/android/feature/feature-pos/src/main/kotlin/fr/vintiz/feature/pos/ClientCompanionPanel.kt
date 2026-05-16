package fr.vintiz.feature.pos

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import fr.vintiz.core.common.Money
import fr.vintiz.data.clients.ClientDto

/**
 * Panneau latéral fidélité affiché au POS dès qu'une cliente est
 * identifiée. Aligné sur les attendus `apps/web/src/components/...
 * ClientCompanion`  : points actuels, gain panier, rachat max 50 %.
 *
 * Pas d'appel à un endpoint dédié pour l'instant — le calcul gain
 * panier est local et indicatif (le backend retransforme au commit).
 */
@Composable
fun ClientCompanionPanel(
    client: ClientDto,
    cartSubtotalCents: Long,
    modifier: Modifier = Modifier,
) {
    val ratioCents = 100L // 1 € = 1 pt (1 pt = 100 cents)
    val gainPoints = (cartSubtotalCents / ratioCents).toInt()
    // Rachat max : 50 % du panier en euros, 1 pt = 0,10 €.
    val maxRedeemPoints = ((cartSubtotalCents / 2) / 10L).coerceAtMost(client.loyalty_points.toLong()).toInt()

    Card(modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                "${client.first_name} ${client.last_name.uppercase()}",
                style = MaterialTheme.typography.titleLarge,
            )
            Text(
                client.membership_number ?: client.email ?: client.phone ?: "—",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(4.dp))
            Row {
                Text("Points actuels", modifier = Modifier.weight(1f))
                Text("${client.loyalty_points}",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary)
            }
            Row {
                Text("Gain sur ce panier", modifier = Modifier.weight(1f))
                Text("+ $gainPoints", style = MaterialTheme.typography.titleMedium)
            }
            if (cartSubtotalCents > 0 && client.loyalty_points > 0) {
                Row {
                    Text("Rachat max (50 % panier)",
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.bodyMedium)
                    Text(
                        "$maxRedeemPoints pts (${Money(maxRedeemPoints * 10L).format()})",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
            client.loyalty_tier?.takeIf { it.isNotBlank() }?.let { tier ->
                Spacer(Modifier.height(4.dp))
                Text("Tier : $tier", style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}
