package fr.vintiz.hardware.escpos.tcp

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.hardware.api.EscPosBytes
import fr.vintiz.hardware.api.PrinterService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import timber.log.Timber
import java.io.IOException
import java.net.InetSocketAddress
import java.net.Socket

/**
 * Reproduit le chemin TCP utilisé par
 * `apps/api/app/services/escpos_service.py:send_raw` : socket vers
 * (host, port=9100), écriture des bytes, fermeture. Le backend conserve
 * le verrou par host+port pour éviter l'interleaving — on déporte la
 * sérialisation côté caller (Hilt @Singleton garantit une seule
 * instance par appareil, donc une seule connexion à la fois en
 * pratique).
 *
 * Retries : 3 tentatives avec backoff exponentiel (300 / 600 / 1200 ms)
 * pour absorber les pertes de paquets Wi-Fi sans bloquer la caisse.
 */
class TcpEscPosPrinter(
    private val host: String,
    private val port: Int = 9100,
    private val connectTimeoutMs: Int = 1500,
    private val drawerPin: Int = 0,
    private val drawerOnMs: Int = 50,
    private val drawerOffMs: Int = 250,
    private val socketFactory: SocketFactory = SocketFactory.Default,
) : PrinterService {

    fun interface SocketFactory {
        fun newSocket(): Socket
        companion object {
            val Default: SocketFactory = SocketFactory { Socket() }
        }
    }

    override suspend fun isReady(): VintizResult<Boolean> = withContext(Dispatchers.IO) {
        runCatching {
            socketFactory.newSocket().use { socket ->
                socket.connect(InetSocketAddress(host, port), connectTimeoutMs)
                true
            }
        }.fold(
            onSuccess = { VintizResult.Success(it) },
            onFailure = { e ->
                Timber.d(e, "MUNBYN ping KO sur %s:%d", host, port)
                VintizResult.Failure(networkError(e))
            },
        )
    }

    override suspend fun printReceipt(bytes: ByteArray): VintizResult<Unit> =
        sendWithRetry(bytes)

    override suspend fun openDrawer(): VintizResult<Unit> =
        sendWithRetry(EscPosBytes.drawerKick(drawerPin, drawerOnMs, drawerOffMs))

    private suspend fun sendWithRetry(payload: ByteArray): VintizResult<Unit> =
        withContext(Dispatchers.IO) {
            var lastError: Throwable? = null
            for (attempt in 0 until RETRIES.size) {
                try {
                    socketFactory.newSocket().use { socket ->
                        socket.connect(InetSocketAddress(host, port), connectTimeoutMs)
                        socket.getOutputStream().apply {
                            write(payload)
                            flush()
                        }
                    }
                    return@withContext VintizResult.Success(Unit)
                } catch (io: IOException) {
                    lastError = io
                    Timber.w(io, "MUNBYN write KO (tentative %d/%d)", attempt + 1, RETRIES.size)
                    if (attempt < RETRIES.size - 1) {
                        Thread.sleep(RETRIES[attempt])
                    }
                }
            }
            VintizResult.Failure(networkError(lastError))
        }

    private fun networkError(cause: Throwable?): VintizError = VintizError.Unknown(
        message = "MUNBYN injoignable sur $host:$port",
        cause = cause,
    )

    private companion object {
        val RETRIES = longArrayOf(300L, 600L, 1200L)
    }
}
