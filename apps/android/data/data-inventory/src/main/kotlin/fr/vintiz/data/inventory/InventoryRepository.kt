package fr.vintiz.data.inventory

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.database.dao.ProductDao
import fr.vintiz.core.database.entity.ProductCacheEntity
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import retrofit2.HttpException
import timber.log.Timber
import java.io.File
import java.io.IOException

class InventoryRepository(
    private val api: InventoryApi,
    private val dao: ProductDao,
    private val now: () -> Long = { System.currentTimeMillis() },
) {

    /**
     * Recherche : tente l'API d'abord, retombe sur le cache local Room
     * si offline. Le caissier doit pouvoir continuer à scanner et à
     * encaisser même sans connexion.
     */
    suspend fun search(query: String): VintizResult<List<ProductDto>> = try {
        val online = api.search(query)
        dao.upsertAll(online.map { it.toCache(now()) })
        VintizResult.Success(online)
    } catch (io: IOException) {
        Timber.i("search offline — fallback Room")
        VintizResult.Success(dao.search(query).map { it.toDto() })
    } catch (http: HttpException) {
        Timber.w(http, "search HTTP %d — fallback Room", http.code())
        VintizResult.Success(dao.search(query).map { it.toDto() })
    }

    /**
     * Lookup par code-barres (douchette ou caméra). Offline-safe.
     */
    suspend fun byBarcode(barcode: String): VintizResult<ProductDto> = try {
        val dto = api.byBarcode(barcode)
        dao.upsertAll(listOf(dto.toCache(now())))
        VintizResult.Success(dto)
    } catch (io: IOException) {
        val cached = dao.byBarcode(barcode)
        if (cached != null) VintizResult.Success(cached.toDto())
        else VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        val cached = dao.byBarcode(barcode)
        if (cached != null) VintizResult.Success(cached.toDto())
        else VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
    }

    suspend fun byId(id: String): VintizResult<ProductDto> = try {
        val dto = api.byId(id)
        dao.upsertAll(listOf(dto.toCache(now())))
        VintizResult.Success(dto)
    } catch (io: IOException) {
        val cached = dao.byId(id)
        if (cached != null) VintizResult.Success(cached.toDto())
        else VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        val cached = dao.byId(id)
        if (cached != null) VintizResult.Success(cached.toDto())
        else VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
    }

    /**
     * Import CSV en masse. `dryRun=true` permet de prévisualiser le
     * résultat (volumes + erreurs ligne par ligne) sans rien
     * persister. À utiliser avant tout commit pour éviter qu'un import
     * mal formaté n'écrase la base.
     */
    suspend fun importCsv(file: File, dryRun: Boolean): VintizResult<CsvImportResultDto> = try {
        val body = file.asRequestBody("text/csv".toMediaTypeOrNull())
        val part = MultipartBody.Part.createFormData("file", file.name, body)
        val result = api.importCsv(part, dryRun)
        if (!dryRun) dao.clear() // forcer SyncProducts au prochain run
        VintizResult.Success(result)
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
    }

    suspend fun photos(productId: String): VintizResult<List<ProductPhotoDto>> = try {
        VintizResult.Success(api.photos(productId))
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
    }

    suspend fun uploadPhoto(productId: String, file: File): VintizResult<ProductPhotoDto> = try {
        val mediaType = (file.guessMimeType()).toMediaTypeOrNull()
        val body = file.asRequestBody(mediaType)
        val part = MultipartBody.Part.createFormData("photo", file.name, body)
        VintizResult.Success(api.uploadPhoto(productId, part))
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
    }

    private fun File.guessMimeType(): String = when (extension.lowercase()) {
        "jpg", "jpeg" -> "image/jpeg"
        "png" -> "image/png"
        "webp" -> "image/webp"
        else -> "application/octet-stream"
    }
}

internal fun ProductDto.toCache(updatedAt: Long): ProductCacheEntity = ProductCacheEntity(
    id = id,
    barcode = barcode,
    name = name,
    priceCents = price_cents,
    tvaRate = tva_rate,
    category = category,
    photoUrl = photo_url,
    status = status,
    updatedAt = updatedAt,
)

internal fun ProductCacheEntity.toDto(): ProductDto = ProductDto(
    id = id,
    barcode = barcode,
    name = name,
    price_cents = priceCents,
    tva_rate = tvaRate,
    category = category,
    photo_url = photoUrl,
    status = status,
)
