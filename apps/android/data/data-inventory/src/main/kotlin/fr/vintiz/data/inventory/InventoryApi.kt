package fr.vintiz.data.inventory

import com.squareup.moshi.JsonClass
import retrofit2.http.GET
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
