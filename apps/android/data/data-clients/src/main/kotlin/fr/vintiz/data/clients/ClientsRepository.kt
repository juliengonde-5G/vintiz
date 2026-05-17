package fr.vintiz.data.clients

import com.squareup.moshi.Moshi
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
    private val moshi: Moshi,
    private val now: () -> Long = { System.currentTimeMillis() },
) {

    private val clientAdapter by lazy { moshi.adapter(ClientDto::class.java) }
    private val matchesAdapter by lazy { moshi.adapter(ClientMatchesDto::class.java) }

    /**
     * Backend `/api/pos/clients/identify` renvoie 3 shapes possibles :
     *   - 404 → "client_not_found" → on retourne `Success(emptyList())`
     *   - Multi-match : `{matches: [...]}` → on extrait `.matches`
     *   - Single match : objet ClientDto seul → on enveloppe en list(1)
     */
    suspend fun identify(query: String): VintizResult<List<ClientDto>> = try {
        val response = api.identify(query)
        when {
            response.code() == 404 -> VintizResult.Success(emptyList())
            !response.isSuccessful -> VintizResult.Failure(
                VintizError.http(response.code(), response.message()),
            )
            else -> {
                val json = response.body()?.string()
                if (json.isNullOrBlank()) {
                    VintizResult.Success(emptyList())
                } else {
                    val list = parseIdentifyJson(json)
                    dao.upsertAll(list.map { it.toCache(now()) })
                    VintizResult.Success(list)
                }
            }
        }
    } catch (io: IOException) {
        Timber.i("identify offline — fallback Room")
        VintizResult.Success(dao.search(query).map { it.toDto() })
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    } catch (t: Throwable) {
        Timber.w(t, "identify parse KO")
        VintizResult.Success(emptyList())
    }

    private fun parseIdentifyJson(json: String): List<ClientDto> {
        // Tentative 1 : matches wrapper
        runCatching { matchesAdapter.fromJson(json) }.getOrNull()
            ?.takeIf { it.matches.isNotEmpty() }
            ?.let { return it.matches }
        // Tentative 2 : objet ClientDto seul
        runCatching { clientAdapter.fromJson(json) }.getOrNull()
            ?.let { return listOf(it) }
        return emptyList()
    }

    suspend fun fullClient(id: String): VintizResult<ClientFullDto> = try {
        VintizResult.Success(api.fullClient(id))
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    }

    suspend fun byNfcUid(uid: String): VintizResult<ClientDto> {
        val cached = dao.byNfcUid(uid)
        if (cached != null) return VintizResult.Success(cached.toDto())
        return when (val r = identify(uid)) {
            is VintizResult.Success -> r.value.firstOrNull { it.nfc_uid == uid }
                ?.let { VintizResult.Success(it) }
                ?: VintizResult.Failure(VintizError.Validation("nfc", "Carte non reconnue"))
            is VintizResult.Failure -> r
        }
    }

    /**
     * RGPD Article 20 — récupère l'export JSON et le retourne en bytes.
     * L'écran appelant peut le partager via FileProvider Intent.
     */
    suspend fun exportData(clientId: String): VintizResult<ByteArray> = try {
        val response = api.exportData(clientId)
        if (!response.isSuccessful) {
            VintizResult.Failure(VintizError.http(response.code(), response.message()))
        } else {
            val body = response.body()
                ?: return VintizResult.Failure(VintizError.Unknown("Export vide"))
            VintizResult.Success(body.bytes())
        }
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    }

    /**
     * RGPD Article 17 — demande de suppression soft.
     */
    suspend fun requestDeletion(clientId: String): VintizResult<ClientDeletionResponseDto> = try {
        VintizResult.Success(api.requestDeletion(clientId))
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
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
