package fr.vintiz.data.auth.dto

import com.squareup.moshi.JsonClass

// Note : pas de LoginRequest data class — /auth/login attend du
// x-www-form-urlencoded (OAuth2PasswordRequestForm FastAPI), pas du
// JSON. AuthApi.login() utilise @FormUrlEncoded + @Field(...).

@JsonClass(generateAdapter = true)
data class TokenResponse(
    val access_token: String,
    val token_type: String,
    val user_id: String,
    val role: String,
)

@JsonClass(generateAdapter = true)
data class CashierLoginRequest(val pin: String)

@JsonClass(generateAdapter = true)
data class CashierResponse(
    val id: String,
    val username: String,
    val role: String,
)
