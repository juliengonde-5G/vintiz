package fr.vintiz.hardware.escpos.usb

import android.content.Context
import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager
import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import fr.vintiz.hardware.api.EscPosBytes
import fr.vintiz.hardware.api.PrinterService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import timber.log.Timber

/**
 * Impression ESC/POS directe via USB-OTG sur la MUNBYN 047P.
 * Reproduit `apps/web/src/lib/webusb-printer.ts:sendEscposBytes` :
 * - cherche le 1er endpoint BULK_OUT de l'interface USB Class 7
 *   (printer)
 * - claim l'interface
 * - envoie les bytes en chunks (le firmware MUNBYN stall si on dépasse
 *   wMaxPacketSize × 16 ou ~4 ko)
 * - termine par un zero-length packet si payload % packetSize == 0
 *
 * Si aucun device branché → VintizError.Validation("usb", "...") pour
 * laisser l'UI proposer un fallback réseau ou un re-pairing.
 */
class UsbEscPosPrinter(
    private val context: Context,
    private val deviceFilter: (UsbDevice) -> Boolean = { it.deviceClass == UsbConstants.USB_CLASS_PRINTER },
    private val drawerPin: Int = 0,
    private val drawerOnMs: Int = 50,
    private val drawerOffMs: Int = 250,
) : PrinterService {

    private val usbManager: UsbManager
        get() = context.getSystemService(Context.USB_SERVICE) as UsbManager

    override suspend fun isReady(): VintizResult<Boolean> = withContext(Dispatchers.IO) {
        val device = findDevice()
        if (device == null) {
            VintizResult.Success(false)
        } else if (!usbManager.hasPermission(device)) {
            VintizResult.Failure(VintizError.Validation("usb", "Permission USB non accordée"))
        } else {
            VintizResult.Success(true)
        }
    }

    override suspend fun printReceipt(bytes: ByteArray): VintizResult<Unit> = sendRaw(bytes)

    override suspend fun openDrawer(): VintizResult<Unit> =
        sendRaw(EscPosBytes.drawerKick(drawerPin, drawerOnMs, drawerOffMs))

    private suspend fun sendRaw(payload: ByteArray): VintizResult<Unit> = withContext(Dispatchers.IO) {
        val device = findDevice()
            ?: return@withContext VintizResult.Failure(
                VintizError.Validation("usb", "Aucune imprimante USB détectée")
            )
        if (!usbManager.hasPermission(device)) {
            return@withContext VintizResult.Failure(
                VintizError.Validation("usb", "Permission USB requise")
            )
        }

        val iface: UsbInterface = findPrinterInterface(device)
            ?: return@withContext VintizResult.Failure(
                VintizError.Validation("usb", "Interface imprimante introuvable")
            )
        val outEndpoint = (0 until iface.endpointCount)
            .map { iface.getEndpoint(it) }
            .firstOrNull {
                it.direction == UsbConstants.USB_DIR_OUT &&
                    it.type == UsbConstants.USB_ENDPOINT_XFER_BULK
            }
            ?: return@withContext VintizResult.Failure(
                VintizError.Validation("usb", "Endpoint BULK OUT introuvable")
            )

        val connection: UsbDeviceConnection = usbManager.openDevice(device)
            ?: return@withContext VintizResult.Failure(
                VintizError.Validation("usb", "Impossible d'ouvrir le device USB")
            )

        try {
            if (!connection.claimInterface(iface, true)) {
                return@withContext VintizResult.Failure(
                    VintizError.Validation("usb", "claim interface échoué")
                )
            }
            val chunkSize = (outEndpoint.maxPacketSize * 16).coerceAtLeast(MIN_CHUNK)
            var offset = 0
            while (offset < payload.size) {
                val len = minOf(chunkSize, payload.size - offset)
                val sent = connection.bulkTransfer(outEndpoint, payload, offset, len, BULK_TIMEOUT_MS)
                if (sent < 0) {
                    Timber.w("bulkTransfer KO offset=%d len=%d", offset, len)
                    return@withContext VintizResult.Failure(
                        VintizError.Validation("usb", "Écriture USB interrompue")
                    )
                }
                offset += sent
            }
            if (payload.size % outEndpoint.maxPacketSize == 0) {
                connection.bulkTransfer(outEndpoint, ByteArray(0), 0, 0, BULK_TIMEOUT_MS)
            }
            VintizResult.Success(Unit)
        } finally {
            connection.releaseInterface(iface)
            connection.close()
        }
    }

    private fun findDevice(): UsbDevice? =
        usbManager.deviceList.values.firstOrNull(deviceFilter)

    private fun findPrinterInterface(device: UsbDevice): UsbInterface? =
        (0 until device.interfaceCount)
            .map { device.getInterface(it) }
            .firstOrNull { it.interfaceClass == UsbConstants.USB_CLASS_PRINTER }

    private companion object {
        const val MIN_CHUNK = 4096
        const val BULK_TIMEOUT_MS = 5_000
    }
}
