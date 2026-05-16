package fr.vintiz.domain.inventory

import fr.vintiz.core.common.Money

data class Product(
    val id: String,
    val barcode: String?,
    val name: String,
    val price: Money,
    val tvaRate: Double,
    val category: String?,
    val photoUrl: String?,
    val status: ProductStatus,
)

enum class ProductStatus(val key: String) {
    InStock("in_stock"),
    OnDisplay("on_display"),
    Sold("sold"),
    Returned("returned"),
    Marked("marked"),
    Unknown("unknown");

    companion object {
        fun fromKey(key: String?): ProductStatus =
            entries.firstOrNull { it.key == key } ?: Unknown
    }
}

/**
 * Nettoyage barcode douchette : la Inateck BCST-35 ajoute parfois
 * \r ou \n selon la config keyboard wedge, et certaines configs
 * keyboard wedge insèrent des espaces parasites. La regex \s+ couvre
 * espaces, tabs, CR, LF, NBSP ( ) et autres séparateurs Unicode.
 * Symétrique avec `apps/api/app/api/inventory/router.py` côté serveur.
 */
object BarcodeNormalizer {
    /**
     * Couvre `\s` (ASCII : espace, tab, CR, LF, FF, VT) + les
     * séparateurs Unicode courants : NBSP (` `), Narrow NBSP
     * (` `), Figure space (` `), Em space (` `),
     * Zero-width space (`​`) — keyboard wedge français peuvent
     * en générer.
     */
    private val WHITESPACE = Regex("[\\s\\u00A0\\u202F\\u2007\\u2003\\u200B]+")
    fun normalize(raw: String): String = WHITESPACE.replace(raw, "")
}
