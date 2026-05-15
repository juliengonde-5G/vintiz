package fr.vintiz.core.database.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import fr.vintiz.core.database.entity.HardwareConfigEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface HardwareConfigDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: HardwareConfigEntity)

    @Query("SELECT * FROM hardware_config WHERE id = ${HardwareConfigEntity.SINGLETON_ID}")
    suspend fun current(): HardwareConfigEntity?

    @Query("SELECT * FROM hardware_config WHERE id = ${HardwareConfigEntity.SINGLETON_ID}")
    fun observe(): Flow<HardwareConfigEntity?>
}
