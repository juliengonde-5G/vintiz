package fr.vintiz.hardware.api

/**
 * Petites séquences ESC/POS produites côté client (vs le ticket complet
 * qui vient du backend). Pour l'instant : kick tiroir.
 *
 * Source canonique : `apps/api/app/services/escpos_service.py:build_drawer_kick`.
 * Si la valeur des champs change côté backend, mettre à jour les deux.
 */
object EscPosBytes {

    private const val ESC = 0x1B.toByte()

    /**
     * @param pin 0 = pin 2 (défaut Safescan SD-4141), 1 = pin 5.
     * @param onMs durée d'impulsion en ms (50 par défaut, max 510).
     * @param offMs durée d'attente off en ms (250 par défaut, max 510).
     */
    fun drawerKick(pin: Int = 0, onMs: Int = 50, offMs: Int = 250): ByteArray {
        require(pin == 0 || pin == 1) { "pin doit être 0 (pin 2) ou 1 (pin 5)" }
        require(onMs in 0..510) { "onMs hors borne ESC/POS (0..510)" }
        require(offMs in 0..510) { "offMs hors borne ESC/POS (0..510)" }
        return byteArrayOf(
            ESC,
            'p'.code.toByte(),
            pin.toByte(),
            (onMs / 2).toByte(),
            (offMs / 2).toByte(),
        )
    }
}
