package fr.vintiz.data.notifications

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import retrofit2.HttpException
import timber.log.Timber
import java.io.IOException

class NotificationsRepository(
    private val api: NotificationsApi,
    private val deviceId: String,
    private val appVersion: String,
) {

    suspend fun register(token: String, topics: List<String> = DEFAULT_TOPICS): VintizResult<Unit> = try {
        api.registerFcmToken(FcmTokenRequest(token, deviceId, appVersion, topics))
        VintizResult.Success(Unit)
    } catch (io: IOException) {
        Timber.w(io, "FCM register offline — sera retenté au prochain boot")
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    }

    suspend fun sendTest(): VintizResult<Unit> = try {
        api.test()
        VintizResult.Success(Unit)
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    }

    private companion object {
        val DEFAULT_TOPICS = listOf("drawer_closed", "large_sale", "low_stock")
    }
}
