package fr.vintiz.core.network.interceptors

import com.google.common.truth.Truth.assertThat
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

class RateLimitInterceptorTest {

    private lateinit var server: MockWebServer
    private val sleeps = mutableListOf<Long>()
    private val recorder = RateLimitInterceptor.Sleeper { seconds -> sleeps += seconds }

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
    fun `retry une fois apres Retry-After`() {
        server.enqueue(
            MockResponse()
                .setResponseCode(429)
                .setHeader("Retry-After", "2")
                .setBody("rate limited")
        )
        server.enqueue(MockResponse().setResponseCode(200).setBody("ok"))

        val client = OkHttpClient.Builder()
            .addInterceptor(RateLimitInterceptor(recorder))
            .build()

        val response = client.newCall(Request.Builder().url(server.url("/api/v1/auth/login")).build())
            .execute()

        assertThat(response.code).isEqualTo(200)
        assertThat(sleeps).containsExactly(2L)
        assertThat(server.requestCount).isEqualTo(2)
    }

    @Test
    fun `pas de retry quand Retry-After est absent`() {
        server.enqueue(MockResponse().setResponseCode(429))

        val client = OkHttpClient.Builder()
            .addInterceptor(RateLimitInterceptor(recorder))
            .build()

        val response = client.newCall(Request.Builder().url(server.url("/api/v1/auth/login")).build())
            .execute()

        assertThat(response.code).isEqualTo(429)
        assertThat(sleeps).isEmpty()
        assertThat(server.requestCount).isEqualTo(1)
    }

    @Test
    fun `pas de retry quand Retry-After depasse la borne`() {
        server.enqueue(
            MockResponse()
                .setResponseCode(429)
                .setHeader("Retry-After", "9999")
        )

        val client = OkHttpClient.Builder()
            .addInterceptor(RateLimitInterceptor(recorder))
            .build()

        val response = client.newCall(Request.Builder().url(server.url("/api/v1/")).build())
            .execute()

        assertThat(response.code).isEqualTo(429)
        assertThat(sleeps).isEmpty()
    }
}
