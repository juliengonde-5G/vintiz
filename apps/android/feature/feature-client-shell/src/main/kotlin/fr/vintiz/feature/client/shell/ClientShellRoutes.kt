package fr.vintiz.feature.client.shell

/**
 * Routes des 3 onglets stricts de l'app cliente, conformément à
 * `docs/PLAN_ANDROID_CLIENT_APP.md` §Périmètre fonctionnel.
 *
 * - [BOUTIQUE] : vitrine + catalogue + adresse + agenda (Sprint B)
 * - [COMPTE]   : 7 zones /account/* (fidélité, historique, RGPD…) (Sprint A stub, C complet)
 * - [SHOPPER]  : Personal Shopper IA + try-on (Sprint C/D)
 */
object ClientShellRoutes {
    const val BOUTIQUE = "client/boutique"
    const val COMPTE = "client/compte"
    const val SHOPPER = "client/shopper"

    /** Route racine du shell — start destination = [COMPTE] (utilisateur déjà loggé). */
    const val GRAPH = "client-shell"
}
