package fr.vintiz.core.database.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import fr.vintiz.core.database.entity.ProductCacheEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ProductDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<ProductCacheEntity>)

    @Query("SELECT * FROM products_cache WHERE id = :id")
    suspend fun byId(id: String): ProductCacheEntity?

    @Query("SELECT * FROM products_cache WHERE barcode = :barcode LIMIT 1")
    suspend fun byBarcode(barcode: String): ProductCacheEntity?

    @Query("""
        SELECT * FROM products_cache
        WHERE name LIKE '%' || :query || '%' OR barcode LIKE '%' || :query || '%'
        ORDER BY updatedAt DESC LIMIT :limit
    """)
    suspend fun search(query: String, limit: Int = 20): List<ProductCacheEntity>

    @Query("SELECT * FROM products_cache ORDER BY updatedAt DESC LIMIT :limit OFFSET :offset")
    fun page(limit: Int, offset: Int): Flow<List<ProductCacheEntity>>

    @Query("DELETE FROM products_cache")
    suspend fun clear()
}
