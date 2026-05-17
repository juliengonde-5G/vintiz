package fr.vintiz.feature.client.shell

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.data.authclient.ClientAuthRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Écran d'accueil du tab "Compte" — Sprint A stub.
 *
 * Affiche l'email authentifié + le numéro de carte fidélité persisté
 * par le flow magic-link. Les sections Wallet pass, coupons, historique
 * etc. sont câblées au Sprint C via `data-account`.
 */
@Composable
fun AccountHomeScreen(
    onLogout: () -> Unit,
    viewModel: AccountHomeViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Top,
    ) {
        Text(
            text = "Mon compte",
            style = MaterialTheme.typography.headlineMedium,
        )
        Spacer(Modifier.height(16.dp))
        Card(
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(
                    text = state.email ?: "—",
                    style = MaterialTheme.typography.titleMedium,
                )
                state.membershipNumber?.let { num ->
                    Spacer(Modifier.height(4.dp))
                    Text(
                        text = "Carte fidélité $num",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
        }
        Spacer(Modifier.height(16.dp))
        Text(
            text = "Sections fidélité, historique, RGPD : livrées au Sprint C.",
            style = MaterialTheme.typography.bodySmall,
        )
        Spacer(Modifier.height(32.dp))
        OutlinedButton(
            onClick = {
                viewModel.logout()
                onLogout()
            },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("Se déconnecter")
        }
    }
}

@HiltViewModel
class AccountHomeViewModel @Inject constructor(
    private val repo: ClientAuthRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(
        AccountHomeUiState(
            email = repo.currentEmail(),
            membershipNumber = repo.currentMembershipNumber(),
        ),
    )
    val state: StateFlow<AccountHomeUiState> = _state.asStateFlow()

    fun logout() {
        repo.logout()
    }
}

data class AccountHomeUiState(
    val email: String? = null,
    val membershipNumber: String? = null,
)
