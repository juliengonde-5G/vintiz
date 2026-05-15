package fr.vintiz.pos.di

import android.content.Context
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import fr.vintiz.core.datastore.AppPreferences
import fr.vintiz.core.network.HttpClientFactory
import fr.vintiz.core.security.AndroidTokenStorage
import fr.vintiz.core.security.TokenStorage
import fr.vintiz.pos.BuildConfig
import javax.inject.Singleton
import kotlinx.coroutines.runBlocking

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideTokenStorage(@ApplicationContext context: Context): TokenStorage =
        AndroidTokenStorage(context)

    @Provides
    @Singleton
    fun provideAppPreferences(@ApplicationContext context: Context): AppPreferences =
        AppPreferences(context)

    /**
     * Le refresh-token est posé en TODO : l'implémentation réelle vivra
     * dans `data:data-auth` (sprint suivant), avec un `AuthRepository`
     * qui appelle `/api/v1/auth/refresh`. Tant que la couche auth n'est
     * pas câblée, on retourne `null` → le 401 se propage et la couche
     * UI redirige vers le login.
     */
    @Provides
    @Singleton
    fun provideHttpClientFactory(
        tokenStorage: TokenStorage,
    ): HttpClientFactory = HttpClientFactory(
        tokenStorage = tokenStorage,
        baseUrl = BuildConfig.API_BASE_URL,
        clientId = "${BuildConfig.CLIENT_ID}/${BuildConfig.VERSION_NAME}",
        debug = BuildConfig.DEBUG,
        refreshToken = { _ -> null },
        runBlocking = { block -> runBlocking { block() } },
    )
}
