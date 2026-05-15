package fr.vintiz.data.pos

import com.squareup.moshi.Moshi
import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.database.dao.QueuedTransactionDao
import fr.vintiz.core.database.entity.QueuedTransactionEntity
import fr.vintiz.data.pos.dto.CreateTransactionRequest
import fr.vintiz.data.pos.dto.TransactionResponse
import retrofit2.HttpException
import timber.log.Timber
import java.io.IOException
import java.util.UUID

/**
 * Toute vente passe d'abord en queue locale Room. Si le réseau répond,
 * on dépile immédiatement avec un POST idempotent. Sinon, le worker
 * `DrainTransactionsWorker` rejouera. Le serveur tranche les doublons
 * via `client_uuid` (`apps/api/app/services/pos.py:68-76`).
 */
class PosRepository(
    private val api: PosApi,
    private val queueDao: QueuedTransactionDao,
    private val moshi: Moshi,
    private val now: () -> Long = { System.currentTimeMillis() },
    private val uuid: () -> String = { UUID.randomUUID().toString() },
) {

    private val adapter = moshi.adapter(CreateTransactionRequest::class.java)

    /**
     * Commit local : la vente est enregistrée en queue + tentative
     * immédiate. Si le POST échoue (réseau / 5xx), la vente reste en
     * queue. Le `client_uuid` est généré ici si absent.
     */
    suspend fun commit(
        request: CreateTransactionRequest,
    ): VintizResult<TransactionResponse> {
        val finalRequest = if (request.client_uuid.isBlank()) {
            request.copy(client_uuid = uuid())
        } else {
            request
        }
        queueDao.enqueue(
            QueuedTransactionEntity(
                clientUuid = finalRequest.client_uuid,
                payloadJson = adapter.toJson(finalRequest),
                createdAt = now(),
            )
        )
        return tryPost(finalRequest)
    }

    private suspend fun tryPost(req: CreateTransactionRequest): VintizResult<TransactionResponse> =
        try {
            val resp = api.createTransaction(req)
            queueDao.delete(req.client_uuid)
            VintizResult.Success(resp)
        } catch (io: IOException) {
            Timber.i("POS commit offline — kept in queue (uuid=%s)", req.client_uuid)
            queueDao.markFailure(req.client_uuid, io.message ?: "network", now())
            VintizResult.Failure(VintizError.Network)
        } catch (http: HttpException) {
            queueDao.markFailure(req.client_uuid, "HTTP ${http.code()}", now())
            when (http.code()) {
                401 -> VintizResult.Failure(VintizError.Unauthorized)
                409 -> {
                    // Serveur a déjà la transaction : on retire la queue.
                    queueDao.delete(req.client_uuid)
                    VintizResult.Failure(VintizError.Idempotent)
                }
                else -> VintizResult.Failure(VintizError.Http(http.code(), http.message() ?: ""))
            }
        }

    /**
     * Drain prioritaire : appelé par `DrainTransactionsWorker`. Tente
     * chaque entrée une fois. Si le serveur retourne un 2xx ou un 409,
     * la ligne est supprimée. Sinon on incrémente `attempts` et on
     * laisse le worker rebondir avec son backoff.
     */
    suspend fun drainQueue(batchSize: Int = 20): DrainReport {
        val batch = queueDao.nextBatch(batchSize)
        var ok = 0
        var failed = 0
        for (entity in batch) {
            val req = runCatching { adapter.fromJson(entity.payloadJson) }
                .getOrNull()
            if (req == null) {
                // Payload corrompu : on retire pour éviter une boucle infinie
                Timber.w("Drain : payload corrompu pour uuid=%s, suppression", entity.clientUuid)
                queueDao.delete(entity.clientUuid)
                failed++
                continue
            }
            when (val r = tryPost(req)) {
                is VintizResult.Success -> ok++
                is VintizResult.Failure -> {
                    if (r.error == VintizError.Idempotent) ok++ else failed++
                }
            }
        }
        return DrainReport(processed = batch.size, succeeded = ok, failed = failed)
    }

    data class DrainReport(val processed: Int, val succeeded: Int, val failed: Int)
}
