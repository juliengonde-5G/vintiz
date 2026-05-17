package fr.vintiz.core.testing

import fr.vintiz.core.security.ClientTokenStorage

class FakeClientTokenStorage(
    initialToken: String? = null,
    initialEmail: String? = null,
    initialMembership: String? = null,
) : ClientTokenStorage {
    var token: String? = initialToken
    var email: String? = initialEmail
    var membership: String? = initialMembership

    override fun getAccessToken(): String? = token
    override fun saveAccessToken(token: String) { this.token = token }
    override fun clearAccessToken() { token = null }

    override fun getEmail(): String? = email
    override fun saveEmail(email: String) { this.email = email }

    override fun getMembershipNumber(): String? = membership
    override fun saveMembershipNumber(number: String?) { membership = number }

    override fun clearAll() { token = null; email = null; membership = null }
}
