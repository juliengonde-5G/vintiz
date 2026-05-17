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
 * Tab "Boutique" — Sprint A stub.
 *
 * À livrer au Sprint B : hero adresse + horaires + météo, stories
 * curation hebdo, catalogue, fiche produit, agenda événements.
 */
@Composable
fun BoutiqueHomeScreen() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Top,
    ) {
        Text(
            text = "Boutique",
            style = MaterialTheme.typography.headlineMedium,
        )
        Spacer(Modifier.height(16.dp))
        Text(
            text = "Vitrine, catalogue, horaires : à venir au Sprint B.",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
