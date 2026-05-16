package fr.vintiz.data.trends

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

interface TrendsApi {

    /**
     * Proposition vitrine pour la semaine ISO courante. 404 si la
     * cron n'a pas encore tourné — l'UI propose alors un bouton
     * "Regénérer maintenant".
     */
    @GET("api/v1/admin/window-display/current")
    suspend fun currentWindowDisplay(): WindowProposalDto

    @POST("api/v1/admin/window-display/regenerate")
    suspend fun regenerateWindowDisplay(): WindowProposalDto

    @POST("api/v1/admin/window-display/{id}/accept")
    suspend fun acceptWindowDisplay(@Path("id") id: String): WindowProposalDto

    /**
     * Réordonne les produits de la proposition vitrine. Body :
     * { "product_ids": ["uuid1", "uuid2", ...] }. Les ids non
     * mentionnés sont conservés en queue par le backend.
     */
    @retrofit2.http.PATCH("api/v1/admin/window-display/{id}/reorder")
    suspend fun reorderWindowDisplay(
        @Path("id") id: String,
        @Body body: ReorderWindowRequest,
    ): WindowProposalDto

    @GET("api/v1/admin/markdown-rules")
    suspend fun markdownRules(@Query("active") active: Boolean? = null): List<MarkdownRuleDto>

    @POST("api/v1/admin/markdown-rules")
    suspend fun createMarkdownRule(@Body body: MarkdownRuleDto): MarkdownRuleDto

    @PUT("api/v1/admin/markdown-rules/{id}")
    suspend fun updateMarkdownRule(
        @Path("id") id: String,
        @Body body: MarkdownRuleDto,
    ): MarkdownRuleDto

    @DELETE("api/v1/admin/markdown-rules/{id}")
    suspend fun deleteMarkdownRule(@Path("id") id: String): Map<String, Any?>

    @GET("api/v1/admin/markdown-rules/preview")
    suspend fun previewMarkdownEngine(): MarkdownEnginePreviewDto

    @POST("api/v1/admin/markdown-rules/run")
    suspend fun runMarkdownEngine(): MarkdownEngineRunDto
}

@JsonClass(generateAdapter = true)
data class ReorderWindowRequest(val product_ids: List<String>)

@JsonClass(generateAdapter = true)
data class WindowProposalDto(
    val id: String,
    val iso_week: String,
    val proposal: Map<String, Any?>,
    val used_llm: Boolean = false,
    val accepted_at: String? = null,
    val accepted_by_user_id: String? = null,
)

@JsonClass(generateAdapter = true)
data class MarkdownRuleDto(
    val id: String? = null,
    val name: String,
    val conditions: Map<String, Any?>,
    val action: Map<String, Any?>,
    val priority: Int = 100,
    val active: Boolean = true,
)

@JsonClass(generateAdapter = true)
data class MarkdownEnginePreviewDto(
    val count_affected: Int,
    val samples: List<MarkdownPreviewItemDto> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class MarkdownPreviewItemDto(
    val product_id: String,
    val name: String,
    val current_price_cents: Long,
    val proposed_price_cents: Long,
    val rule_name: String,
)

@JsonClass(generateAdapter = true)
data class MarkdownEngineRunDto(
    val executed_at: String,
    val count_updated: Int,
)
