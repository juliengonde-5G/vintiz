package fr.vintiz.data.hardware

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.database.dao.HardwareConfigDao
import fr.vintiz.core.database.entity.HardwareConfigEntity
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import timber.log.Timber
import java.io.IOException

/**
 * Charge la config matériel persistée côté backend dans
 * `apps/api/data/hardware.json` et la cache localement Room (singleton)
 * pour que la caisse continue à imprimer même si le backend est down
 * au boot de l'app.
 */
class HardwareRepository(
    private val api: HardwareApi,
    private val dao: HardwareConfigDao,
    private val now: () -> Long = { System.currentTimeMillis() },
) {

    fun observe(): Flow<HardwareConfig?> = dao.observe().map { it?.toDomain() }

    suspend fun current(): HardwareConfig? = dao.current()?.toDomain()

    suspend fun syncFromApi(): VintizResult<HardwareConfig> = try {
        val dto = api.getConfig()
        val entity = dto.toEntity(now())
        dao.upsert(entity)
        VintizResult.Success(entity.toDomain())
    } catch (io: IOException) {
        Timber.i("hardware config offline — fallback Room cache")
        val cached = current()
        if (cached != null) VintizResult.Success(cached) else VintizResult.Failure(VintizError.Network)
    }

    suspend fun push(config: HardwareConfig): VintizResult<HardwareConfig> = try {
        val dto = config.toDto()
        val saved = api.setConfig(dto)
        val entity = saved.toEntity(now())
        dao.upsert(entity)
        VintizResult.Success(entity.toDomain())
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    }
}

data class HardwareConfig(
    val receiptPrinterHost: String?,
    val receiptPrinterPort: Int,
    val receiptPrinterUsb: Boolean,
    val labelPrinterHost: String?,
    val labelPrinterPort: Int,
    val drawerKickOnCash: Boolean,
    val drawerKickPin: Int,
    val drawerOnMs: Int,
    val drawerOffMs: Int,
)

internal fun HardwareConfigDto.toEntity(now: Long): HardwareConfigEntity = HardwareConfigEntity(
    receiptPrinterHost = receipt_printer.host,
    receiptPrinterPort = receipt_printer.port,
    receiptPrinterUsb = receipt_printer.connection == "usb",
    labelPrinterHost = label_printer.host,
    labelPrinterPort = label_printer.port,
    drawerKickOnCash = cash_drawer.kick_on_cash,
    drawerKickPin = cash_drawer.kick_pin,
    drawerOnMs = cash_drawer.on_time_ms,
    drawerOffMs = cash_drawer.off_time_ms,
    updatedAt = now,
)

internal fun HardwareConfigEntity.toDomain(): HardwareConfig = HardwareConfig(
    receiptPrinterHost = receiptPrinterHost,
    receiptPrinterPort = receiptPrinterPort,
    receiptPrinterUsb = receiptPrinterUsb,
    labelPrinterHost = labelPrinterHost,
    labelPrinterPort = labelPrinterPort,
    drawerKickOnCash = drawerKickOnCash,
    drawerKickPin = drawerKickPin,
    drawerOnMs = drawerOnMs,
    drawerOffMs = drawerOffMs,
)

internal fun HardwareConfig.toDto(): HardwareConfigDto = HardwareConfigDto(
    receipt_printer = ReceiptPrinterDto(
        connection = if (receiptPrinterUsb) "usb" else "network",
        host = receiptPrinterHost,
        port = receiptPrinterPort,
    ),
    label_printer = LabelPrinterDto(host = labelPrinterHost, port = labelPrinterPort),
    cash_drawer = CashDrawerDto(
        kick_on_cash = drawerKickOnCash,
        kick_pin = drawerKickPin,
        on_time_ms = drawerOnMs,
        off_time_ms = drawerOffMs,
    ),
)
