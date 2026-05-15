package fr.vintiz.core.database.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Cache local cliente — `cachedAt` driver le TTL 30 j RGPD purgé par
 * `PurgePIIWorker` (voir docs/MIGRATION_ANDROID_NATIVE.md §3.4).
 */
@Entity(tableName = "clients_cache")
data class ClientCacheEntity(
    @PrimaryKey val id: String,
    val firstName: String,
    val lastName: String,
    val email: String?,
    val phone: String?,
    val membershipNumber: String?,
    val loyaltyPoints: Int,
    val loyaltyTier: String?,
    val nfcUid: String?,
    val cachedAt: Long,
)
