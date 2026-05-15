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
}
