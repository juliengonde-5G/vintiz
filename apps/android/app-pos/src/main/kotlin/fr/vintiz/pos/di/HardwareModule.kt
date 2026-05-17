package fr.vintiz.pos.di

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import fr.vintiz.data.hardware.HardwareConfig
import fr.vintiz.data.hardware.HardwareRepository
import fr.vintiz.hardware.api.LabelPrinterService
import fr.vintiz.hardware.api.NfcService
import fr.vintiz.hardware.api.PrinterService
import fr.vintiz.hardware.api.ScannerService
import fr.vintiz.hardware.escpos.tcp.TcpEscPosPrinter
import fr.vintiz.hardware.nfc.AndroidNfcService
import fr.vintiz.hardware.scanner.hid.HidScanner
import fr.vintiz.hardware.zpl.tcp.TcpZebraPrinter
import javax.inject.Singleton
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking

/**
 * Bindings hardware. Le choix imprimante (USB vs réseau) et TPE
 * (SDK vs REST) est piloté par `AppPreferences` côté UI, mais l'impl
 * concrète injectée par Hilt est résolue à la 1ʳᵉ utilisation via la
 * config Room `hardware_config` (singleton). En V1, on prend le mode
 * réseau (TCP 9100) par défaut, robuste et toujours dispo.
 */
@Module
@InstallIn(SingletonComponent::class)
object HardwareModule {

    @Provides @Singleton
    fun provideHidScanner(): HidScanner = HidScanner()

    @Provides @Singleton
    fun provideScannerService(hid: HidScanner): ScannerService = hid

    @Provides @Singleton
    fun provideAndroidNfcService(): AndroidNfcService = AndroidNfcService()

    @Provides @Singleton
    fun provideNfcService(svc: AndroidNfcService): NfcService = svc

    /**
     * PrinterService — résolution lazy au 1ᵉʳ appel via la config
     * Room. Si la config n'est pas chargée (1ʳᵉ install), on retombe
     * sur le défaut documenté (10.0.0.20:9100, cf.
     * docs/ANDROID_PROD_OPS.md §4.1).
     */
    @Provides @Singleton
    fun providePrinterService(hardwareRepo: HardwareRepository): PrinterService {
        val config = runBlocking { hardwareRepo.observe().first() }
            ?: defaultHardwareConfig()
        return TcpEscPosPrinter(
            host = config.receiptPrinterHost ?: "10.0.0.20",
            port = config.receiptPrinterPort,
            drawerPin = config.drawerKickPin,
            drawerOnMs = config.drawerOnMs,
            drawerOffMs = config.drawerOffMs,
        )
    }

    @Provides @Singleton
    fun provideLabelPrinterService(hardwareRepo: HardwareRepository): LabelPrinterService {
        val config = runBlocking { hardwareRepo.observe().first() }
            ?: defaultHardwareConfig()
        return TcpZebraPrinter(
            host = config.labelPrinterHost ?: "10.0.0.21",
            port = config.labelPrinterPort,
        )
    }

    private fun defaultHardwareConfig() = HardwareConfig(
        receiptPrinterHost = "10.0.0.20",
        receiptPrinterPort = 9100,
        receiptPrinterUsb = false,
        labelPrinterHost = "10.0.0.21",
        labelPrinterPort = 9100,
        drawerKickOnCash = true,
        drawerKickPin = 0,
        drawerOnMs = 50,
        drawerOffMs = 250,
    )
}
