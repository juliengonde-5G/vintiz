package fr.vintiz.data.fiscal

import android.content.Context
import androidx.core.content.FileProvider
import android.net.Uri
import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import java.io.File
import java.io.IOException
import retrofit2.HttpException
import timber.log.Timber

/**
 * Télécharge l'export fiscal NF525 et le persiste dans le cache app.
 * Retourne un Uri partageable via FileProvider pour qu'on l'ouvre
 * dans un Intent ACTION_SEND (mail / Drive / signature électronique).
 *
 * Aucun parsing local du contenu : le hash NF525 reste vérifié côté
 * serveur, on transporte du opaque.
 */
class FiscalRepository(
    private val api: FiscalApi,
    private val context: Context,
) {

    data class ExportFile(val uri: Uri, val filename: String, val mimeType: String)

    suspend fun export(
        from: String?,
        to: String?,
        format: FiscalFormat,
    ): VintizResult<ExportFile> = try {
        val response = api.export(from = from, to = to, format = format.key)
        if (!response.isSuccessful) {
            VintizResult.Failure(VintizError.Http(response.code(), response.message()))
        } else {
            val body = response.body()
                ?: return VintizResult.Failure(VintizError.Unknown("Réponse vide du serveur"))
            val filename = parseFilename(response.headers()["Content-Disposition"])
                ?: defaultFilename(from, format)
            val file = File(context.cacheDir, filename).apply {
                parentFile?.mkdirs()
                outputStream().use { out -> body.byteStream().use { it.copyTo(out) } }
            }
            val uri = FileProvider.getUriForFile(
                context, "${context.packageName}.fileprovider", file,
            )
            VintizResult.Success(ExportFile(uri, filename, format.mimeType))
        }
    } catch (io: IOException) {
        Timber.w(io, "Téléchargement fiscal-export KO")
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
    }

    private fun parseFilename(contentDisposition: String?): String? {
        if (contentDisposition.isNullOrBlank()) return null
        val regex = Regex("filename=\"?([^\";]+)\"?")
        return regex.find(contentDisposition)?.groupValues?.getOrNull(1)
    }

    private fun defaultFilename(from: String?, format: FiscalFormat): String {
        val suffix = from?.take(10) ?: "all"
        return "vintiz-fiscal-export-$suffix.${format.key}"
    }
}

enum class FiscalFormat(val key: String, val mimeType: String, val label: String) {
    Xml("xml", "application/xml", "XML (NF525)"),
    Json("json", "application/json", "JSON");
}
