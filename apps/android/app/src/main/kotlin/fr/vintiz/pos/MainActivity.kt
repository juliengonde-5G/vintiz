package fr.vintiz.pos

import android.os.Bundle
import android.view.KeyEvent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import dagger.hilt.android.AndroidEntryPoint
import fr.vintiz.core.design.VzTheme
import fr.vintiz.hardware.scanner.hid.HidScanner
import fr.vintiz.pos.nav.VintizNavGraph
import fr.vintiz.pos.update.InAppUpdateManager
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var hidScanner: HidScanner

    private val updateManager by lazy { InAppUpdateManager(applicationContext) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            VzTheme { VintizNavGraph() }
        }
    }

    override fun onResume() {
        super.onResume()
        updateManager.checkAndPrompt(this)
    }

    /**
     * La douchette Inateck arrive en KeyEvent. On laisse [HidScanner]
     * accumuler ; il retourne true quand un code complet vient d'être
     * émis sur son SharedFlow.
     */
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (hidScanner.feed(event)) return true
        return super.dispatchKeyEvent(event)
    }
}
