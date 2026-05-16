package fr.vintiz.feature.auth

import com.google.common.truth.Truth.assertThat
import fr.vintiz.core.common.VintizError
import org.junit.jupiter.api.Test

class UserMessageTest {

    @Test
    fun `unauthorized renvoie message non technique`() {
        assertThat(VintizError.Unauthorized.userMessage())
            .isEqualTo("Identifiants incorrects")
    }

    @Test
    fun `rate limit indique le delai retry`() {
        assertThat(VintizError.RateLimit(retryAfterSeconds = 30).userMessage())
            .isEqualTo("Trop de tentatives, réessayer dans 30s")
    }

    @Test
    fun `network propre`() {
        assertThat(VintizError.Network.userMessage())
            .isEqualTo("Connexion indisponible")
    }

    @Test
    fun `http expose code`() {
        assertThat(VintizError.Http(503, "down").userMessage())
            .isEqualTo("Erreur serveur (503)")
    }

    @Test
    fun `unknown fallback message defaut`() {
        assertThat(VintizError.Unknown("boom").userMessage())
            .isEqualTo("boom")
    }
}
