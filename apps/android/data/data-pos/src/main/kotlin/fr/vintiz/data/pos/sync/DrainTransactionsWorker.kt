package fr.vintiz.data.pos.sync

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import fr.vintiz.data.pos.PosRepository
import timber.log.Timber

class DrainTransactionsWorker(
    appContext: Context,
    params: WorkerParameters,
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
