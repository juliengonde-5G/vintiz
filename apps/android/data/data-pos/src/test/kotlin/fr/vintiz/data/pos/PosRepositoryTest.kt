package fr.vintiz.data.pos

import com.google.common.truth.Truth.assertThat
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.database.dao.QueuedTransactionDao
import fr.vintiz.core.database.entity.QueuedTransactionEntity
import fr.vintiz.data.pos.dto.CreateTransactionRequest
import fr.vintiz.data.pos.dto.PaymentDto
import fr.vintiz.data.pos.dto.TransactionItemDto
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

class PosRepositoryTest {

    private lateinit var server: MockWebServer
    private lateinit var api: PosApi
    private val queue = InMemoryQueueDao()
    private val moshi: Moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private var clock = 1_000L
    private var nextUuid = "uuid-1"

    @BeforeEach
    fun setUp() {
        server = MockWebServer().apply { start() }
        api = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
            .create(PosApi::class.java)
    }

    @AfterEach
    fun tearDown() { server.shutdown() }

    private fun newRepo() = PosRepository(
        api = api,
        queueDao = queue,
        moshi = moshi,
        now = { clock },
        uuid = { nextUuid },
    )

    private fun sampleRequest(uuid: String = "uuid-1") = CreateTransactionRequest(
        items = listOf(
            TransactionItemDto(product_id = "p1", quantity = 1, discount_percent = 0)
        ),
        payments = listOf(PaymentDto(method = "cash", amount_cents = 1500)),
        client_uuid = uuid,
    )

    @Test
    fun `commit OK retire la queue`() = runTest {
        server.enqueue(
            MockResponse().setResponseCode(200).setBody(
                """{"id":"t1","total_cents":1500,"status":"completed","client_uuid":"uuid-1"}"""
            )
        )
        val result = newRepo().commit(sampleRequest())
        assertThat(result).isInstanceOf(VintizResult.Success::class.java)
        assertThat(queue.store).isEmpty()
    }

    @Test
    fun `commit offline laisse la vente en queue`() = runTest {
        // pas de réponse enqueue → MockWebServer va timeout / fermer
        server.shutdown() // simule réseau down
        val result = newRepo().commit(sampleRequest())
        assertThat(result).isEqualTo(VintizResult.Failure(VintizError.Network))
        assertThat(queue.store).hasSize(1)
        assertThat(queue.store.values.single().attempts).isEqualTo(1)
    }

    @Test
    fun `commit sans client_uuid en genere un`() = runTest {
        nextUuid = "generated-uuid"
        server.enqueue(MockResponse().setResponseCode(200).setBody(
            """{"id":"t2","total_cents":100,"status":"completed"}"""
        ))
        val req = sampleRequest(uuid = "")
        val result = newRepo().commit(req)
        assertThat(result).isInstanceOf(VintizResult.Success::class.java)
        // La queue est vide (suppression après POST OK) — vérification
        // que l'UUID généré a bien servi via le payload envoyé.
        val recorded = server.takeRequest().body.readUtf8()
        assertThat(recorded).contains("\"client_uuid\":\"generated-uuid\"")
    }

    @Test
    fun `409 retire la queue car serveur a deja la transaction`() = runTest {
        server.enqueue(MockResponse().setResponseCode(409))
        val result = newRepo().commit(sampleRequest())
        assertThat(result).isEqualTo(VintizResult.Failure(VintizError.Idempotent))
        assertThat(queue.store).isEmpty()
    }

    @Test
    fun `drain rejoue les ventes en attente`() = runTest {
        queue.enqueue(
            QueuedTransactionEntity(
                clientUuid = "uuid-x",
                payloadJson = moshi.adapter(CreateTransactionRequest::class.java)
                    .toJson(sampleRequest(uuid = "uuid-x")),
                createdAt = 1L,
            )
        )
        server.enqueue(MockResponse().setResponseCode(200).setBody(
            """{"id":"t-x","total_cents":1500,"status":"completed","client_uuid":"uuid-x"}"""
        ))

        val report = newRepo().drainQueue()
        assertThat(report.processed).isEqualTo(1)
        assertThat(report.succeeded).isEqualTo(1)
        assertThat(report.failed).isEqualTo(0)
        assertThat(queue.store).isEmpty()
    }

    @Test
    fun `payload corrompu est supprime pour eviter une boucle infinie`() = runTest {
        queue.enqueue(
            QueuedTransactionEntity(
                clientUuid = "bad",
                payloadJson = "{this is not json",
                createdAt = 1L,
            )
        )
        val report = newRepo().drainQueue()
        assertThat(report.failed).isEqualTo(1)
        assertThat(queue.store).isEmpty()
    }
}

private class InMemoryQueueDao : QueuedTransactionDao {
    val store = linkedMapOf<String, QueuedTransactionEntity>()

    override suspend fun enqueue(entity: QueuedTransactionEntity) {
        store.putIfAbsent(entity.clientUuid, entity)
    }
    override fun pending(): Flow<List<QueuedTransactionEntity>> = flowOf(store.values.toList())
    override suspend fun nextBatch(limit: Int): List<QueuedTransactionEntity> =
        store.values.take(limit)
    override suspend fun markFailure(clientUuid: String, error: String, now: Long) {
        val e = store[clientUuid] ?: return
        store[clientUuid] = e.copy(attempts = e.attempts + 1, lastError = error, lastAttemptAt = now)
    }
    override suspend fun delete(clientUuid: String) { store.remove(clientUuid) }
    override fun count(): Flow<Int> = flowOf(store.size)
}
