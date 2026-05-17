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

        // Flag explicite posé par OnboardingScreen quand l'utilisateur
        // termine la dernière étape. Une réinstallation efface le flag
        // et relance l'onboarding.
        val startRoute = runBlocking {
            if (prefs.onboardingCompleted.first()) Routes.LOGIN else Routes.ONBOARDING
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
