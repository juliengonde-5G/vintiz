package fr.vintiz.core.network.interceptors

import com.google.common.truth.Truth.assertThat
import fr.vintiz.core.security.TokenStorage
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

class AuthInterceptorTest {

    private lateinit var server: MockWebServer
    private val storage = FakeTokenStorage()

    @BeforeEach
    fun setUp() {
        server = MockWebServer()
        server.start()
    }

    @AfterEach
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun `injecte Bearer quand un token est stocke`() {
        storage.saveAccessToken("eyJabc")
        val client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(storage))
            .build()

        server.enqueue(MockResponse().setResponseCode(200))
        client.newCall(Request.Builder().url(server.url("/api/v1/inventory")).build()).execute()

        val recorded = server.takeRequest()
        assertThat(recorded.getHeader("Authorization")).isEqualTo("Bearer eyJabc")
    }

    @Test
    fun `n'ajoute rien quand pas de token`() {
        val client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(storage))
            .build()

        server.enqueue(MockResponse().setResponseCode(200))
        client.newCall(Request.Builder().url(server.url("/api/v1/inventory")).build()).execute()

        val recorded = server.takeRequest()
        assertThat(recorded.getHeader("Authorization")).isNull()
    }

    @Test
    fun `respecte X-Skip-Auth et retire le header marqueur`() {
        storage.saveAccessToken("eyJabc")
        val client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(storage))
            .build()

        server.enqueue(MockResponse().setResponseCode(200))
        client.newCall(
            Request.Builder()
                .url(server.url("/api/v1/auth/login"))
                .header(AuthInterceptor.SKIP_AUTH_HEADER, "true")
                .build()
        ).execute()

        val recorded = server.takeRequest()
        assertThat(recorded.getHeader("Authorization")).isNull()
        assertThat(recorded.getHeader(AuthInterceptor.SKIP_AUTH_HEADER)).isNull()
    }
}

private class FakeTokenStorage : TokenStorage {
    private var token: String? = null
    private var cashier: String? = null
    override fun getAccessToken(): String? = token
    override fun saveAccessToken(token: String) { this.token = token }
    override fun clearAccessToken() { token = null }
    override fun getCashierId(): String? = cashier
    override fun saveCashierId(cashierId: String) { cashier = cashierId }
    override fun clearCashierId() { cashier = null }
    override fun clearAll() { token = null; cashier = null }
}
