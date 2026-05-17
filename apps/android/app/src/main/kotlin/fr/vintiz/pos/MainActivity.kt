package fr.vintiz.pos

import android.os.Bundle
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dagger.hilt.android.AndroidEntryPoint
import fr.vintiz.core.datastore.AppPreferences
import fr.vintiz.core.design.VzTheme
import fr.vintiz.core.security.TokenStorage
import fr.vintiz.hardware.scanner.hid.HidScanner
import fr.vintiz.pos.nav.Routes
import fr.vintiz.pos.nav.VintizNavGraph
import fr.vintiz.pos.update.InAppUpdateManager
import javax.inject.Inject
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var hidScanner: HidScanner
    @Inject lateinit var prefs: AppPreferences
    @Inject lateinit var tokenStorage: TokenStorage

    private val updateManager by lazy { InAppUpdateManager(applicationContext) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Décision de la route initiale :
        // 1. Onboarding non terminé → ONBOARDING
        // 2. Sinon, JWT manager déjà stocké (EncryptedSharedPreferences
        //    Keystore) → CASHIER_PIN direct (rétention session — pas
        //    de re-saisie identifiants à chaque boot)
        // 3. Sinon → LOGIN
        val startRoute = runBlocking {
            when {
                !prefs.onboardingCompleted.first() -> Routes.ONBOARDING
                tokenStorage.getAccessToken().isNullOrBlank() -> Routes.LOGIN
                else -> Routes.CASHIER_PIN
            }
        }

        setContent {
            VzTheme { VintizNavGraph(startDestination = startRoute) }
        }
    }

    override fun onResume() {
        super.onResume()
        updateManager.checkAndPrompt(this)
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (hidScanner.feed(event)) return true
        return super.dispatchKeyEvent(event)
    }
}
