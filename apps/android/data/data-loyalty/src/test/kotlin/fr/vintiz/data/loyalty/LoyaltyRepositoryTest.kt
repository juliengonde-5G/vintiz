package fr.vintiz.data.loyalty

import com.google.common.truth.Truth.assertThat
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

class LoyaltyRepositoryTest {

    private lateinit var server: MockWebServer
    private lateinit var repo: LoyaltyRepository

    @BeforeEach
    fun setUp() {
        server = MockWebServer().apply { start() }
        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        val api = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
            .create(LoyaltyApi::class.java)
        repo = LoyaltyRepository(api)
    }

    @AfterEach
    fun tearDown() { server.shutdown() }

    @Test
    fun `subscribe OK retourne la carte`() = runTest {
        server.enqueue(MockResponse().setBody(
            """{"id":"c1","membership_number":"V000123","first_name":"Léa",
                "last_name":"Martin","email":"lea@example.fr","loyalty_points":0}"""
                .replace("\n", "").replace("                ", "")
        ))
        val r = repo.subscribe(LoyaltySubscribeRequest(
            email = "lea@example.fr", first_name = "Léa", last_name = "Martin",
        ))
        assertThat(r).isInstanceOf(VintizResult.Success::class.java)
        val card = (r as VintizResult.Success).value
        assertThat(card.membership_number).isEqualTo("V000123")
    }

    @Test
    fun `subscribe 409 retourne Validation email deja inscrite`() = runTest {
        server.enqueue(MockResponse().setResponseCode(409))
        val r = repo.subscribe(LoyaltySubscribeRequest(
            email = "exist@example.fr", first_name = "X", last_name = "Y",
        ))
        assertThat(r).isInstanceOf(VintizResult.Failure::class.java)
        val err = (r as VintizResult.Failure).error
        assertThat(err).isInstanceOf(VintizError.Validation::class.java)
        assertThat((err as VintizError.Validation).field).isEqualTo("email")
    }

    @Test
    fun `validateCoupon valid retourne Success avec new_total_cents`() = runTest {
        server.enqueue(MockResponse().setBody(
            """{"code":"VINTIZ10","valid":true,"discount_cents":200,
                "discount_percent":10,"new_total_cents":1800,"applies_to":"cart"}"""
                .replace("\n", "").replace("                ", "")
        ))
        val r = repo.validateCoupon("VINTIZ10", cartTotalCents = 2000)
        assertThat(r).isInstanceOf(VintizResult.Success::class.java)
        val preview = (r as VintizResult.Success).value
        assertThat(preview.new_total_cents).isEqualTo(1800)
        assertThat(preview.discount_percent).isEqualTo(10)
    }

    @Test
    fun `validateCoupon invalide retourne Validation avec reason`() = runTest {
        server.enqueue(MockResponse().setBody(
            """{"code":"EXPIRED","valid":false,"reason":"Coupon expiré",
                "new_total_cents":2000}"""
                .replace("\n", "").replace("                ", "")
        ))
        val r = repo.validateCoupon("EXPIRED", cartTotalCents = 2000)
        assertThat(r).isInstanceOf(VintizResult.Failure::class.java)
        val err = (r as VintizResult.Failure).error
        assertThat(err).isInstanceOf(VintizError.Validation::class.java)
        assertThat((err as VintizError.Validation).message).isEqualTo("Coupon expiré")
    }

    @Test
    fun `validateCoupon 404 retourne Validation code introuvable`() = runTest {
        server.enqueue(MockResponse().setResponseCode(404))
        val r = repo.validateCoupon("UNKNOWN", cartTotalCents = 2000)
        assertThat(r).isInstanceOf(VintizResult.Failure::class.java)
        val err = (r as VintizResult.Failure).error
        assertThat(err).isInstanceOf(VintizError.Validation::class.java)
        assertThat((err as VintizError.Validation).message).isEqualTo("Code introuvable")
    }
}
