package fr.vintiz.hardware.escpos.tcp

import com.google.common.truth.Truth.assertThat
import fr.vintiz.core.common.VintizResult
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import java.net.ServerSocket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class TcpEscPosPrinterTest {

    private lateinit var server: ServerSocket
    private val executor = Executors.newSingleThreadExecutor()
    @Volatile
    private var lastPayload: ByteArray? = null

    @BeforeEach
    fun setUp() {
        server = ServerSocket(0)
        executor.submit {
            while (!server.isClosed) {
                runCatching {
                    server.accept().use { client ->
                        lastPayload = client.getInputStream().readAllBytes()
                    }
                }
            }
        }
    }

    @AfterEach
    fun tearDown() {
        server.close()
        executor.shutdownNow()
        executor.awaitTermination(2, TimeUnit.SECONDS)
    }

    @Test
    fun `printReceipt ecrit les bytes sur le socket`() = runTest {
        val printer = TcpEscPosPrinter("127.0.0.1", server.localPort)
        val payload = "VINTIZ\n".toByteArray()

        val result = printer.printReceipt(payload)

        assertThat(result).isInstanceOf(VintizResult.Success::class.java)
        // Laisser le serveur thread écrire la valeur
        Thread.sleep(150)
        assertThat(lastPayload).isEqualTo(payload)
    }

    @Test
    fun `openDrawer envoie la sequence ESC p 0 25 125`() = runTest {
        val printer = TcpEscPosPrinter("127.0.0.1", server.localPort)
        val result = printer.openDrawer()

        assertThat(result).isInstanceOf(VintizResult.Success::class.java)
        Thread.sleep(150)
        assertThat(lastPayload).isEqualTo(byteArrayOf(0x1B, 'p'.code.toByte(), 0, 25, 125))
    }

    @Test
    fun `isReady renvoie Success false-friendly quand l hote est injoignable`() = runTest {
        val printer = TcpEscPosPrinter("127.0.0.1", 1, connectTimeoutMs = 100)
        val result = printer.isReady()
        assertThat(result).isInstanceOf(VintizResult.Failure::class.java)
    }
}
