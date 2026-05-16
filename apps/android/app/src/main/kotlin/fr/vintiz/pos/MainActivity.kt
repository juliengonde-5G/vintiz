package fr.vintiz.pos

import android.os.Bundle
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dagger.hilt.android.AndroidEntryPoint
import fr.vintiz.core.datastore.AppPreferences
import fr.vintiz.core.design.VzTheme
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

    private val updateManager by lazy { InAppUpdateManager(applicationContext) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Décision synchrone (cheap sur DataStore en mémoire) :
        // si la clé environment n'a jamais été posée, on lance l'onboarding.
        val startRoute = runBlocking {
            val env = prefs.environment.first()
            // Heuristic : si on a déjà posé un backend explicite, on suppose
            // que l'onboarding a déjà été parcouru. Sinon, première install.
            val backend = prefs.printerBackend.first()
            if (env.key == "dev" && backend.key == "network") Routes.ONBOARDING
            else Routes.LOGIN
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
