package fr.vintiz.data.reports

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import retrofit2.HttpException
import java.io.IOException

/**
 * Pas d'offline pour les rapports : ce sont des agrégats temps réel
 * (CA jour, KPIs sur N jours, Z-reports). Sans réseau on remonte
 * VintizError.Network et la couche UI affiche un état dégradé.
 */
class ReportsRepository(private val api: ReportsApi) {

    suspend fun dashboard(): VintizResult<DashboardDto> = call { api.dashboard() }

    suspend fun retailKpis(periodDays: Int = 30): VintizResult<RetailKpisDto> =
        call { api.retailKpis(periodDays) }

    suspend fun daily(date: String? = null): VintizResult<DailyRecapDto> =
        call { api.daily(date) }

    suspend fun zReports(from: String? = null, to: String? = null): VintizResult<List<ZReportDto>> =
        call { api.zReports(from, to) }

    suspend fun fiscalExport(from: String, to: String): VintizResult<FiscalExportDto> =
        call { api.fiscalExport(from, to) }

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
