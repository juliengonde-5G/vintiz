package fr.vintiz.data.reports

import com.squareup.moshi.JsonClass
import retrofit2.http.GET
import retrofit2.http.Query

interface ReportsApi {

    @GET("api/reports/dashboard")
    suspend fun dashboard(): DashboardDto

    @GET("api/reports/retail-kpis")
    suspend fun retailKpis(@Query("period_days") periodDays: Int = 30): RetailKpisDto

    @GET("api/reports/daily")
    suspend fun daily(@Query("date") date: String? = null): DailyRecapDto

    @GET("api/pos/z-reports")
    suspend fun zReports(
        @Query("from") from: String? = null,
        @Query("to") to: String? = null,
    ): List<ZReportDto>

    @GET("api/admin/fiscal-export")
    suspend fun fiscalExport(
        @Query("from") from: String,
        @Query("to") to: String,
        @Query("format") format: String = "json",
    ): FiscalExportDto
}

@JsonClass(generateAdapter = true)
data class DashboardDto(
    val today_revenue_cents: Long,
    val today_transactions: Int,
    val today_average_cart_cents: Long,
    val stock_value_cents: Long,
    val top_products: List<TopProductDto> = emptyList(),
    val weather: WeatherDto? = null,
)

@JsonClass(generateAdapter = true)
data class TopProductDto(
    val product_id: String,
    val name: String,
    val sold_quantity: Int,
    val revenue_cents: Long,
)

@JsonClass(generateAdapter = true)
data class WeatherDto(
    val temperature_c: Double,
    val description: String,
    val icon: String? = null,
)

@JsonClass(generateAdapter = true)
data class RetailKpisDto(
    val period_days: Int,
    val sell_through_rate: Double,
    val gmroi: Double,
    val average_inventory_turnover_days: Double,
    val revenue_per_sqm_per_month_cents: Long,
)

@JsonClass(generateAdapter = true)
data class DailyRecapDto(
    val date: String,
    val revenue_cents: Long,
    val transaction_count: Int,
    val payment_split: Map<String, Long>,
)

@JsonClass(generateAdapter = true)
data class ZReportDto(
    val id: String,
    val drawer_id: String,
    val opened_at: String,
    val closed_at: String,
    val opening_amount_cents: Long,
    val closing_amount_cents: Long,
    val expected_cents: Long,
    val diff_cents: Long,
    val total_cash_cents: Long,
    val total_card_cents: Long,
    val total_cheque_cents: Long,
)

@JsonClass(generateAdapter = true)
data class FiscalExportDto(
    val from: String,
    val to: String,
    val signature: String,
    val transactions: List<FiscalTxDto>,
)

@JsonClass(generateAdapter = true)
data class FiscalTxDto(
    val id: String,
    val timestamp: String,
    val total_cents: Long,
    val payment_method: String,
    val nf525_hash: String,
)
