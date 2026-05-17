package fr.vintiz.data.cahier

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import retrofit2.HttpException
import java.io.IOException

class CahierRepository(private val api: CahierApi) {

    suspend fun day(date: String): VintizResult<CahierDayDto> = call { api.day(date) }

    suspend fun setMonthlyTarget(
        year: Int,
        month: Int,
        targetEur: Double,
        notes: String? = null,
    ): VintizResult<Unit> = call {
        api.setMonthlyTarget(MonthlyTargetUpdateDto(year, month, targetEur, notes))
        Unit
    }

    suspend fun setDailyText(
        date: String,
        message: String? = null,
        operation: String? = null,
    ): VintizResult<Unit> = call {
        api.setDailyText(DailyTextDto(date, message, operation))
        Unit
    }

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
        VintizResult.Failure(
            VintizError.Unknown("Cahier : ${t.message ?: t::class.simpleName}")
        )
    }
}
