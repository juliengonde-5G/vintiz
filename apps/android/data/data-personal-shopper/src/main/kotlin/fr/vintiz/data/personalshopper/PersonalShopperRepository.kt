package fr.vintiz.data.personalshopper

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import retrofit2.HttpException
import timber.log.Timber
import java.io.IOException

class PersonalShopperRepository(private val api: PersonalShopperApi) {

    suspend fun forClient(clientId: String): VintizResult<PersonalShopperPicksDto> =
        call { api.forClient(clientId) }

    suspend fun companion(
        clientId: String,
        cartTotalCents: Long = 0,
        items: List<String> = emptyList(),
    ): VintizResult<PosCompanionDto> = call {
        api.companion(
            id = clientId,
            cartTotalCents = cartTotalCents,
            items = items.takeIf { it.isNotEmpty() }?.joinToString(","),
        )
    }

    /**
     * Recherche libre texte. Le backend renvoie un payload Claude Haiku
     * dont la structure peut varier (`{filters, products}` ou
     * `{products}`). On retourne le Map raw — l'UI extrait `products`
     * qui sera quasi toujours présent.
     */
    suspend fun searchByText(
        clientEmail: String,
        query: String,
    ): VintizResult<List<PickDto>> = try {
        val raw = api.search(PersonalShopperSearchRequest(clientEmail, query))
        val rawProducts = (raw["products"] as? List<*>).orEmpty()
            .mapNotNull { it as? Map<*, *> }
            .map { m ->
                PickDto(
                    product_id = (m["product_id"] as? String) ?: (m["id"] as? String).orEmpty(),
                    name = (m["name"] as? String).orEmpty(),
                    price_cents = ((m["sale_price"] as? Number)?.toDouble()?.times(100))?.toLong()
                        ?: (m["price_cents"] as? Number)?.toLong()
                        ?: 0L,
                    photo_url = m["photo_url"] as? String,
                    score = (m["score"] as? Number)?.toDouble() ?: 0.0,
                    reason = m["reason"] as? String,
                )
            }
        VintizResult.Success(rawProducts)
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        when (http.code()) {
            403 -> VintizResult.Failure(
                VintizError.Validation("consent", "Profilage non autorisé par la cliente"),
            )
            else -> VintizResult.Failure(VintizError.http(http.code(), http.message()))
        }
    } catch (t: Throwable) {
        Timber.w(t, "search libre KO")
        VintizResult.Failure(VintizError.Unknown("Recherche indisponible"))
    }

    suspend fun logClick(clientId: String, productId: String): VintizResult<Unit> = try {
        api.logClick(ClickEventDto(clientId, productId))
        VintizResult.Success(Unit)
    } catch (t: Throwable) {
        // Log discret : un click manqué ne doit pas casser la vente.
        Timber.d(t, "logClick KO — ignoré")
        VintizResult.Success(Unit)
    }

    private suspend inline fun <T> call(block: suspend () -> T): VintizResult<T> = try {
        VintizResult.Success(block())
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        when (http.code()) {
            403 -> VintizResult.Failure(
                VintizError.Validation("consent", "Profilage non autorisé par la cliente"),
            )
            404 -> VintizResult.Failure(
                VintizError.Validation("client", "Cliente sans profil — recommandation indisponible"),
            )
            else -> VintizResult.Failure(VintizError.http(http.code(), http.message()))
        }
    }
}
