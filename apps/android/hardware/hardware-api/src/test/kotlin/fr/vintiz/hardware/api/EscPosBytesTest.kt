package fr.vintiz.hardware.api

import com.google.common.truth.Truth.assertThat
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class EscPosBytesTest {

    @Test
    fun `drawer kick par defaut produit ESC p 0 25 125`() {
        val bytes = EscPosBytes.drawerKick()
        assertThat(bytes).isEqualTo(
            byteArrayOf(0x1B, 'p'.code.toByte(), 0, 25, 125)
        )
    }

    @Test
    fun `drawer kick pin 1 utilise pin 5 sur RJ-12`() {
        val bytes = EscPosBytes.drawerKick(pin = 1)
        assertThat(bytes[2]).isEqualTo(1.toByte())
    }

    @Test
    fun `drawer kick divise les ms par 2 comme escpos_service le fait`() {
        val bytes = EscPosBytes.drawerKick(onMs = 100, offMs = 200)
        assertThat(bytes[3]).isEqualTo(50.toByte())
        assertThat(bytes[4]).isEqualTo(100.toByte())
    }

    @Test
    fun `drawer kick pin invalide refuse`() {
        assertThrows<IllegalArgumentException> { EscPosBytes.drawerKick(pin = 2) }
    }

    @Test
    fun `drawer kick onMs hors borne refuse`() {
        assertThrows<IllegalArgumentException> { EscPosBytes.drawerKick(onMs = 511) }
    }
}
