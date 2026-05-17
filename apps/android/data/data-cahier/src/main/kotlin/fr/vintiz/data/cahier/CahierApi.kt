package fr.vintiz.data.cahier

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PUT
import retrofit2.http.Path

interface CahierApi {

    @GET("api/cahier/{date}")
    suspend fun day(@Path("date") date: String): CahierDayDto

    @GET("api/cahier/monthly-target/{year}/{month}")
    suspend fun monthlyTarget(
        @Path("year") year: Int,
        @Path("month") month: Int,
    ): MonthlyTargetDto

    @PUT("api/cahier/monthly-target")
    suspend fun setMonthlyTarget(@Body body: MonthlyTargetDto): MonthlyTargetDto

    @PUT("api/cahier/daily-text")
    suspend fun setDailyText(@Body body: DailyTextDto): CahierDayDto

    @PUT("api/cahier/signature")
    suspend fun sign(@Body body: SignatureDto): CahierDayDto

    @GET("api/cahier/weekday-weights")
    suspend fun weekdayWeights(): WeekdayWeightsDto
}

@JsonClass(generateAdapter = true)
data class WeekdayWeightsDto(
    /** Poids historique normalisé 0..1 par jour (0=lundi, 6=dimanche). */
    val weights: List<Double>,
    val sample_weeks: Int = 0,
)

@JsonClass(generateAdapter = true)
data class CahierDayDto(
    val date: String,
    val target_cents: Long,
    val actual_cents: Long,
    val transaction_count: Int,
    val message_of_the_day: String? = null,
    val current_operation: String? = null,
    val manager_signature: String? = null,
    val team_signature: String? = null,
    val cumulative_month_cents: Long = 0,
    val remaining_month_cents: Long = 0,
    val ya1_cents: Long = 0,
)

@JsonClass(generateAdapter = true)
data class MonthlyTargetDto(val year: Int, val month: Int, val target_cents: Long)

@JsonClass(generateAdapter = true)
data class DailyTextDto(
    val date: String,
    val message_of_the_day: String? = null,
    val current_operation: String? = null,
)

@JsonClass(generateAdapter = true)
data class SignatureDto(val date: String, val role: String, val signature: String)
