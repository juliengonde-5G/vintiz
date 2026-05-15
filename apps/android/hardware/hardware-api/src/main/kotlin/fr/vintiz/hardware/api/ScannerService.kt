package fr.vintiz.hardware.api

import kotlinx.coroutines.flow.Flow

/**
 * Lecture de codes-barres unifiée :
 * - implémentation HID (Inateck BCST-35) → capture `KeyEvent` au focus
 * - implémentation CameraX + ML Kit (fallback douchette HS / scan rayon)
 *
 * Le sélecteur d'impl vit dans Hilt et lit
 * [fr.vintiz.core.datastore.AppPreferences.cameraScannerEnabled].
 */
interface ScannerService {
    fun scans(): Flow<BarcodeScan>
}

data class BarcodeScan(
    val code: String,
    val format: BarcodeFormat,
    val source: ScanSource,
)

enum class BarcodeFormat { Code128, Ean13, Ean8, QrCode, Unknown }
enum class ScanSource { Hid, Camera }
