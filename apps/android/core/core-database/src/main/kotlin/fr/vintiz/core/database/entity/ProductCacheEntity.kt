package fr.vintiz.core.database.entity

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "products_cache",
    indices = [Index("barcode", unique = false)],
)
data class ProductCacheEntity(
    @PrimaryKey val id: String,
    val barcode: String?,
    val name: String,
    val priceCents: Long,
    val tvaRate: Double,
    val category: String?,
    val photoUrl: String?,
    val status: String,
    val updatedAt: Long,
)
