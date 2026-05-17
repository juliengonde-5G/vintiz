package fr.vintiz.data.clients

import com.squareup.moshi.JsonClass
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

interface ClientsApi {

    /**
     * Backend renvoie 3 shapes selon le résultat :
     *   - 404 si rien trouvé
     *   - Un objet `ClientDto` seul si match unique
     *   - `{matches: [...]}` si multi-match
     * On expose un `Response<ResponseBody>` brut pour parser dans le
     * repo avec un fallback gracieux (404 = liste vide).
     */
    @GET("api/pos/clients/identify")
    suspend fun identify(@Query("q") q: String): Response<ResponseBody>

    @GET("api/crm/clients/lookup")
    suspend fun lookupByEmail(@Query("email") email: String): ClientDto?

    /**
     * Fiche cliente complète manager : 6 sections (synthèse, achats,
     * fidélité, goûts, RGPD, audit) renvoyées dans un seul payload
     * agrégé pour éviter 6 round-trips.
     */
    @GET("api/crm/clients/{id}/full")
    suspend fun fullClient(@Path("id") id: String): ClientFullDto

    /**
     * RGPD Article 20 — export portable JSON de toutes les données
     * cliente (commandes, consents, audit). Manager only.
     */
    @GET("api/crm/clients/{id}/data-export")
    @Streaming
    suspend fun exportData(@Path("id") id: String): Response<ResponseBody>

    /**
     * RGPD Article 17 — demande de suppression soft (fenêtre 30 j
     * annulable). L'API marque la cliente, le worker côté serveur la
     * purge à expiration.
     */
    @POST("api/crm/clients/{id}/deletion-request")
    suspend fun requestDeletion(@Path("id") id: String): ClientDeletionResponseDto
}

@JsonClass(generateAdapter = true)
data class ClientMatchesDto(
    val matches: List<ClientDto> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class ClientDeletionResponseDto(
    val status: String,
    val purge_at: String? = null,
)

@JsonClass(generateAdapter = true)
data class ClientDto(
    val id: String,
    val first_name: String,
    val last_name: String,
    val email: String? = null,
    val phone: String? = null,
    val membership_number: String? = null,
    val loyalty_points: Int = 0,
    val loyalty_tier: String? = null,
    val nfc_uid: String? = null,
)

@JsonClass(generateAdapter = true)
data class ClientFullDto(
    val client: ClientDto,
    val total_spent_cents: Long = 0,
    val transaction_count: Int = 0,
    val avg_basket_cents: Long = 0,
    val last_visit_at: String? = null,
    val rfm_segment: String? = null, // champion / loyal / at_risk / hibernating / new
    val recent_transactions: List<ClientTransactionDto> = emptyList(),
    val tastes: List<String> = emptyList(),
    val consents: List<ClientConsentDto> = emptyList(),
    val recent_audit: List<ClientAuditDto> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class ClientTransactionDto(
    val id: String,
    val timestamp: String,
    val total_cents: Long,
    val item_count: Int = 0,
)

@JsonClass(generateAdapter = true)
data class ClientConsentDto(
    val purpose: String,
    val granted: Boolean,
    val recorded_at: String,
)

@JsonClass(generateAdapter = true)
data class ClientAuditDto(
    val timestamp: String,
    val action: String,
    val user_id: String? = null,
)
