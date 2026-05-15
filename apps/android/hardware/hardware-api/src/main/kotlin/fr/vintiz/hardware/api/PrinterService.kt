package fr.vintiz.hardware.api

import fr.vintiz.core.common.VintizResult

/**
 * Imprimante de tickets ESC/POS (MUNBYN 047P en boutique Vintiz).
 *
 * Les bytes sont produits côté backend par
 * `apps/api/app/services/escpos_service.py` puis téléchargés via
 * `GET /api/v1/pos/transactions/{id}/escpos` — le client Android se
 * contente de les transmettre. Aucun rendu local : la signature NF525
 * reste 100 % serveur (cf. docs/MIGRATION_ANDROID_NATIVE.md §5.3
 * règle d'or n°7).
 */
interface PrinterService {

    suspend fun isReady(): VintizResult<Boolean>

    suspend fun printReceipt(bytes: ByteArray): VintizResult<Unit>

    /**
     * Impulsion `ESC p m t1 t2` qui ouvre le tiroir Safescan SD-4141
     * câblé en RJ-12 sur l'imprimante. Voir
     * `escpos_service.build_drawer_kick`.
     */
    suspend fun openDrawer(): VintizResult<Unit>
}
