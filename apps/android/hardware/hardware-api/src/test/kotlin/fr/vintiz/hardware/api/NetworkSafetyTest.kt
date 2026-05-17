package fr.vintiz.hardware.api

import com.google.common.truth.Truth.assertThat
import org.junit.jupiter.api.Test

class NetworkSafetyTest {

    @Test
    fun `accepte les blocs RFC 1918`() {
        listOf(
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.1.10",
            "192.168.0.1",
        ).forEach { assertThat(it.isPrivateLanTarget()).isTrue() }
    }

    @Test
    fun `accepte loopback et link-local`() {
        assertThat("127.0.0.1".isPrivateLanTarget()).isTrue()
        assertThat("169.254.1.1".isPrivateLanTarget()).isTrue()
    }

    @Test
    fun `accepte les hostnames mDNS local`() {
        assertThat("munbyn.local".isPrivateLanTarget()).isTrue()
        assertThat("zebra-zd421d.local".isPrivateLanTarget()).isTrue()
    }

    @Test
    fun `refuse les IPs publiques`() {
        listOf(
            "8.8.8.8",
            "1.1.1.1",
            "172.15.0.1",  // hors plage 16-31
            "172.32.0.1",  // hors plage 16-31
            "192.169.0.1",
            "11.0.0.1",
        ).forEach { assertThat(it.isPrivateLanTarget()).isFalse() }
    }

    @Test
    fun `refuse les domaines internet`() {
        listOf("api.vintiz.fr", "vintiz.fr", "google.com").forEach {
            assertThat(it.isPrivateLanTarget()).isFalse()
        }
    }

    @Test
    fun `refuse les inputs malformés`() {
        listOf("", "   ", "300.0.0.1", "192.168.1", "abc.def.ghi.jkl", "::1")
            .forEach { assertThat(it.isPrivateLanTarget()).isFalse() }
    }

    @Test
    fun `tolere casse et espaces`() {
        assertThat("  MUNBYN.LOCAL  ".isPrivateLanTarget()).isTrue()
        assertThat("  192.168.1.10  ".isPrivateLanTarget()).isTrue()
    }
}
