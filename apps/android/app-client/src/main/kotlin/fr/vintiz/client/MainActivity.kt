package fr.vintiz.client

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dagger.hilt.android.AndroidEntryPoint
import fr.vintiz.client.nav.ClientRootNavGraph
import fr.vintiz.core.design.VzTheme
import fr.vintiz.core.security.ClientTokenStorage
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var clientTokenStorage: ClientTokenStorage

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Décision de la route initiale :
        // - JWT client déjà persisté → directement le shell
        // - Sinon → flow magic-link OTP
        val isAuthenticated = !clientTokenStorage.getAccessToken().isNullOrBlank()

        setContent {
            VzTheme {
                ClientRootNavGraph(startAuthenticated = isAuthenticated)
            }
        }
    }
}
