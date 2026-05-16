package fr.vintiz.data.inventory

import com.squareup.moshi.JsonClass
import okhttp3.MultipartBody
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface InventoryApi {

    @GET("api/v1/inventory/products")
    suspend fun list(
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 50,
    ): ProductPageDto

    @GET("api/v1/inventory/products/search")
    suspend fun search(
        @Query("q") q: String,
        @Query("include_sold") includeSold: Boolean = false,
    ): List<ProductDto>

    @GET("api/v1/inventory/products/by-barcode/{barcode}")
    suspend fun byBarcode(@Path("barcode") barcode: String): ProductDto

    @GET("api/v1/inventory/products/{id}")
    suspend fun byId(@Path("id") id: String): ProductDto

    /**
     * Import en masse CSV. Le backend supporte un dry-run preview
     * (?dry_run=true) qui retourne uniquement les volumes attendus
     * sans rien modifier — utile pour valider le format avant commit.
     */
    @Multipart
    @POST("api/v1/inventory/products/import-csv")
    suspend fun importCsv(
        @Part file: MultipartBody.Part,
        @Query("dry_run") dryRun: Boolean = false,
    ): CsvImportResultDto

    @GET("api/v1/inventory/products/{id}/photos")
    suspend fun photos(@Path("id") productId: String): List<ProductPhotoDto>

    @Multipart
    @POST("api/v1/inventory/products/{id}/photos")
    suspend fun uploadPhoto(
        @Path("id") productId: String,
        @Part photo: MultipartBody.Part,
    ): ProductPhotoDto
}

@JsonClass(generateAdapter = true)
data class ProductDto(
    val id: String,
    val barcode: String? = null,
    val name: String,
    val price_cents: Long,
    val tva_rate: Double = 20.0,
    val category: String? = null,
    val photo_url: String? = null,
    val status: String = "in_stock",
)

@JsonClass(generateAdapter = true)
data class ProductPageDto(
    val items: List<ProductDto>,
    val total: Int,
    val page: Int,
    val page_size: Int,
)

@JsonClass(generateAdapter = true)
data class CsvImportResultDto(
    val dry_run: Boolean,
    val created: Int = 0,
    val updated: Int = 0,
    val skipped: Int = 0,
    val errors: List<CsvImportErrorDto> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class CsvImportErrorDto(val row: Int, val reason: String)

@JsonClass(generateAdapter = true)
data class ProductPhotoDto(
    val id: String,
    val url: String,
    val is_primary: Boolean = false,
    val display_order: Int = 0,
)
