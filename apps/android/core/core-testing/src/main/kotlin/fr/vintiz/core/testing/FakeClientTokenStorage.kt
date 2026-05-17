package fr.vintiz.core.testing

import fr.vintiz.core.security.ClientTokenStorage

/**
 * Fake in-memory de [ClientTokenStorage] pour les tests unitaires.
 *
 * Les champs publics (`token`, `email`, `membership`) sont renommés
 * volontairement pour éviter une collision de signature JVM avec les
 * méthodes du contrat (`getEmail()` est exposé par l'interface ; un
 * `var email` génèrerait un `getEmail()` synthétique du même JVM
 * signature → "platform declaration clash").
 */
class FakeClientTokenStorage(
    initialToken: String? = null,
    initialEmail: String? = null,
    initialMembership: String? = null,
) : ClientTokenStorage {
    var token: String? = initialToken
    var storedEmail: String? = initialEmail
    var membership: String? = initialMembership

    override fun getAccessToken(): String? = token
    override fun saveAccessToken(token: String) { this.token = token }
    override fun clearAccessToken() { token = null }

    override fun getEmail(): String? = storedEmail
    override fun saveEmail(email: String) { this.storedEmail = email }

    override fun getMembershipNumber(): String? = membership
    override fun saveMembershipNumber(number: String?) { membership = number }

    override fun clearAll() { token = null; storedEmail = null; membership = null }
}
