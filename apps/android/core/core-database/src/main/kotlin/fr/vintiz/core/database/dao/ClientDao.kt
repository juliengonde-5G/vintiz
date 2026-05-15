package fr.vintiz.core.database.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import fr.vintiz.core.database.entity.ClientCacheEntity

@Dao
interface ClientDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<ClientCacheEntity>)

    @Query("SELECT * FROM clients_cache WHERE id = :id")
    suspend fun byId(id: String): ClientCacheEntity?

    @Query("SELECT * FROM clients_cache WHERE email = :email LIMIT 1")
    suspend fun byEmail(email: String): ClientCacheEntity?

    @Query("SELECT * FROM clients_cache WHERE membershipNumber = :v LIMIT 1")
    suspend fun byMembership(v: String): ClientCacheEntity?

    @Query("SELECT * FROM clients_cache WHERE nfcUid = :uid LIMIT 1")
    suspend fun byNfcUid(uid: String): ClientCacheEntity?

    @Query("""
        SELECT * FROM clients_cache
        WHERE firstName LIKE '%' || :q || '%'
           OR lastName  LIKE '%' || :q || '%'
           OR email     LIKE '%' || :q || '%'
           OR phone     LIKE '%' || :q || '%'
        ORDER BY lastName ASC LIMIT 20
    """)
    suspend fun search(q: String): List<ClientCacheEntity>

    /** TTL 30 j RGPD — appelée par PurgePIIWorker. */
    @Query("DELETE FROM clients_cache WHERE cachedAt < :threshold")
    suspend fun purgeOlderThan(threshold: Long): Int

    @Query("DELETE FROM clients_cache")
    suspend fun clear()
}
