package fr.vintiz.core.testing

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.hardware.api.PrinterService

class FakePrinterService(
    var ready: Boolean = true,
    var failOnPrint: VintizError? = null,
) : PrinterService {

    val printedPayloads = mutableListOf<ByteArray>()
    var drawerKicks: Int = 0
        private set

    override suspend fun isReady(): VintizResult<Boolean> =
        if (ready) VintizResult.Success(true) else VintizResult.Failure(VintizError.Network)

    override suspend fun printReceipt(bytes: ByteArray): VintizResult<Unit> {
        failOnPrint?.let { return VintizResult.Failure(it) }
        printedPayloads += bytes
        return VintizResult.Success(Unit)
    }

    override suspend fun openDrawer(): VintizResult<Unit> {
        drawerKicks++
        return VintizResult.Success(Unit)
    }
}
