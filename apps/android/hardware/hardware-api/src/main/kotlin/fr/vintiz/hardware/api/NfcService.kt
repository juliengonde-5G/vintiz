package fr.vintiz.hardware.api

import kotlinx.coroutines.flow.Flow

/**
 * Lecture NFC carte fidélité. L'UID hexa lu est ensuite résolu via
 * `GET /api/v1/pos/clients/identify?nfc_uid=...` (alias backend à
 * confirmer côté équipe API, cf. docs §4.4).
 */
interface NfcService {
    fun tags(): Flow<NfcTag>
}

data class NfcTag(val uid: String, val technologies: List<String>)
