package fr.vintiz.hardware.zpl.tcp

import com.google.common.truth.Truth.assertThat
import fr.vintiz.core.common.VintizResult
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import java.net.ServerSocket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class TcpZebraPrinterTest {

    private lateinit var server: ServerSocket
    private val executor = Executors.newSingleThreadExecutor()
    @Volatile
    private var lastPayload: String? = null

    @BeforeEach
    fun setUp() {
        server = ServerSocket(0)
        executor.submit {
            while (!server.isClosed) {
                runCatching {
                    server.accept().use { client ->
                        lastPayload = String(client.getInputStream().readAllBytes(), Charsets.UTF_8)
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
    fun `printZpl envoie le texte en UTF-8`() = runTest {
        val printer = TcpZebraPrinter("127.0.0.1", server.localPort)
        val zpl = "^XA^CI28^FO0,0^A0N,40,40^FDVintiz éàç^FS^XZ"

        val result = printer.printZpl(zpl)

        assertThat(result).isInstanceOf(VintizResult.Success::class.java)
        Thread.sleep(150)
        assertThat(lastPayload).isEqualTo(zpl)
    }

    @Test
    fun `isReady remonte un echec quand le port est mort`() = runTest {
        val printer = TcpZebraPrinter("127.0.0.1", 1, connectTimeoutMs = 100)
        val result = printer.isReady()
        assertThat(result).isInstanceOf(VintizResult.Failure::class.java)
    }
}
