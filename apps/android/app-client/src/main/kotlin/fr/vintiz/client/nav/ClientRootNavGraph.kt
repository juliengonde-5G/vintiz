package fr.vintiz.client.nav

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import fr.vintiz.feature.client.onboarding.OnboardingRoutes
import fr.vintiz.feature.client.onboarding.onboardingNavGraph
import fr.vintiz.feature.client.shell.ClientShell

private object ClientRootRoutes {
    const val SHELL = "shell"
}

/**
 * Graphe racine de l'app cliente.
 *
 * - Non authentifié → start sur [OnboardingRoutes.GRAPH] (magic-link)
 * - Authentifié      → start sur [ClientRootRoutes.SHELL] (3 onglets)
 *
 * Au logout, on retourne sur le graph onboarding avec `popUpTo(SHELL)`
 * pour vider la pile (impossible de revenir au shell sans re-login).
 */
@Composable
fun ClientRootNavGraph(startAuthenticated: Boolean) {
    val navController = rememberNavController()
    val startDestination = if (startAuthenticated) {
        ClientRootRoutes.SHELL
    } else {
        OnboardingRoutes.GRAPH
    }

    NavHost(
        navController = navController,
        startDestination = startDestination,
    ) {
        onboardingNavGraph(
            navController = navController,
            onAuthenticated = {
                navController.navigate(ClientRootRoutes.SHELL) {
                    popUpTo(OnboardingRoutes.GRAPH) { inclusive = true }
                }
            },
        )
        composable(ClientRootRoutes.SHELL) {
            ClientShell(
                onLogout = {
                    navController.navigate(OnboardingRoutes.GRAPH) {
                        popUpTo(ClientRootRoutes.SHELL) { inclusive = true }
                    }
                },
            )
        }
    }
}
