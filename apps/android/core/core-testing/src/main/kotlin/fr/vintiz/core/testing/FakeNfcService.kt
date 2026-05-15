package fr.vintiz.core.testing

import fr.vintiz.hardware.api.NfcService
import fr.vintiz.hardware.api.NfcTag
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow

class FakeNfcService : NfcService {
    private val flow = MutableSharedFlow<NfcTag>(replay = 0, extraBufferCapacity = 4)
    override fun tags(): Flow<NfcTag> = flow.asSharedFlow()

    suspend fun emit(uid: String, technologies: List<String> = listOf("NfcA")) {
        flow.emit(NfcTag(uid, technologies))
    }
}
