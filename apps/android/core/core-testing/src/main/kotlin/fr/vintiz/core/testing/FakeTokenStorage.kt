package fr.vintiz.core.testing

import fr.vintiz.core.security.TokenStorage

class FakeTokenStorage(
    initialToken: String? = null,
    initialCashier: String? = null,
) : TokenStorage {
    var token: String? = initialToken
    var cashier: String? = initialCashier

    override fun getAccessToken(): String? = token
    override fun saveAccessToken(token: String) { this.token = token }
    override fun clearAccessToken() { token = null }
    override fun getCashierId(): String? = cashier
    override fun saveCashierId(cashierId: String) { cashier = cashierId }
    override fun clearCashierId() { cashier = null }
    override fun clearAll() { token = null; cashier = null }
}
