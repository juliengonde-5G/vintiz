package fr.vintiz.data.clients

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.database.dao.ClientDao
import fr.vintiz.core.database.entity.ClientCacheEntity
import retrofit2.HttpException
import timber.log.Timber
import java.io.IOException

class ClientsRepository(
    private val api: ClientsApi,
    private val dao: ClientDao,
    private val now: () -> Long = { System.currentTimeMillis() },
) {

    suspend fun identify(query: String): VintizResult<List<ClientDto>> = try {
        val online = api.identify(query)
        dao.upsertAll(online.map { it.toCache(now()) })
        VintizResult.Success(online)
    } catch (io: IOException) {
        Timber.i("identify offline — fallback Room")
        VintizResult.Success(dao.search(query).map { it.toDto() })
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
    }

    suspend fun fullClient(id: String): VintizResult<ClientFullDto> = try {
        VintizResult.Success(api.fullClient(id))
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
    }

    suspend fun byNfcUid(uid: String): VintizResult<ClientDto> {
        val cached = dao.byNfcUid(uid)
        if (cached != null) return VintizResult.Success(cached.toDto())
        return try {
            val matches = api.identify(uid)
            val match = matches.firstOrNull { it.nfc_uid == uid }
                ?: return VintizResult.Failure(VintizError.Validation("nfc", "Carte non reconnue"))
            dao.upsertAll(listOf(match.toCache(now())))
            VintizResult.Success(match)
        } catch (io: IOException) {
            VintizResult.Failure(VintizError.Network)
        } catch (http: HttpException) {
            VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
        }
    }

    /**
     * RGPD Article 20 — récupère l'export JSON et le retourne en bytes.
     * L'écran appelant peut le partager via FileProvider Intent.
     */
    suspend fun exportData(clientId: String): VintizResult<ByteArray> = try {
        val response = api.exportData(clientId)
        if (!response.isSuccessful) {
            VintizResult.Failure(VintizError.Http(response.code(), response.message()))
        } else {
            val body = response.body()
                ?: return VintizResult.Failure(VintizError.Unknown("Export vide"))
            VintizResult.Success(body.bytes())
        }
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
    }

    /**
     * RGPD Article 17 — demande de suppression soft.
     */
    suspend fun requestDeletion(clientId: String): VintizResult<ClientDeletionResponseDto> = try {
        VintizResult.Success(api.requestDeletion(clientId))
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
    }
}

internal fun ClientDto.toCache(now: Long): ClientCacheEntity = ClientCacheEntity(
    id = id,
    firstName = first_name,
    lastName = last_name,
    email = email,
    phone = phone,
    membershipNumber = membership_number,
    loyaltyPoints = loyalty_points,
    loyaltyTier = loyalty_tier,
    nfcUid = nfc_uid,
    cachedAt = now,
)

internal fun ClientCacheEntity.toDto(): ClientDto = ClientDto(
    id = id,
    first_name = firstName,
    last_name = lastName,
    email = email,
    phone = phone,
    membership_number = membershipNumber,
    loyalty_points = loyaltyPoints,
    loyalty_tier = loyaltyTier,
    nfc_uid = nfcUid,
)
