package fr.vintiz.data.inventory.sync

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import fr.vintiz.core.common.VintizResult
import fr.vintiz.core.datastore.AppPreferences
import fr.vintiz.data.inventory.InventoryRepository
import kotlinx.coroutines.flow.first
import timber.log.Timber

/**
 * Sync les produits par lots toutes les heures. Stratégie naïve V1 :
 * on relit la liste paginée full et upsert. V2 utilisera
 * `?updated_since=<epoch>` côté backend (à implémenter API) pour
 * limiter la bande passante.
 */
@HiltWorker
class SyncProductsWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted params: WorkerParameters,
    private val repo: InventoryRepository,
    private val prefs: AppPreferences,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val lastSync = prefs.lastProductsSync.first()
        Timber.d("SyncProducts — lastSync=%d", lastSync)
        // V1 : on relit la 1ʳᵉ page (50 produits). Le repo upsert dans
        // products_cache. Pour la pagination complète, voir TODO V2.
        return when (repo.search("")) {
            is VintizResult.Success -> {
                prefs.setLastProductsSync(System.currentTimeMillis() / 1000)
                Result.success()
            }
            is VintizResult.Failure -> Result.retry()
        }
    }

    companion object {
        const val UNIQUE_NAME = "sync_products"
    }
}
