package fr.vintiz.data.notifications

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.POST

interface NotificationsApi {

    /**
     * Enregistre le device token FCM côté backend.
     * Endpoint à créer côté équipe API (cf. docs/MIGRATION_ANDROID_NATIVE.md §4.4).
     */
    @POST("api/notifications/fcm-token")
    suspend fun registerFcmToken(@Body body: FcmTokenRequest): Map<String, Any?>

    @POST("api/notifications/test")
    suspend fun test(): Map<String, Any?>
}

@JsonClass(generateAdapter = true)
data class FcmTokenRequest(
    val token: String,
    val device_id: String,
    val app_version: String,
    val topics: List<String> = emptyList(),
)
