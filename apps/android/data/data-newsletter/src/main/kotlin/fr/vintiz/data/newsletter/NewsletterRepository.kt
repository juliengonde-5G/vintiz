package fr.vintiz.data.newsletter

import android.content.Context
import android.net.Uri
import androidx.core.content.FileProvider
import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import retrofit2.HttpException
import timber.log.Timber
import java.io.File
import java.io.IOException

class NewsletterRepository(
    private val api: NewsletterApi,
    private val context: Context,
) {

    data class CsvExport(val uri: Uri, val filename: String)

    suspend fun list(query: String? = null): VintizResult<List<SubscriberDto>> = call {
        api.list(query)
    }

    suspend fun delete(id: String): VintizResult<Unit> = call {
        api.delete(id); Unit
    }

    suspend fun exportCsv(): VintizResult<CsvExport> = try {
        val response = api.export()
        if (!response.isSuccessful) {
            VintizResult.Failure(VintizError.http(response.code(), response.message()))
        } else {
            val body = response.body()
                ?: return VintizResult.Failure(VintizError.Unknown("Réponse vide"))
            val filename = parseFilename(response.headers()["Content-Disposition"])
                ?: "vintiz-newsletter-${System.currentTimeMillis()}.csv"
            val file = File(context.cacheDir, filename).apply {
                parentFile?.mkdirs()
                outputStream().use { out -> body.byteStream().use { it.copyTo(out) } }
            }
            val uri = FileProvider.getUriForFile(
                context, "${context.packageName}.fileprovider", file,
            )
            VintizResult.Success(CsvExport(uri, filename))
        }
    } catch (io: IOException) {
        Timber.w(io, "Téléchargement newsletter CSV KO")
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    }

    private fun parseFilename(contentDisposition: String?): String? {
        if (contentDisposition.isNullOrBlank()) return null
        val regex = Regex("filename=\"?([^\";]+)\"?")
        return regex.find(contentDisposition)?.groupValues?.getOrNull(1)
    }

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
