package fr.vintiz.data.fiscal

import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Query
import retrofit2.http.Streaming

interface FiscalApi {

    /**
     * Export NF525-conforme sur la période [from, to] (inclus). Le
     * backend signe avec une SHA-256 hash chain — voir
     * `apps/api/app/services/fiscal_export.py`.
     *
     * @Streaming : on lit le corps comme InputStream pour écrire dans
     * un fichier local sans tout charger en mémoire. Le serveur pose
     * le `Content-Disposition` avec un filename suggéré.
     *
     * Réponse encapsulée dans Response<> pour lire les headers (le
     * filename suggéré, le Content-Type effectif).
     */
    @Streaming
    @GET("api/v1/admin/fiscal-export")
    suspend fun export(
        @Query("from") from: String?,
        @Query("to") to: String?,
        @Query("format") format: String = "xml",
        @Query("merchant_name") merchantName: String = "Vintiz Vernon",
        @Query("merchant_id") merchantId: String = "",
    ): Response<ResponseBody>
}
