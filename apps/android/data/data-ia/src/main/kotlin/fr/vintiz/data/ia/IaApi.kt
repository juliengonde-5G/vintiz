package fr.vintiz.data.ia

import com.squareup.moshi.JsonClass
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface IaApi {

    @GET("api/ai/weekly-checklist")
    suspend fun weeklyChecklist(): WeeklyChecklistDto

    @GET("api/ai/trends")
    suspend fun trends(): TrendsDto

    @POST("api/ai/persona/marketing")
    suspend fun marketingPersona(): PersonaReportDto

    @POST("api/ai/persona/juridique")
    suspend fun juridiquePersona(): PersonaReportDto

    @GET("api/inventory/products/{id}/insights")
    suspend fun productInsights(@Path("id") id: String): ProductInsightsDto
}

@JsonClass(generateAdapter = true)
data class WeeklyChecklistDto(
    val week_iso: String,
    val items: List<ChecklistItemDto>,
)

@JsonClass(generateAdapter = true)
data class ChecklistItemDto(
    val id: String,
    val title: String,
    val priority: String,
    val rationale: String? = null,
    val done: Boolean = false,
)

@JsonClass(generateAdapter = true)
data class TrendsDto(
    val generated_at: String,
    val social_signals: List<TrendSignalDto> = emptyList(),
    val retail_signals: List<TrendSignalDto> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class TrendSignalDto(
    val source: String,
    val label: String,
    val score: Double,
    val link: String? = null,
)

@JsonClass(generateAdapter = true)
data class PersonaReportDto(
    val title: String,
    val summary: String,
    val recommendations: List<String> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class ProductInsightsDto(
    val product_id: String,
    val badges: List<String>,
    val suggested_price_cents: Long? = null,
    val markdown_due_at: String? = null,
)
