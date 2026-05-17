package fr.vintiz.data.hardware

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PUT

interface HardwareApi {

    @GET("api/hardware/config")
    suspend fun getConfig(): HardwareConfigDto

    @PUT("api/hardware/config")
    suspend fun setConfig(@Body body: HardwareConfigDto): HardwareConfigDto
}

@JsonClass(generateAdapter = true)
data class HardwareConfigDto(
    val receipt_printer: ReceiptPrinterDto,
    val label_printer: LabelPrinterDto,
    val cash_drawer: CashDrawerDto,
)

@JsonClass(generateAdapter = true)
data class ReceiptPrinterDto(
    val enabled: Boolean = true,
    val connection: String = "network",
    val host: String? = null,
    val port: Int = 9100,
)

@JsonClass(generateAdapter = true)
data class LabelPrinterDto(
    val enabled: Boolean = true,
    val host: String? = null,
    val port: Int = 9100,
)

@JsonClass(generateAdapter = true)
data class CashDrawerDto(
    val enabled: Boolean = true,
    val kick_on_cash: Boolean = true,
    val kick_pin: Int = 0,
    val on_time_ms: Int = 50,
    val off_time_ms: Int = 250,
)
