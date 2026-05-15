package fr.vintiz.hardware.scanner.camera

import android.annotation.SuppressLint
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import fr.vintiz.domain.inventory.BarcodeNormalizer
import fr.vintiz.hardware.api.BarcodeFormat
import fr.vintiz.hardware.api.BarcodeScan
import fr.vintiz.hardware.api.ScanSource
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import timber.log.Timber

/**
 * Fallback scan camera quand la douchette HID est indisponible.
 * Configuré via AppPreferences.cameraScannerEnabled = true. L'app pose
 * cet analyzer sur l'`ImageAnalysis` CameraX et observe le Flow.
 *
 * Throttle interne : on n'émet pas deux fois le même code en moins de
 * [debounceMs] millisecondes pour éviter les doublons lors du scan
 * continu d'un même produit posé devant la caméra.
 */
class CameraBarcodeAnalyzer(
    private val debounceMs: Long = 800L,
    private val now: () -> Long = { System.currentTimeMillis() },
) : ImageAnalysis.Analyzer {

    private val options = BarcodeScannerOptions.Builder()
        .setBarcodeFormats(
            Barcode.FORMAT_CODE_128,
            Barcode.FORMAT_EAN_13,
            Barcode.FORMAT_EAN_8,
            Barcode.FORMAT_QR_CODE,
        )
        .build()
    private val scanner = BarcodeScanning.getClient(options)

    private val flow = MutableSharedFlow<BarcodeScan>(
        replay = 0,
        extraBufferCapacity = 4,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )

    private var lastCode: String? = null
    private var lastEmit: Long = 0L

    fun scans(): Flow<BarcodeScan> = flow.asSharedFlow()

    @SuppressLint("UnsafeOptInUsageError")
    @OptIn(ExperimentalGetImage::class)
    override fun analyze(image: ImageProxy) {
        val media = image.image
        if (media == null) {
            image.close()
            return
        }
        val input = InputImage.fromMediaImage(media, image.imageInfo.rotationDegrees)
        scanner.process(input)
            .addOnSuccessListener { barcodes ->
                for (b in barcodes) {
                    val raw = b.rawValue ?: continue
                    val code = BarcodeNormalizer.normalize(raw)
                    if (code.isEmpty()) continue
                    val n = now()
                    if (code == lastCode && (n - lastEmit) < debounceMs) continue
                    lastCode = code
                    lastEmit = n
                    flow.tryEmit(BarcodeScan(code, mapFormat(b.format), ScanSource.Camera))
                }
            }
            .addOnFailureListener { Timber.w(it, "ML Kit scan KO") }
            .addOnCompleteListener { image.close() }
    }

    private fun mapFormat(mlFormat: Int): BarcodeFormat = when (mlFormat) {
        Barcode.FORMAT_EAN_13 -> BarcodeFormat.Ean13
        Barcode.FORMAT_EAN_8 -> BarcodeFormat.Ean8
        Barcode.FORMAT_QR_CODE -> BarcodeFormat.QrCode
        Barcode.FORMAT_CODE_128 -> BarcodeFormat.Code128
        else -> BarcodeFormat.Unknown
    }
}
