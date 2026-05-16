package fr.vintiz.feature.fiscal

import com.google.common.truth.Truth.assertThat
import org.junit.jupiter.api.Test

class FiscalDateValidatorTest {

    @Test
    fun `vide ou null OK des deux cotes`() {
        assertThat(FiscalDateValidator.validate(null, null)).isNull()
        assertThat(FiscalDateValidator.validate("", "")).isNull()
        assertThat(FiscalDateValidator.validate("2026-01-01", null)).isNull()
        assertThat(FiscalDateValidator.validate(null, "2026-12-31")).isNull()
    }

    @Test
    fun `format invalide rejete des deux cotes`() {
        assertThat(FiscalDateValidator.validate("2026/01/01", null))
            .contains("date début invalide")
        assertThat(FiscalDateValidator.validate(null, "2026-1-1"))
            .contains("date fin invalide")
        assertThat(FiscalDateValidator.validate("janvier", null))
            .contains("date début invalide")
    }

    @Test
    fun `from doit etre avant to`() {
        assertThat(FiscalDateValidator.validate("2026-12-31", "2026-01-01"))
            .isEqualTo("La date de début doit être avant la date de fin")
        // Égalité tolérée (export d'une journée).
        assertThat(FiscalDateValidator.validate("2026-05-15", "2026-05-15")).isNull()
    }

    @Test
    fun `intervalle valide OK`() {
        assertThat(FiscalDateValidator.validate("2026-01-01", "2026-12-31")).isNull()
    }
}
