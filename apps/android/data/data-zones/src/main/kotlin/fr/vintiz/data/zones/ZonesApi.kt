package fr.vintiz.data.zones

import com.squareup.moshi.JsonClass
import retrofit2.http.GET

interface ZonesApi {

    @GET("api/admin/store-plan")
    suspend fun storePlan(): StorePlanResponse
}

@JsonClass(generateAdapter = true)
data class StorePlanResponse(val zones: List<ZoneDto>)

@JsonClass(generateAdapter = true)
data class ZoneDto(
    val id: String,
    val name: String,
    val description: String? = null,
    val capacity: Int? = null,
    val product_types: List<String>? = null,
    val color_code: String? = null,
    val icon: String? = null,
    val is_window: Boolean = false,
    val pos_x: Int = 0,
    val pos_y: Int = 0,
    val width: Int = 100,
    val height: Int = 100,
    val shape: String = "rectangle",
    val n_products: Int = 0,
    val occupancy_pct: Double? = null,
    val avg_score: Double? = null,
    val score_bucket: String? = null,
)
