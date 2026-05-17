package fr.vintiz.data.loyalty

import fr.vintiz.core.common.VintizError
import fr.vintiz.core.common.VintizResult
import retrofit2.HttpException
import java.io.IOException

class LoyaltyRepository(private val api: LoyaltyApi) {

    suspend fun subscribe(request: LoyaltySubscribeRequest): VintizResult<LoyaltyCardDto> = try {
        VintizResult.Success(api.subscribe(request))
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        when (http.code()) {
            409 -> VintizResult.Failure(VintizError.Validation("email", "Adresse déjà inscrite"))
            422 -> VintizResult.Failure(VintizError.Validation("body", "Données invalides"))
            else -> VintizResult.Failure(VintizError.http(http.code(), http.message()))
        }
    } catch (t: Throwable) {
        VintizResult.Failure(VintizError.Unknown(t.message ?: t::class.simpleName ?: "Erreur inconnue"))
    }

    suspend fun getConfig(): VintizResult<LoyaltyConfigDto> = call { api.getConfig() }

    suspend fun setConfig(config: LoyaltyConfigDto): VintizResult<LoyaltyConfigDto> = call {
        api.setConfig(config)
    }

    suspend fun validateCoupon(
        code: String,
        cartTotalCents: Long,
        clientId: String? = null,
    ): VintizResult<CouponPreviewDto> = try {
        val preview = api.validateCoupon(ValidateCouponRequest(code, cartTotalCents, clientId))
        if (!preview.valid) {
            VintizResult.Failure(VintizError.Validation("coupon", preview.reason ?: "Coupon invalide"))
        } else {
            VintizResult.Success(preview)
        }
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        when (http.code()) {
            404 -> VintizResult.Failure(VintizError.Validation("coupon", "Code introuvable"))
            else -> VintizResult.Failure(VintizError.http(http.code(), http.message()))
        }
    } catch (t: Throwable) {
        VintizResult.Failure(VintizError.Unknown(t.message ?: t::class.simpleName ?: "Erreur inconnue"))
    }

    private suspend inline fun <T> call(block: suspend () -> T): VintizResult<T> = try {
        VintizResult.Success(block())
    } catch (io: IOException) {
        VintizResult.Failure(VintizError.Network)
    } catch (http: HttpException) {
        VintizResult.Failure(VintizError.http(http.code(), http.message()))
    } catch (t: Throwable) {
        VintizResult.Failure(VintizError.Unknown(t.message ?: t::class.simpleName ?: "Erreur inconnue"))
    }
}
