package fr.vintiz.data.auth.dto

import com.squareup.moshi.JsonClass

// Note : pas de LoginRequest data class — /auth/login attend du
// x-www-form-urlencoded (OAuth2PasswordRequestForm FastAPI), pas du
// JSON. AuthApi.login() utilise @FormUrlEncoded + @Field(...).

@JsonClass(generateAdapter = true)
data class TokenResponse(
    val access_token: String,
    val token_type: String = "bearer",
    // user_id et role sont OPTIONNELS côté schéma backend
    // (apps/api/app/schemas/user.py:25-29 Token), donc en `String?`
    // côté Kotlin pour éviter qu'un body sans ces champs casse
    // Moshi avec "required value user_id missing at $".
    val user_id: String? = null,
    val role: String? = null,
)

@JsonClass(generateAdapter = true)
data class CashierLoginRequest(val pin: String)

@JsonClass(generateAdapter = true)
data class CashierResponse(
    val id: String,
    val username: String,
    val role: String,
)
