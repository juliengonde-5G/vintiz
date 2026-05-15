package fr.vintiz.data.inventory

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.database.dao.ProductDao
import fr.vintiz.core.database.entity.ProductCacheEntity
import timber.log.Timber
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
    }

    suspend fun byId(id: String): VintizResult<ProductDto> = try {
        val dto = api.byId(id)
        dao.upsertAll(listOf(dto.toCache(now())))
        VintizResult.Success(dto)
    } catch (io: IOException) {
        val cached = dao.byId(id)
        if (cached != null) VintizResult.Success(cached.toDto())
        else VintizResult.Failure(VintizError.Network)
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
