package fr.vintiz.hardware.scanner.hid

import android.view.KeyEvent
import fr.vintiz.domain.inventory.BarcodeNormalizer
import fr.vintiz.hardware.api.BarcodeFormat
import fr.vintiz.hardware.api.BarcodeScan
import fr.vintiz.hardware.api.ScannerService
import fr.vintiz.hardware.api.ScanSource
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * Capture les KeyEvent envoyés par la douchette Inateck BCST-35 (USB
 * HID = clavier). Les Activity / Compose Scaffold doivent appeler
 * [feed] depuis leur `dispatchKeyEvent` pour pousser les events ici.
 *
 * Le suffixe par défaut configurable côté douchette est `\n` (Enter) :
 * dès qu'on le reçoit, on émet le code accumulé après normalisation
 * (cf. BarcodeNormalizer — symétrique avec le backend).
 */
class HidScanner(
    private val terminator: Char = '\n',
    private val minLength: Int = 4,
) : ScannerService {

    private val flow = MutableSharedFlow<BarcodeScan>(
        replay = 0,
        extraBufferCapacity = 16,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )

    private val buffer = StringBuilder()

    /**
     * Appelée par l'host (Activity ou ComponentActivity) sur chaque
     * `KeyEvent`. Retourne `true` si l'event a été consommé (caractère
     * de barcode), `false` sinon — l'host peut alors le faire
     * remonter à la vue Compose.
     */
    fun feed(event: KeyEvent): Boolean {
        if (event.action != KeyEvent.ACTION_DOWN) return false
        if (event.unicodeChar == 0 && event.keyCode != KeyEvent.KEYCODE_ENTER) return false

        val ch = when (event.keyCode) {
            KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_NUMPAD_ENTER -> terminator
            else -> event.unicodeChar.toChar()
        }

        if (ch == terminator) {
            val code = BarcodeNormalizer.normalize(buffer.toString())
            buffer.setLength(0)
            if (code.length >= minLength) {
                flow.tryEmit(
                    BarcodeScan(code = code, format = guessFormat(code), source = ScanSource.Hid)
                )
                return true
            }
            return false
        }

        buffer.append(ch)
        return true
    }

    override fun scans(): Flow<BarcodeScan> = flow.asSharedFlow()

    private fun guessFormat(code: String): BarcodeFormat = when {
        code.length == 13 && code.all { it.isDigit() } -> BarcodeFormat.Ean13
        code.length == 8 && code.all { it.isDigit() } -> BarcodeFormat.Ean8
        else -> BarcodeFormat.Code128
    }
}
