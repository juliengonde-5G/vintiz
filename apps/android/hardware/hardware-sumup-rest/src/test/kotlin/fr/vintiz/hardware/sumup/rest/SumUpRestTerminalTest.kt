package fr.vintiz.hardware.sumup.rest

import com.google.common.truth.Truth.assertThat
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import fr.vintiz.core.common.Money
import fr.vintiz.hardware.api.PaymentOutcome
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

class SumUpRestTerminalTest {

    private lateinit var server: MockWebServer
    private lateinit var api: SumUpRestApi

    @BeforeEach
    fun setUp() {
        server = MockWebServer().apply { start() }
        api = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(Moshi.Builder().add(KotlinJsonAdapterFactory()).build()))
            .build()
            .create(SumUpRestApi::class.java)
    }

    @AfterEach
    fun tearDown() { server.shutdown() }

    @Test
    fun `paiement reussi remonte Paid avec card_brand`() = runTest {
        server.enqueue(MockResponse().setBody("""{"checkout_id":"ck1","status":"PENDING"}"""))
        server.enqueue(MockResponse().setBody(
            """{"status":"PAID","card_brand":"VISA","card_last4":"4242","auth_code":"A123"}"""
        ))
        val terminal = SumUpRestTerminal(api, pollIntervalMs = 1L, timeoutMs = 2_000L)
        val outcome = terminal.pay(Money(1500), "tx-1", "Vente Vintiz")
        assertThat(outcome).isInstanceOf(PaymentOutcome.Paid::class.java)
        val paid = outcome as PaymentOutcome.Paid
        assertThat(paid.checkoutId).isEqualTo("ck1")
        assertThat(paid.cardBrand).isEqualTo("VISA")
        assertThat(paid.cardLast4).isEqualTo("4242")
    }

    @Test
    fun `paiement refuse remonte Declined`() = runTest {
        server.enqueue(MockResponse().setBody("""{"checkout_id":"ck2","status":"PENDING"}"""))
        server.enqueue(MockResponse().setBody(
            """{"status":"FAILED","error_detail":"insufficient funds"}"""
        ))
        val terminal = SumUpRestTerminal(api, pollIntervalMs = 1L, timeoutMs = 2_000L)
        val outcome = terminal.pay(Money(2000), "tx-2", "Vente")
        assertThat(outcome).isInstanceOf(PaymentOutcome.Declined::class.java)
        assertThat((outcome as PaymentOutcome.Declined).reason).isEqualTo("insufficient funds")
    }

    @Test
    fun `cancellation remonte Cancelled byUser`() = runTest {
        server.enqueue(MockResponse().setBody("""{"checkout_id":"ck3","status":"PENDING"}"""))
        server.enqueue(MockResponse().setBody("""{"status":"CANCELLED"}"""))
        val terminal = SumUpRestTerminal(api, pollIntervalMs = 1L, timeoutMs = 2_000L)
        val outcome = terminal.pay(Money(500), "tx-3", "Vente")
        assertThat(outcome).isInstanceOf(PaymentOutcome.Cancelled::class.java)
    }

    @Test
    fun `timeout remonte Failed`() = runTest {
        server.enqueue(MockResponse().setBody("""{"checkout_id":"ck4","status":"PENDING"}"""))
        // Renvoyer PENDING en boucle — le terminal va timeout
        repeat(20) {
            server.enqueue(MockResponse().setBody("""{"status":"PENDING"}"""))
        }
        val terminal = SumUpRestTerminal(api, pollIntervalMs = 1L, timeoutMs = 50L)
        val outcome = terminal.pay(Money(100), "tx-4", "Vente")
        assertThat(outcome).isInstanceOf(PaymentOutcome.Failed::class.java)
    }
}
