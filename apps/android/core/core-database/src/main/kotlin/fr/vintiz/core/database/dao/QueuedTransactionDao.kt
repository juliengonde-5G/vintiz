package fr.vintiz.core.database.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import fr.vintiz.core.database.entity.QueuedTransactionEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface QueuedTransactionDao {

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun enqueue(entity: QueuedTransactionEntity)

    @Query("SELECT * FROM queued_transactions ORDER BY createdAt ASC")
    fun pending(): Flow<List<QueuedTransactionEntity>>

    @Query("SELECT * FROM queued_transactions ORDER BY createdAt ASC LIMIT :limit")
    suspend fun nextBatch(limit: Int = 20): List<QueuedTransactionEntity>

    @Query(
        """UPDATE queued_transactions
           SET attempts = attempts + 1, lastError = :error, lastAttemptAt = :now
           WHERE clientUuid = :clientUuid"""
    )
    suspend fun markFailure(clientUuid: String, error: String, now: Long)

    @Query("DELETE FROM queued_transactions WHERE clientUuid = :clientUuid")
    suspend fun delete(clientUuid: String)

    @Query("SELECT COUNT(*) FROM queued_transactions")
    fun count(): Flow<Int>
}
