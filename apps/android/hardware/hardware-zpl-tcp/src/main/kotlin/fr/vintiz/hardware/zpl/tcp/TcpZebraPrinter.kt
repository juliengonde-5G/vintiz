package fr.vintiz.hardware.zpl.tcp

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.hardware.api.LabelPrinterService
import fr.vintiz.hardware.api.isPrivateLanTarget
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import timber.log.Timber
import java.io.IOException
import java.net.InetSocketAddress
import java.net.Socket

/**
 * Reproduit `apps/api/app/services/zebra_printer.py:send_zpl` : socket
 * TCP vers (host, port=9100), écriture du ZPL en UTF-8, fermeture.
 *
 * Le ZPL est généré exclusivement côté backend
 * (`apps/api/app/services/zebra_zpl.py`). Toute évolution de template
 * doit y être faite — pas dans l'app Android.
 */
class TcpZebraPrinter(
    private val host: String,
    private val port: Int = 9100,
    private val connectTimeoutMs: Int = 1500,
    private val socketFactory: SocketFactory = SocketFactory.Default,
) : LabelPrinterService {

    fun interface SocketFactory {
        fun newSocket(): Socket
        companion object {
            val Default: SocketFactory = SocketFactory { Socket() }
        }
    }

    override suspend fun isReady(): VintizResult<Boolean> = withContext(Dispatchers.IO) {
        if (!host.isPrivateLanTarget()) {
            return@withContext VintizResult.Failure(
                VintizError.Validation("label.host", "Host Zebra hors LAN ($host)")
            )
        }
        runCatching {
            socketFactory.newSocket().use { socket ->
                socket.connect(InetSocketAddress(host, port), connectTimeoutMs)
                true
            }
        }.fold(
            onSuccess = { VintizResult.Success(it) },
            onFailure = { e ->
                Timber.d(e, "Zebra ping KO sur %s:%d", host, port)
                VintizResult.Failure(networkError(e))
            },
        )
    }

    override suspend fun printZpl(zpl: String): VintizResult<Unit> = withContext(Dispatchers.IO) {
        if (!host.isPrivateLanTarget()) {
            return@withContext VintizResult.Failure(
                VintizError.Validation("label.host", "Host Zebra hors LAN ($host)")
            )
        }
        var lastError: Throwable? = null
        for (attempt in 0 until RETRIES.size) {
            try {
                socketFactory.newSocket().use { socket ->
                    socket.connect(InetSocketAddress(host, port), connectTimeoutMs)
                    socket.getOutputStream().apply {
                        write(zpl.toByteArray(Charsets.UTF_8))
                        flush()
                    }
                }
                return@withContext VintizResult.Success(Unit)
            } catch (io: IOException) {
                lastError = io
                Timber.w(io, "Zebra write KO (tentative %d/%d)", attempt + 1, RETRIES.size)
                if (attempt < RETRIES.size - 1) Thread.sleep(RETRIES[attempt])
            }
        }
        VintizResult.Failure(networkError(lastError))
    }

    private fun networkError(cause: Throwable?): VintizError = VintizError.Unknown(
        message = "Zebra injoignable sur $host:$port",
        cause = cause,
    )

    private companion object {
        val RETRIES = longArrayOf(300L, 600L, 1200L)
    }
}
