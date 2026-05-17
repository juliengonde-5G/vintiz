package fr.vintiz.feature.client.shell

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * Tab "Shopper" — Sprint A stub.
 *
 * À livrer au Sprint C/D : gate consent profilage, recherche sémantique
 * Claude Haiku, alertes tendance, try-on Claude Vision, lookbooks.
 */
@Composable
fun ShopperHomeScreen() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Top,
    ) {
        Text(
            text = "Personal Shopper",
            style = MaterialTheme.typography.headlineMedium,
        )
        Spacer(Modifier.height(16.dp))
        Text(
            text = "Recommandations IA, alertes tendance, try-on : à venir aux Sprints C–D.",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
