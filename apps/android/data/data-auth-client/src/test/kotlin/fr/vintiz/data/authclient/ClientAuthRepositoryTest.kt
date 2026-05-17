package fr.vintiz.data.authclient

import com.google.common.truth.Truth.assertThat
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.testing.FakeClientTokenStorage
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

class ClientAuthRepositoryTest {

    private lateinit var server: MockWebServer
    private lateinit var api: ClientAuthApi
    private val storage = FakeClientTokenStorage()

    @BeforeEach
    fun setUp() {
        server = MockWebServer().apply { start() }
        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        api = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
            .create(ClientAuthApi::class.java)
    }

    @AfterEach
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun `requestOtp - 204 retourne Success sans persister quoi que ce soit`() = runTest {
        server.enqueue(MockResponse().setResponseCode(204))
        val repo = ClientAuthRepository(api, storage)
        val result = repo.requestOtp("cliente@vintiz.fr")
        assertThat(result).isInstanceOf(VintizResult.Success::class.java)
        assertThat(storage.token).isNull()
        assertThat(storage.storedEmail).isNull()
    }

    @Test
    fun `verifyOtp - 200 persiste token + email + membership`() = runTest {
        server.enqueue(
            MockResponse().setResponseCode(200).setBody(
                """{"access_token":"eyJabc","expires_in":3600,"client_id":"cli-42","membership_number":"V000042"}"""
            )
        )
        val repo = ClientAuthRepository(api, storage)
        val result = repo.verifyOtp("cliente@vintiz.fr", "123456")
        assertThat(result).isInstanceOf(VintizResult.Success::class.java)
        assertThat(storage.token).isEqualTo("eyJabc")
        assertThat(storage.storedEmail).isEqualTo("cliente@vintiz.fr")
        assertThat(storage.membership).isEqualTo("V000042")
    }

    @Test
    fun `verifyOtp - membership_number nullable accepte null`() = runTest {
        server.enqueue(
            MockResponse().setResponseCode(200).setBody(
                """{"access_token":"eyJabc","expires_in":3600,"client_id":"cli-42","membership_number":null}"""
            )
        )
        val repo = ClientAuthRepository(api, storage)
        val result = repo.verifyOtp("cliente@vintiz.fr", "123456")
        assertThat(result).isInstanceOf(VintizResult.Success::class.java)
        assertThat(storage.membership).isNull()
    }

    @Test
    fun `verifyOtp - 401 retourne Unauthorized et ne persiste rien`() = runTest {
        server.enqueue(MockResponse().setResponseCode(401))
        val repo = ClientAuthRepository(api, storage)
        val result = repo.verifyOtp("cliente@vintiz.fr", "000000")
        assertThat(result).isEqualTo(VintizResult.Failure(VintizError.Unauthorized))
        assertThat(storage.token).isNull()
    }

    @Test
    fun `verifyOtp - 429 retourne RateLimit avec Retry-After`() = runTest {
        server.enqueue(MockResponse().setResponseCode(429).setHeader("Retry-After", "45"))
        val repo = ClientAuthRepository(api, storage)
        val result = repo.verifyOtp("cliente@vintiz.fr", "123456")
        assertThat(result).isEqualTo(VintizResult.Failure(VintizError.RateLimit(45)))
    }

    @Test
    fun `logout efface tout le stockage`() = runTest {
        storage.saveAccessToken("x")
        storage.saveEmail("a@b.fr")
        storage.saveMembershipNumber("V000001")
        ClientAuthRepository(api, storage).logout()
        assertThat(storage.token).isNull()
        assertThat(storage.storedEmail).isNull()
        assertThat(storage.membership).isNull()
    }
}
