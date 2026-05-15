package fr.vintiz.pos.nav

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import fr.vintiz.feature.auth.CashierPinScreen
import fr.vintiz.feature.auth.LoginScreen
import fr.vintiz.feature.clients.ClientsScreen
import fr.vintiz.feature.inventory.InventoryScreen
import fr.vintiz.feature.pos.PosScreen
import fr.vintiz.feature.settings.SettingsScreen

object Routes {
    const val LOGIN = "login"
    const val CASHIER_PIN = "cashier_pin"
    const val SHELL = "shell"

    const val POS = "shell/pos"
    const val INVENTORY = "shell/inventory"
    const val CLIENTS = "shell/clients"
    const val SETTINGS = "shell/settings"
}

@Composable
fun VintizNavGraph() {
    val nav = rememberNavController()
    NavHost(navController = nav, startDestination = Routes.LOGIN) {
        composable(Routes.LOGIN) {
            LoginScreen(onLoginSuccess = {
                nav.navigate(Routes.CASHIER_PIN) {
                    popUpTo(Routes.LOGIN) { inclusive = true }
                }
            })
        }
        composable(Routes.CASHIER_PIN) {
            CashierPinScreen(onPinSuccess = {
                nav.navigate(Routes.SHELL) {
                    popUpTo(Routes.CASHIER_PIN) { inclusive = true }
                }
            })
        }
        composable(Routes.SHELL) {
            Shell(rootNav = nav)
        }
    }
}

@Composable
private fun Shell(rootNav: NavHostController) {
    val shellNav = rememberNavController()
    val current by shellNav.currentBackStackEntryAsState()
    val currentRoute = current?.destination?.route ?: Routes.POS

    Scaffold(
        bottomBar = {
            NavigationBar {
                BottomNavItem.entries.forEach { item ->
                    NavigationBarItem(
                        selected = currentRoute == item.route,
                        onClick = {
                            shellNav.navigate(item.route) {
                                popUpTo(shellNav.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Text(item.icon) },
                        label = { Text(item.label) },
                    )
                }
            }
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding),
            verticalArrangement = Arrangement.Top,
        ) {
            NavHost(navController = shellNav, startDestination = Routes.POS) {
                composable(Routes.POS) {
                    PosScreen(onLogout = {
                        rootNav.navigate(Routes.LOGIN) {
                            popUpTo(Routes.SHELL) { inclusive = true }
                        }
                    })
                }
                composable(Routes.INVENTORY) { InventoryScreen() }
                composable(Routes.CLIENTS) { ClientsScreen() }
                composable(Routes.SETTINGS) { SettingsScreen() }
            }
        }
    }
}

private enum class BottomNavItem(val route: String, val label: String, val icon: String) {
    Pos(Routes.POS, "Caisse", "₽"),
    Inventory(Routes.INVENTORY, "Stock", "≡"),
    Clients(Routes.CLIENTS, "Clientes", "♥"),
    Settings(Routes.SETTINGS, "Réglages", "⚙"),
}
