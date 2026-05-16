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
            else -> VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
        }
    }
}
