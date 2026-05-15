package fr.vintiz.hardware.nfc

import android.content.Intent
import android.nfc.NfcAdapter
import android.nfc.Tag
import fr.vintiz.hardware.api.NfcService
import fr.vintiz.hardware.api.NfcTag
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import timber.log.Timber

/**
 * Reçoit les `Intent` NFC dispatché par l'OS Android (foreground
 * dispatch ou intent ACTION_NDEF_DISCOVERED / ACTION_TAG_DISCOVERED) et
 * émet l'UID hexa pour résolution `/api/v1/pos/clients/identify?nfc_uid=`.
 *
 * L'activité hôte (POS / Clients) appelle [handleIntent] depuis
 * `onNewIntent` après s'être enregistrée via
 * `NfcAdapter.enableForegroundDispatch`.
 */
class AndroidNfcService : NfcService {

    private val flow = MutableSharedFlow<NfcTag>(
        replay = 0,
        extraBufferCapacity = 4,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )

    fun handleIntent(intent: Intent): Boolean {
        val action = intent.action ?: return false
        if (action !in NFC_ACTIONS) return false
        val tag: Tag = intent.getParcelableExtra(NfcAdapter.EXTRA_TAG) ?: return false
        val uid = tag.id.toHexString()
        val techs = tag.techList.toList()
        Timber.d("NFC tag uid=%s techs=%s", uid, techs)
        flow.tryEmit(NfcTag(uid = uid, technologies = techs))
        return true
    }

    override fun tags(): Flow<NfcTag> = flow.asSharedFlow()

    private companion object {
        val NFC_ACTIONS = setOf(
            NfcAdapter.ACTION_TAG_DISCOVERED,
            NfcAdapter.ACTION_TECH_DISCOVERED,
            NfcAdapter.ACTION_NDEF_DISCOVERED,
        )
    }
}

private fun ByteArray.toHexString(): String =
    joinToString(separator = "") { "%02X".format(it) }
