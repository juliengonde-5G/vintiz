package fr.vintiz.core.database.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Queue locale des ventes POS en attente d'envoi (mode offline).
 *
 * La clé primaire `client_uuid` est l'identifiant idempotent généré par
 * l'app avant le 1er POST `/api/v1/pos/transactions` — replay safe côté
 * serveur grâce à `apps/api/app/services/pos.py:68-76`.
 *
 * `payload_json` contient le corps complet du POST sérialisé en Moshi
 * (items + payments + cashier_id + client_id + …). On ne dénormalise
 * pas pour éviter la dérive de schéma : le backend reste la source de
 * vérité du format.
 */
@Entity(tableName = "queued_transactions")
data class QueuedTransactionEntity(
    @PrimaryKey val clientUuid: String,
    val payloadJson: String,
    val createdAt: Long,
    val attempts: Int = 0,
    val lastError: String? = null,
    val lastAttemptAt: Long? = null,
)
