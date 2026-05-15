package fr.vintiz.core.database

import androidx.room.Database
import androidx.room.RoomDatabase
import fr.vintiz.core.database.dao.ClientDao
import fr.vintiz.core.database.dao.HardwareConfigDao
import fr.vintiz.core.database.dao.ProductDao
import fr.vintiz.core.database.dao.QueuedTransactionDao
import fr.vintiz.core.database.entity.ClientCacheEntity
import fr.vintiz.core.database.entity.HardwareConfigEntity
import fr.vintiz.core.database.entity.ProductCacheEntity
import fr.vintiz.core.database.entity.QueuedTransactionEntity

@Database(
    entities = [
        QueuedTransactionEntity::class,
        ProductCacheEntity::class,
        ClientCacheEntity::class,
        HardwareConfigEntity::class,
    ],
    version = 1,
    exportSchema = true,
)
abstract class VintizDatabase : RoomDatabase() {
    abstract fun queuedTransactions(): QueuedTransactionDao
    abstract fun products(): ProductDao
    abstract fun clients(): ClientDao
    abstract fun hardwareConfig(): HardwareConfigDao

    companion object {
        const val DB_NAME = "vintiz.db"
    }
}
