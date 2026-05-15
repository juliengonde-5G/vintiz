package fr.vintiz.data.clients

import com.squareup.moshi.JsonClass
import retrofit2.http.GET
import retrofit2.http.Query

interface ClientsApi {

    @GET("api/v1/pos/clients/identify")
    suspend fun identify(@Query("q") q: String): List<ClientDto>

    @GET("api/v1/crm/clients/lookup")
    suspend fun lookupByEmail(@Query("email") email: String): ClientDto?
}

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
