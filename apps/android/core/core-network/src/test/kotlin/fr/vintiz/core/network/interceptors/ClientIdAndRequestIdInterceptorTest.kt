package fr.vintiz.core.network.interceptors

import com.google.common.truth.Truth.assertThat
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

class ClientIdAndRequestIdInterceptorTest {

    private lateinit var server: MockWebServer

    @BeforeEach
    fun setUp() {
        server = MockWebServer().apply { start() }
    }

    @AfterEach
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun `tag X-Client est applique a chaque requete`() {
        val client = OkHttpClient.Builder()
            .addInterceptor(ClientIdInterceptor("vintiz-android/0.1.0-dev"))
            .build()

        server.enqueue(MockResponse().setResponseCode(200))
        client.newCall(Request.Builder().url(server.url("/api/v1/")).build()).execute()

        val recorded = server.takeRequest()
        assertThat(recorded.getHeader("X-Client")).isEqualTo("vintiz-android/0.1.0-dev")
    }

    @Test
    fun `request-id absent est genere en hex 16 caracteres`() {
        val client = OkHttpClient.Builder()
            .addInterceptor(RequestIdInterceptor())
            .build()

        server.enqueue(MockResponse().setResponseCode(200))
        client.newCall(Request.Builder().url(server.url("/api/v1/")).build()).execute()

        val id = server.takeRequest().getHeader("x-request-id")
        assertThat(id).isNotNull()
        assertThat(id!!).hasLength(16)
        assertThat(id).matches("^[0-9a-f]{16}$")
    }

    @Test
    fun `request-id deja present est preserve`() {
        val client = OkHttpClient.Builder()
            .addInterceptor(RequestIdInterceptor())
            .build()

        server.enqueue(MockResponse().setResponseCode(200))
        client.newCall(
            Request.Builder()
                .url(server.url("/api/v1/"))
                .header("x-request-id", "manual-id-123")
                .build()
        ).execute()

        assertThat(server.takeRequest().getHeader("x-request-id")).isEqualTo("manual-id-123")
    }
}
