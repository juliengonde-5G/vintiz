package fr.vintiz.data.authclient.dto

import com.squareup.moshi.JsonClass

/**
 * Contrat magic-link OTP — voir `apps/api/app/api/auth/router.py`
 * sections "magic-link/request" et "magic-link/verify".
 *
 * Ces DTO sont sérialisés en **JSON** (Pydantic `BaseModel`), à la
 * différence du login manager (`OAuth2PasswordRequestForm`, form-urlencoded).
 */
@JsonClass(generateAdapter = true)
data class MagicLinkRequestBody(
    val email: String,
)

@JsonClass(generateAdapter = true)
data class MagicLinkVerifyBody(
    val email: String,
    val code: String,
)

@JsonClass(generateAdapter = true)
data class MagicLinkVerifyResponse(
    val access_token: String,
    val expires_in: Int,
    val client_id: String,
    val membership_number: String? = null,
)
