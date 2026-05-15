package fr.vintiz.core.database.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "hardware_config")
data class HardwareConfigEntity(
    @PrimaryKey val id: Int = SINGLETON_ID,
    val receiptPrinterHost: String?,
    val receiptPrinterPort: Int,
    val receiptPrinterUsb: Boolean,
    val labelPrinterHost: String?,
    val labelPrinterPort: Int,
    val drawerKickOnCash: Boolean,
    val drawerKickPin: Int,
    val drawerOnMs: Int,
    val drawerOffMs: Int,
    val updatedAt: Long,
) {
    companion object {
        const val SINGLETON_ID = 1
    }
}
