package fr.vintiz.data.cahier

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PUT
import retrofit2.http.Path

/**
 * Endpoints Cahier — voir apps/api/app/api/cahier/router.py.
 *
 * Le payload `/cahier/{date}` est nested EUR (cf. `service.compute_*`)
 * et non flat cents. Les writes utilisent des structures distinctes :
 *   - `/monthly-target` (PUT) attend `{year, month, target_eur,
 *     notes?}`
 *   - `/daily-text` (PUT) attend `{date, message_du_jour?,
 *     operation_en_cours?}`
 *   - Pas d'endpoint signature (supprimé Lot 5 backend).
 */
interface CahierApi {

    @GET("api/cahier/{date}")
    suspend fun day(@Path("date") date: String): CahierDayDto

    @GET("api/cahier/monthly-target/{year}/{month}")
    suspend fun monthlyTarget(
        @Path("year") year: Int,
        @Path("month") month: Int,
    ): MonthlyTargetDto

    @PUT("api/cahier/monthly-target")
    suspend fun setMonthlyTarget(@Body body: MonthlyTargetUpdateDto): Map<String, Any?>

    @PUT("api/cahier/daily-text")
    suspend fun setDailyText(@Body body: DailyTextDto): Map<String, Any?>

    @GET("api/cahier/weekday-weights")
    suspend fun weekdayWeights(): WeekdayWeightsDto
}

@JsonClass(generateAdapter = true)
data class WeekdayWeightsDto(
    /** Poids historique normalisé par jour (0=lundi, 6=dimanche). */
    val weights: List<Double> = emptyList(),
    val sample_weeks: Int = 0,
)

@JsonClass(generateAdapter = true)
data class CahierDayDto(
    val date: String,
    val is_past: Boolean = false,
    val weekday: String = "",
    val header: CahierHeaderDto = CahierHeaderDto(),
    val objectifs_valeur: ObjectifsValeurDto = ObjectifsValeurDto(),
    val performance: PerformanceDto = PerformanceDto(),
    val zoning: List<ZoningRowDto> = emptyList(),
    val crm_loyalty: CrmLoyaltyDto = CrmLoyaltyDto(),
    val progression_horaire: List<HourlyPointDto> = emptyList(),
    val progression_cible_horaire: List<HourlyPointDto> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class CahierHeaderDto(
    val weather: WeatherDto? = null,
    val message_du_jour: String? = null,
    val operation_en_cours: String? = null,
)

@JsonClass(generateAdapter = true)
data class WeatherDto(
    val temperature_c: Double = 0.0,
    val description: String = "",
    val icon: String? = null,
)

@JsonClass(generateAdapter = true)
data class ObjectifsValeurDto(
    /** CA budget mensuel saisi par le manager (EUR). */
    val ca_budget_mois: Double? = null,
    /** Objectif jour (% du mensuel × poids weekday). */
    val ca_objectif_jour: Double? = null,
    /** CA réalisé l'an dernier ce jour (EUR). */
    val ca_n1_jour: Double = 0.0,
    /** "transaction_log" / "z_report" / "absent". */
    val ca_n1_source: String? = null,
    /** Cumul mensuel à date (EUR). */
    val prog_ca_cumul_mois: Double = 0.0,
    /** Reste à faire mois (EUR), null si pas d'objectif. */
    val reste_a_faire_mois: Double? = null,
)

@JsonClass(generateAdapter = true)
data class PerformanceDto(
    /** Objectif jour (EUR). */
    val obj: Double? = null,
    /** CA réalisé jour (EUR). */
    val ca: Double = 0.0,
    /** CA N-1 (EUR). */
    val ca_n1: Double = 0.0,
    /** Progression vs objectif (%) — null si pas d'objectif. */
    val prog_vs_obj_pct: Double? = null,
    /** Delta vs N-1 (%). */
    val delta_vs_n1_pct: Double? = null,
    /** Taux ticket avec CRM (%). */
    val tx_crm_pct: Double = 0.0,
    /** Taux fidélité (%). */
    val loyalty_pct: Double = 0.0,
    /** Tickets count (TK). */
    val tk: Int = 0,
    /** Items par ticket (IV). */
    val iv: Double = 0.0,
    /** Panier moyen (PM, EUR). */
    val pm: Double = 0.0,
    /** Productivité opérateur (EUR/h). */
    val prod: Double = 0.0,
)

@JsonClass(generateAdapter = true)
data class ZoningRowDto(
    val zone_id: String,
    val zone_name: String,
    val color_code: String = "#008678",
    val obj_jour: Double = 0.0,
    val ca: Double = 0.0,
    val ca_n1: Double = 0.0,
    val delta_pct: Double? = null,
    val units: Int = 0,
)

@JsonClass(generateAdapter = true)
data class CrmLoyaltyDto(
    val fiches_creees: Int = 0,
    val adhesions_fidelite: Int = 0,
    val reprints: Int = 0,
    val tickets_fidelo: Int = 0,
)

@JsonClass(generateAdapter = true)
data class HourlyPointDto(
    val hour: Int,
    val ca_cumul: Double = 0.0,
)

@JsonClass(generateAdapter = true)
data class MonthlyTargetDto(
    val year: Int,
    val month: Int,
    /** Le backend stocke `target_eur` (float), null si pas saisi. */
    val target_eur: Double? = null,
    val notes: String? = null,
    val updated_at: String? = null,
)

@JsonClass(generateAdapter = true)
data class MonthlyTargetUpdateDto(
    val year: Int,
    val month: Int,
    val target_eur: Double,
    val notes: String? = null,
)

@JsonClass(generateAdapter = true)
data class DailyTextDto(
    val date: String,
    val message_du_jour: String? = null,
    val operation_en_cours: String? = null,
)
