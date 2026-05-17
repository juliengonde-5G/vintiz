package fr.vintiz.data.ia

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import retrofit2.HttpException
import java.io.IOException

class IaRepository(private val api: IaApi) {

    suspend fun weeklyChecklist(): VintizResult<WeeklyChecklistDto> =
        call { api.weeklyChecklist() }

    suspend fun trends(): VintizResult<TrendsDto> = call { api.trends() }

    suspend fun marketingPersona(): VintizResult<PersonaReportDto> =
        call { api.marketingPersona() }

    suspend fun juridiquePersona(): VintizResult<PersonaReportDto> =
        call { api.juridiquePersona() }

    suspend fun productInsights(productId: String): VintizResult<ProductInsightsDto> =
        call { api.productInsights(productId) }

    private suspend inline fun <T> call(block: suspend () -> T): VintizResult<T> = try {
        VintizResult.Success(block())
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    } catch (t: Throwable) {
        // Anti-crash : JsonDataException ou autres exceptions non
        // attendues (schéma DTO désynchronisé, NPE Moshi, etc.).
        VintizResult.Failure(VintizError.Unknown(t.message ?: t::class.simpleName ?: "Erreur inconnue"))
    }
}
