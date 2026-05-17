package fr.vintiz.data.ia

import com.squareup.moshi.JsonClass
import retrofit2.http.GET
import retrofit2.http.Path

/**
 * Endpoints IA — alignés sur `apps/api/app/api/ai/router.py`.
 *
 * - `/ai/weekly-checklist` retourne `{week, year, generated_at,
 *   ai_summary, checklist: [...]}`
 * - `/ai/trends` retourne `{week, year, season, generated_at,
 *   editorial_intro, trends, brands, channels, inventory_matches}`
 * - `/ai/persona/marketing` est en `GET` (pas POST) et retourne un
 *   payload IA structuré dont l'app n'extrait que `intro/sections`.
 *   La persona "juridique" reste un POST (audit RGPD à la demande).
 */
interface IaApi {

    @GET("api/ai/weekly-checklist")
    suspend fun weeklyChecklist(): WeeklyChecklistDto

    @GET("api/ai/trends")
    suspend fun trends(): TrendsDto

    @GET("api/ai/persona/marketing")
    suspend fun marketingPersona(): PersonaReportDto

    @GET("api/inventory/products/{id}/insights")
    suspend fun productInsights(@Path("id") id: String): ProductInsightsDto
}

@JsonClass(generateAdapter = true)
data class WeeklyChecklistDto(
    val week: Int = 0,
    val year: Int = 0,
    val generated_at: String? = null,
    val ai_summary: String? = null,
    val checklist: List<ChecklistItemDto> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class ChecklistItemDto(
    val type: String? = null,
    val priority: String? = null,
    val title: String,
    val description: String? = null,
    val deeplink: String? = null,
    val products: List<Map<String, Any?>>? = null,
)

@JsonClass(generateAdapter = true)
data class TrendsDto(
    val week: Int = 0,
    val year: Int = 0,
    val season: String? = null,
    val generated_at: String? = null,
    val editorial_intro: String? = null,
    val trends: List<TrendDto> = emptyList(),
    val brands: List<BrandDto> = emptyList(),
    /** Forme legacy {reseaux_sociaux, vinted, retail} — flex via Map. */
    val channels: Map<String, Any?>? = null,
    /** Inventory matches keyword → list produits — flex. */
    val inventory_matches: Map<String, Any?>? = null,
)

@JsonClass(generateAdapter = true)
data class TrendDto(
    val id: String? = null,
    val title: String,
    val key_words: List<String> = emptyList(),
    val source: String? = null,
    val article: String? = null,
    val visual_prompt: String? = null,
    val categories: List<String> = emptyList(),
    val colors: List<String> = emptyList(),
    val match_keywords: List<String> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class BrandDto(
    val name: String,
    val tier: String? = null,
    val why: String? = null,
    val logo_query: String? = null,
)

/**
 * Persona report — la structure exacte dépend de Claude Haiku, on
 * accepte un sous-ensemble plat + un map raw pour le reste.
 */
@JsonClass(generateAdapter = true)
data class PersonaReportDto(
    val week: Int = 0,
    val year: Int = 0,
    val generated_at: String? = null,
    val intro: String? = null,
    val summary: String? = null,
    val sections: List<PersonaSectionDto> = emptyList(),
    val recommendations: List<String> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class PersonaSectionDto(
    val title: String,
    val body: String? = null,
    val items: List<String> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class ProductInsightsDto(
    val product_id: String? = null,
    val badges: List<String> = emptyList(),
    val suggested_price_cents: Long? = null,
    val markdown_due_at: String? = null,
)
