package fr.vintiz.data.cahier

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import retrofit2.HttpException
import java.io.IOException

class CahierRepository(private val api: CahierApi) {

    suspend fun day(date: String): VintizResult<CahierDayDto> = call { api.day(date) }

    suspend fun setMonthlyTarget(year: Int, month: Int, targetCents: Long): VintizResult<MonthlyTargetDto> =
        call { api.setMonthlyTarget(MonthlyTargetDto(year, month, targetCents)) }

    suspend fun setDailyText(
        date: String,
        message: String? = null,
        operation: String? = null,
    ): VintizResult<CahierDayDto> =
        call { api.setDailyText(DailyTextDto(date, message, operation)) }

    suspend fun sign(date: String, role: String, signature: String): VintizResult<CahierDayDto> =
        call { api.sign(SignatureDto(date, role, signature)) }

    suspend fun weekdayWeights(): VintizResult<WeekdayWeightsDto> =
        call { api.weekdayWeights() }

    suspend fun monthlyTarget(year: Int, month: Int): VintizResult<MonthlyTargetDto> =
        call { api.monthlyTarget(year, month) }

    private suspend inline fun <T> call(block: suspend () -> T): VintizResult<T> = try {
        VintizResult.Success(block())
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    } catch (t: Throwable) {
        // Schéma backend Cahier diverge encore du DTO Android (champs
        // nested EUR vs flat cents). Tant que les deux ne sont pas
        // alignés, on rattrape JsonDataException + autres au lieu de
        // crasher l'app.
        VintizResult.Failure(
            VintizError.Unknown("Cahier indisponible : ${t.message ?: t::class.simpleName}")
        )
    }
}
