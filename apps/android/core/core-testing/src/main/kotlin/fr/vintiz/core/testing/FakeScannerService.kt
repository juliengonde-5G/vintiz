package fr.vintiz.core.testing

import fr.vintiz.hardware.api.BarcodeFormat
import fr.vintiz.hardware.api.BarcodeScan
import fr.vintiz.hardware.api.ScanSource
import fr.vintiz.hardware.api.ScannerService
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow

class FakeScannerService : ScannerService {
    private val flow = MutableSharedFlow<BarcodeScan>(replay = 0, extraBufferCapacity = 16)
    override fun scans(): Flow<BarcodeScan> = flow.asSharedFlow()

    suspend fun emit(code: String, format: BarcodeFormat = BarcodeFormat.Code128, source: ScanSource = ScanSource.Hid) {
        flow.emit(BarcodeScan(code, format, source))
    }
}
