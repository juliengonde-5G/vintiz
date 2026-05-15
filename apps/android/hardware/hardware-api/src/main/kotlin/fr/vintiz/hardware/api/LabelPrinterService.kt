package fr.vintiz.hardware.api

import fr.vintiz.core.common.VintizResult

/**
 * Imprimante d'étiquettes ZPL (Zebra ZD421d en boutique Vintiz, 80×120 mm).
 * Le ZPL est généré côté backend par
 * `apps/api/app/services/zebra_zpl.py` puis envoyé en TCP 9100.
 */
interface LabelPrinterService {

    suspend fun isReady(): VintizResult<Boolean>

    suspend fun printZpl(zpl: String): VintizResult<Unit>
}
