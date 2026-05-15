package fr.vintiz.pos.di

import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import fr.vintiz.hardware.api.NfcService
import fr.vintiz.hardware.api.ScannerService
import fr.vintiz.hardware.nfc.AndroidNfcService
import fr.vintiz.hardware.scanner.hid.HidScanner
import javax.inject.Singleton

/**
 * Modules de bas niveau exposant les services hardware singleton. Le
 * choix imprimante (USB vs réseau) et TPE (SDK vs REST) reste piloté
 * par `core:core-datastore:AppPreferences` — les implémentations
 * concrètes seront sélectionnées via un `@Binds` paramétré dans un
 * sprint suivant (data:data-hardware).
 */
@Module
@InstallIn(SingletonComponent::class)
object HardwareModule {

    @Provides @Singleton
    fun provideHidScanner(): HidScanner = HidScanner()

    @Provides @Singleton
    fun provideScannerService(hid: HidScanner): ScannerService = hid

    @Provides @Singleton
    fun provideNfcService(): NfcService = AndroidNfcService()

    @Provides @Singleton
    fun provideAndroidNfcService(svc: NfcService): AndroidNfcService = svc as AndroidNfcService
}
