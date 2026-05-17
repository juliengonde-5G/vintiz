package fr.vintiz.data.newsletter

import com.squareup.moshi.JsonClass
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

interface NewsletterApi {

    /**
     * Backend renvoie `{total, active, unsubscribed, results: [...]}`
     * (cf. apps/api/app/api/newsletter/router.py:83-88
     * SubscribersListResponse). Le DTO Android encapsule donc le wrap.
     */
    @GET("api/newsletter/subscribers")
    suspend fun list(
        @Query("q") query: String? = null,
        @Query("limit") limit: Int = 100,
    ): SubscribersListDto

    @Streaming
    @GET("api/newsletter/subscribers/export")
    suspend fun export(): Response<ResponseBody>

    @DELETE("api/newsletter/subscribers/{id}")
    suspend fun delete(@Path("id") id: String): Map<String, Any?>
}

@JsonClass(generateAdapter = true)
data class SubscribersListDto(
    val total: Int = 0,
    val active: Int = 0,
    val unsubscribed: Int = 0,
    val results: List<SubscriberDto> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class SubscriberDto(
    val id: String,
    val email: String,
    val first_name: String? = null,
    val subscribed_at: String,
    val unsubscribed_at: String? = null,
    val consent_text_version: String? = null,
) {
    val isActive: Boolean get() = unsubscribed_at.isNullOrBlank()
}
