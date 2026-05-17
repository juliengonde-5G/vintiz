package fr.vintiz.data.zones

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import retrofit2.HttpException
import java.io.IOException

/**
 * Pas de cache local : le plan boutique est consulté manuellement par
 * le manager, pas pendant la vente. Sans réseau on remonte un
 * VintizError.Network — l'UI affiche un état dégradé "Plan
 * indisponible hors-ligne".
 */
class ZonesRepository(private val api: ZonesApi) {

    suspend fun storePlan(): VintizResult<List<ZoneDto>> = try {
        VintizResult.Success(api.storePlan().zones)
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    }
}
