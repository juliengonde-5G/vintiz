package fr.vintiz.client.di

import android.content.Context
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import fr.vintiz.client.BuildConfig
import fr.vintiz.core.network.HttpClientFactory
import fr.vintiz.core.security.AndroidClientTokenStorage
import fr.vintiz.core.security.ClientTokenStorage
import fr.vintiz.core.security.ClientTokenStorageAdapter
import fr.vintiz.core.security.TokenStorage
import fr.vintiz.data.authclient.ClientAuthApi
import fr.vintiz.data.authclient.ClientAuthRepository
import javax.inject.Singleton
import kotlinx.coroutines.runBlocking
import retrofit2.Retrofit

@Module
@InstallIn(SingletonComponent::class)
object ClientAppModule {

    @Provides @Singleton
    fun provideClientTokenStorage(
        @ApplicationContext context: Context,
    ): ClientTokenStorage = AndroidClientTokenStorage(context)

    /**
     * `HttpClientFactory` reste typé `TokenStorage` pour rester partagé
     * avec :app-pos. L'adapter délègue les méthodes JWT et no-op les
     * méthodes cashier (inutilisées côté client).
     */
    @Provides @Singleton
    fun provideTokenStorageAdapter(
        clientStorage: ClientTokenStorage,
    ): TokenStorage = ClientTokenStorageAdapter(clientStorage)

    @Provides @Singleton
    fun provideHttpClientFactory(
        tokenStorage: TokenStorage,
    ): HttpClientFactory = HttpClientFactory(
        tokenStorage = tokenStorage,
        baseUrl = BuildConfig.API_BASE_URL,
        clientId = "${BuildConfig.CLIENT_ID}/${BuildConfig.VERSION_NAME}",
        debug = BuildConfig.DEBUG,
        // Sprint A : le refresh JWT du flow magic-link n'est pas encore
        // exposé côté backend (cf. plan Sprint E biométrie). Sur 401, on
        // logout simple en retournant null.
        refreshToken = { _ -> null },
        runBlocking = { block -> runBlocking { block() } },
    )

    @Provides @Singleton
    fun provideRetrofit(factory: HttpClientFactory): Retrofit = factory.retrofit

    @Provides @Singleton
    fun provideClientAuthApi(retrofit: Retrofit): ClientAuthApi =
        retrofit.create(ClientAuthApi::class.java)

    @Provides @Singleton
    fun provideClientAuthRepository(
        api: ClientAuthApi,
        storage: ClientTokenStorage,
    ): ClientAuthRepository = ClientAuthRepository(api, storage)
}
