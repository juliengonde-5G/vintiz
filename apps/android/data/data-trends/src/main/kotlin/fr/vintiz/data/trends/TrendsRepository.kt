package fr.vintiz.data.trends

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import retrofit2.HttpException
import java.io.IOException

/**
 * Recos vitrine + règles markdown. Manager-only côté backend.
 * Pas de cache local : ce sont des décisions one-shot.
 */
class TrendsRepository(private val api: TrendsApi) {

    /**
     * 404 distinct : la cron n'a pas encore tourné. L'UI propose alors
     * "Regénérer maintenant" pour forcer un calcul.
     */
    suspend fun currentWindowDisplay(): VintizResult<WindowProposalDto?> = try {
        VintizResult.Success(api.currentWindowDisplay())
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        if (http.code() == 404) VintizResult.Success(null)
        else VintizResult.Failure(VintizError.http(http.code(), http.message()))
    }

    suspend fun regenerateWindowDisplay(): VintizResult<WindowProposalDto> =
        call { api.regenerateWindowDisplay() }

    suspend fun acceptWindowDisplay(id: String): VintizResult<WindowProposalDto> =
        call { api.acceptWindowDisplay(id) }

    suspend fun reorderWindowDisplay(
        id: String,
        productIds: List<String>,
    ): VintizResult<WindowProposalDto> = try {
        VintizResult.Success(api.reorderWindowDisplay(id, ReorderWindowRequest(productIds)))
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        when (http.code()) {
            409 -> VintizResult.Failure(VintizError.Validation(
                "proposal", "Déjà validée — régénérer d'abord"))
            else -> VintizResult.Failure(VintizError.http(http.code(), http.message()))
        }
    } catch (t: Throwable) {
        // Anti-crash : JsonDataException ou autres exceptions non
        // attendues (schéma DTO désynchronisé, NPE Moshi, etc.).
        VintizResult.Failure(VintizError.Unknown(t.message ?: t::class.simpleName ?: "Erreur inconnue"))
    }

    suspend fun markdownRules(active: Boolean? = null): VintizResult<List<MarkdownRuleDto>> =
        call { api.markdownRules(active) }

    suspend fun previewMarkdownEngine(): VintizResult<MarkdownEnginePreviewDto> =
        call { api.previewMarkdownEngine() }

    suspend fun runMarkdownEngine(): VintizResult<MarkdownEngineRunDto> =
        call { api.runMarkdownEngine() }

    private suspend inline fun <T> call(block: suspend () -> T): VintizResult<T> = try {
        VintizResult.Success(block())
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    } catch (t: Throwable) {
        VintizResult.Failure(VintizError.Unknown(t.message ?: t::class.simpleName ?: "Erreur inconnue"))
    }
}
