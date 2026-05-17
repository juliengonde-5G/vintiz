package fr.vintiz.feature.client.shell

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Storefront
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController

/**
 * Bottom-nav 3 onglets pour l'app cliente. Chaque onglet est un sous-graphe
 * indépendant. Au switch d'onglet on `popUpTo` la start destination du tab
 * et on `restoreState = true` pour préserver le scroll/state interne.
 */
@Composable
fun ClientShell(
    onLogout: () -> Unit,
) {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route

    Scaffold(
        bottomBar = {
            NavigationBar {
                ClientTab.entries.forEach { tab ->
                    NavigationBarItem(
                        selected = backStackEntry?.destination?.hierarchy
                            ?.any { it.route == tab.route } == true,
                        onClick = {
                            navController.navigate(tab.route) {
                                popUpTo(navController.graph.startDestinationId) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = { Text(tab.label) },
                    )
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = ClientShellRoutes.COMPTE,
            modifier = Modifier.padding(padding),
        ) {
            composable(ClientShellRoutes.BOUTIQUE) {
                BoutiqueHomeScreen()
            }
            composable(ClientShellRoutes.COMPTE) {
                AccountHomeScreen(onLogout = onLogout)
            }
            composable(ClientShellRoutes.SHOPPER) {
                ShopperHomeScreen()
            }
        }
    }
}

private enum class ClientTab(
    val route: String,
    val label: String,
    val icon: ImageVector,
) {
    Boutique(ClientShellRoutes.BOUTIQUE, "Boutique", Icons.Outlined.Storefront),
    Compte(ClientShellRoutes.COMPTE, "Compte", Icons.Outlined.Person),
    Shopper(ClientShellRoutes.SHOPPER, "Shopper", Icons.Outlined.AutoAwesome),
}
