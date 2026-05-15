package fr.vintiz.pos.di

import android.content.Context
import androidx.room.Room
import dagger.Lazy
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import fr.vintiz.core.database.VintizDatabase
import fr.vintiz.core.database.dao.ClientDao
import fr.vintiz.core.database.dao.HardwareConfigDao
import fr.vintiz.core.database.dao.ProductDao
import fr.vintiz.core.database.dao.QueuedTransactionDao
import fr.vintiz.core.datastore.AppPreferences
import fr.vintiz.core.network.HttpClientFactory
import fr.vintiz.core.security.AndroidTokenStorage
import fr.vintiz.core.security.TokenStorage
import fr.vintiz.data.auth.AuthApi
import fr.vintiz.data.auth.AuthRepository
import fr.vintiz.data.clients.ClientsApi
import fr.vintiz.data.clients.ClientsRepository
import fr.vintiz.data.hardware.HardwareApi
import fr.vintiz.data.hardware.HardwareRepository
import fr.vintiz.data.inventory.InventoryApi
import fr.vintiz.data.inventory.InventoryRepository
import fr.vintiz.data.pos.PosApi
import fr.vintiz.data.pos.PosRepository
import fr.vintiz.hardware.api.PaymentTerminalService
import fr.vintiz.hardware.sumup.rest.SumUpRestApi
import fr.vintiz.hardware.sumup.rest.SumUpRestTerminal
import fr.vintiz.pos.BuildConfig
import javax.inject.Singleton
import kotlinx.coroutines.runBlocking
import retrofit2.Retrofit

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides @Singleton
    fun provideTokenStorage(@ApplicationContext context: Context): TokenStorage =
        AndroidTokenStorage(context)

    @Provides @Singleton
    fun provideAppPreferences(@ApplicationContext context: Context): AppPreferences =
        AppPreferences(context)

    @Provides @Singleton
    fun provideDatabase(@ApplicationContext context: Context): VintizDatabase =
        Room.databaseBuilder(context, VintizDatabase::class.java, VintizDatabase.DB_NAME).build()

    @Provides fun provideQueueDao(db: VintizDatabase): QueuedTransactionDao = db.queuedTransactions()
    @Provides fun provideProductDao(db: VintizDatabase): ProductDao = db.products()
    @Provides fun provideClientDao(db: VintizDatabase): ClientDao = db.clients()
    @Provides fun provideHardwareConfigDao(db: VintizDatabase): HardwareConfigDao = db.hardwareConfig()

    @Provides @Singleton
    fun provideHttpClientFactory(
        tokenStorage: TokenStorage,
        authRepositoryLazy: Lazy<AuthRepository>,
    ): HttpClientFactory = HttpClientFactory(
        tokenStorage = tokenStorage,
        baseUrl = BuildConfig.API_BASE_URL,
        clientId = "${BuildConfig.CLIENT_ID}/${BuildConfig.VERSION_NAME}",
        debug = BuildConfig.DEBUG,
        refreshToken = { old -> authRepositoryLazy.get().refresh(old) },
        runBlocking = { block -> runBlocking { block() } },
    )

    @Provides @Singleton
    fun provideRetrofit(factory: HttpClientFactory): Retrofit = factory.retrofit

    @Provides @Singleton fun provideAuthApi(r: Retrofit): AuthApi = r.create(AuthApi::class.java)
    @Provides @Singleton fun providePosApi(r: Retrofit): PosApi = r.create(PosApi::class.java)
    @Provides @Singleton fun provideInventoryApi(r: Retrofit): InventoryApi = r.create(InventoryApi::class.java)
    @Provides @Singleton fun provideClientsApi(r: Retrofit): ClientsApi = r.create(ClientsApi::class.java)
    @Provides @Singleton fun provideHardwareApi(r: Retrofit): HardwareApi = r.create(HardwareApi::class.java)
    @Provides @Singleton fun provideSumUpRestApi(r: Retrofit): SumUpRestApi = r.create(SumUpRestApi::class.java)

    @Provides @Singleton
    fun provideAuthRepository(api: AuthApi, tokens: TokenStorage): AuthRepository =
        AuthRepository(api, tokens)

    @Provides @Singleton
    fun providePosRepository(
        api: PosApi,
        queue: QueuedTransactionDao,
        factory: HttpClientFactory,
    ): PosRepository = PosRepository(api, queue, factory.moshi)

    @Provides @Singleton
    fun provideInventoryRepository(api: InventoryApi, dao: ProductDao): InventoryRepository =
        InventoryRepository(api, dao)

    @Provides @Singleton
    fun provideClientsRepository(api: ClientsApi, dao: ClientDao): ClientsRepository =
        ClientsRepository(api, dao)

    @Provides @Singleton
    fun provideHardwareRepository(api: HardwareApi, dao: HardwareConfigDao): HardwareRepository =
        HardwareRepository(api, dao)

    @Provides @Singleton
    fun providePaymentTerminal(api: SumUpRestApi): PaymentTerminalService =
        SumUpRestTerminal(api)
}
