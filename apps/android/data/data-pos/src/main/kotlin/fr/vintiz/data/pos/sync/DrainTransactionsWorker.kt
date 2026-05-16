package fr.vintiz.data.pos.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import fr.vintiz.data.pos.PosRepository
import timber.log.Timber

@HiltWorker
class DrainTransactionsWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val repository: PosRepository,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val report = repository.drainQueue()
        Timber.i(
            "Drain done — processed=%d succeeded=%d failed=%d",
            report.processed, report.succeeded, report.failed,
        )
        return when {
            report.failed > 0 -> Result.retry()
            else -> Result.success()
        }
    }

    companion object {
        const val UNIQUE_NAME = "drain_pos_transactions"
    }
}
