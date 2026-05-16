package fr.vintiz.domain.inventory

import com.google.common.truth.Truth.assertThat
import org.junit.jupiter.api.Test

class BarcodeNormalizerTest {

    @Test
    fun `strippe espaces et controles`() {
        assertThat(BarcodeNormalizer.normalize("  123 456\n")).isEqualTo("123456")
        assertThat(BarcodeNormalizer.normalize("  abc\r\n")).isEqualTo("abc")
        assertThat(BarcodeNormalizer.normalize("\tVTZ-001 ")).isEqualTo("VTZ-001")
    }

    @Test
    fun `statut decode fallback Unknown`() {
        assertThat(ProductStatus.fromKey("in_stock")).isEqualTo(ProductStatus.InStock)
        assertThat(ProductStatus.fromKey(null)).isEqualTo(ProductStatus.Unknown)
        assertThat(ProductStatus.fromKey("inexistant")).isEqualTo(ProductStatus.Unknown)
    }

    @Test
    fun `regex couvre NBSP et separateurs unicode`() {
        // NBSP   (configurations keyboard wedge françaises)
        assertThat(BarcodeNormalizer.normalize("VTZ 001")).isEqualTo("VTZ001")
        // Em space
        assertThat(BarcodeNormalizer.normalize("AB CD")).isEqualTo("ABCD")
        // Mixed
        assertThat(BarcodeNormalizer.normalize(" V\t T Z \n")).isEqualTo("VTZ")
    }

    @Test
    fun `chaine deja propre reste inchangee`() {
        assertThat(BarcodeNormalizer.normalize("VTZ-2026-00142")).isEqualTo("VTZ-2026-00142")
        assertThat(BarcodeNormalizer.normalize("3210987654321")).isEqualTo("3210987654321")
    }

    @Test
    fun `vide reste vide`() {
        assertThat(BarcodeNormalizer.normalize("")).isEqualTo("")
        assertThat(BarcodeNormalizer.normalize("   \n\t  ")).isEqualTo("")
    }
}
