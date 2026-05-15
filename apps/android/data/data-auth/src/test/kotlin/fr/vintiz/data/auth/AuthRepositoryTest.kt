package fr.vintiz.data.auth

import com.google.common.truth.Truth.assertThat
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.testing.FakeTokenStorage
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

class AuthRepositoryTest {

    private lateinit var server: MockWebServer
    private lateinit var api: AuthApi
    private val storage = FakeTokenStorage()

    @BeforeEach
    fun setUp() {
        server = MockWebServer().apply { start() }
        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        api = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
            .create(AuthApi::class.java)
    }

    @AfterEach
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun `login OK persiste le token`() = runTest {
        server.enqueue(
            MockResponse().setResponseCode(200).setBody(
                """{"access_token":"eyJxyz","token_type":"bearer","user_id":"u1","role":"manager"}"""
            )
        )
        val repo = AuthRepository(api, storage)
        val result = repo.login("admin", "vintiz2026")
        assertThat(result).isInstanceOf(VintizResult.Success::class.java)
        assertThat(storage.token).isEqualTo("eyJxyz")
    }

    @Test
    fun `login 401 retourne Unauthorized`() = runTest {
        server.enqueue(MockResponse().setResponseCode(401))
        val repo = AuthRepository(api, storage)
        val result = repo.login("admin", "wrong")
        assertThat(result).isEqualTo(VintizResult.Failure(VintizError.Unauthorized))
        assertThat(storage.token).isNull()
    }

    @Test
    fun `login 429 retourne RateLimit avec Retry-After`() = runTest {
        server.enqueue(MockResponse().setResponseCode(429).setHeader("Retry-After", "30"))
        val repo = AuthRepository(api, storage)
        val result = repo.login("admin", "x")
        assertThat(result).isEqualTo(VintizResult.Failure(VintizError.RateLimit(30)))
    }

    @Test
    fun `cashier login OK persiste l'id`() = runTest {
        server.enqueue(
            MockResponse().setResponseCode(200).setBody(
                """{"id":"c1","username":"lea","role":"collaborateur"}"""
            )
        )
        val repo = AuthRepository(api, storage)
        val result = repo.cashierLogin("1234")
        assertThat(result).isInstanceOf(VintizResult.Success::class.java)
        assertThat(storage.cashier).isEqualTo("c1")
    }

    @Test
    fun `refresh renvoie le nouveau token`() = runTest {
        server.enqueue(
            MockResponse().setResponseCode(200).setBody(
                """{"access_token":"newToken","token_type":"bearer","user_id":"u1","role":"manager"}"""
            )
        )
        val repo = AuthRepository(api, storage)
        val refreshed = repo.refresh("oldToken")
        assertThat(refreshed).isEqualTo("newToken")
    }

    @Test
    fun `refresh sur erreur renvoie null pour declencher logout`() = runTest {
        server.enqueue(MockResponse().setResponseCode(401))
        val repo = AuthRepository(api, storage)
        val refreshed = repo.refresh("oldToken")
        assertThat(refreshed).isNull()
    }

    @Test
    fun `logout efface le stockage`() = runTest {
        storage.saveAccessToken("x")
        storage.saveCashierId("y")
        AuthRepository(api, storage).logout()
        assertThat(storage.token).isNull()
        assertThat(storage.cashier).isNull()
    }
}
