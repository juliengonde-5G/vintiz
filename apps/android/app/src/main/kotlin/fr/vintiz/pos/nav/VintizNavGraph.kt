package fr.vintiz.pos.nav

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import fr.vintiz.feature.admin.AdminScreen
import fr.vintiz.feature.auth.CashierPinScreen
import fr.vintiz.feature.auth.LoginScreen
import fr.vintiz.feature.cahier.CahierScreen
import fr.vintiz.feature.clients.ClientDetailScreen
import fr.vintiz.feature.clients.ClientsScreen
import fr.vintiz.feature.dashboard.DashboardScreen
import fr.vintiz.feature.drawer.DrawerScreen
import fr.vintiz.feature.fiscal.FiscalExportScreen
import fr.vintiz.feature.inventory.InventoryImportScreen
import fr.vintiz.feature.inventory.ProductDetailScreen
import fr.vintiz.feature.ia.IaScreen
import fr.vintiz.feature.loyalty.LoyaltySubscribeScreen
import fr.vintiz.feature.newsletter.NewsletterScreen
import fr.vintiz.feature.personalshopper.PersonalShopperScreen
import fr.vintiz.feature.inventory.InventoryScreen
import fr.vintiz.feature.pos.PosScreen
import fr.vintiz.feature.settings.SettingsScreen
import fr.vintiz.feature.onboarding.OnboardingScreen
import fr.vintiz.feature.zones.ZonesScreen

object Routes {
    const val ONBOARDING = "onboarding"
    const val LOGIN = "login"
    const val CASHIER_PIN = "cashier_pin"
    const val SHELL = "shell"

    const val POS = "shell/pos"
    const val INVENTORY = "shell/inventory"
    const val CLIENTS = "shell/clients"
    const val CAHIER = "shell/cahier"
    const val SETTINGS = "shell/settings"

    const val DASHBOARD = "shell/dashboard"
    const val IA = "shell/ia"
    const val ZONES = "shell/zones"
    const val ADMIN = "shell/admin"
    const val FISCAL = "shell/fiscal"
    const val NEWSLETTER = "shell/newsletter"
    const val LOYALTY_SUBSCRIBE = "shell/loyalty/subscribe"
    const val PERSONAL_SHOPPER = "shell/personal-shopper"
    const val DRAWER = "shell/drawer"
    const val INVENTORY_DETAIL = "shell/inventory/detail"
    const val INVENTORY_IMPORT = "shell/inventory/import"
    const val CLIENT_DETAIL = "shell/clients/detail"

    fun inventoryDetail(productId: String) = "$INVENTORY_DETAIL/$productId"
    fun clientDetail(clientId: String) = "$CLIENT_DETAIL/$clientId"

    fun fiscalRoute(from: String? = null, to: String? = null): String {
        val params = buildList {
            if (!from.isNullOrBlank()) add("from=$from")
            if (!to.isNullOrBlank()) add("to=$to")
        }
        return if (params.isEmpty()) FISCAL else FISCAL + "?" + params.joinToString("&")
    }
}

@Composable
fun VintizNavGraph(startDestination: String = Routes.LOGIN) {
    val nav = rememberNavController()
    NavHost(navController = nav, startDestination = startDestination) {
        composable(Routes.ONBOARDING) {
            OnboardingScreen(onFinished = {
                nav.navigate(Routes.LOGIN) {
                    popUpTo(Routes.ONBOARDING) { inclusive = true }
                }
            })
        }
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
        composable(Routes.SHELL) { Shell(rootNav = nav) }
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
                        selected = currentRoute == item.route ||
                            (item == BottomNavItem.Plus && currentRoute in PLUS_ROUTES),
                        onClick = {
                            shellNav.navigate(item.route) {
                                popUpTo(shellNav.graph.findStartDestination().id) { saveState = true }
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
                composable(Routes.INVENTORY) {
                    InventoryScreen(onProductClick = { id ->
                        shellNav.navigate(Routes.inventoryDetail(id))
                    })
                }
                composable(
                    route = "${Routes.INVENTORY_DETAIL}/{productId}",
                    arguments = listOf(
                        androidx.navigation.navArgument("productId") {
                            type = androidx.navigation.NavType.StringType
                        },
                    ),
                ) { backStackEntry ->
                    ProductDetailScreen(
                        productId = backStackEntry.arguments?.getString("productId").orEmpty(),
                        onBack = { shellNav.popBackStack() },
                    )
                }
                composable(Routes.INVENTORY_IMPORT) {
                    InventoryImportScreen(onBack = { shellNav.popBackStack() })
                }
                composable(Routes.DRAWER) { DrawerScreen() }
                composable(Routes.CLIENTS) {
                    ClientsScreen(onClientClick = { id ->
                        shellNav.navigate(Routes.clientDetail(id))
                    })
                }
                composable(
                    route = "${Routes.CLIENT_DETAIL}/{clientId}",
                    arguments = listOf(
                        androidx.navigation.navArgument("clientId") {
                            type = androidx.navigation.NavType.StringType
                        },
                    ),
                ) { backStackEntry ->
                    ClientDetailScreen(
                        clientId = backStackEntry.arguments?.getString("clientId").orEmpty(),
                        onBack = { shellNav.popBackStack() },
                    )
                }
                composable(Routes.CAHIER) { CahierScreen() }
                composable(Routes.SETTINGS) { SettingsScreen() }
                composable(Routes.DASHBOARD) { DashboardScreen() }
                composable(Routes.IA) { IaScreen() }
                composable(Routes.ZONES) { ZonesScreen() }
                composable(Routes.ADMIN) {
                    AdminScreen(onExportPeriod = { from, to ->
                        shellNav.navigate(Routes.fiscalRoute(from, to))
                    })
                }
                composable(
                    route = "${Routes.FISCAL}?from={from}&to={to}",
                    arguments = listOf(
                        androidx.navigation.navArgument("from") {
                            type = androidx.navigation.NavType.StringType
                            nullable = true
                            defaultValue = null
                        },
                        androidx.navigation.navArgument("to") {
                            type = androidx.navigation.NavType.StringType
                            nullable = true
                            defaultValue = null
                        },
                    ),
                ) { backStackEntry ->
                    FiscalExportScreen(
                        initialFrom = backStackEntry.arguments?.getString("from"),
                        initialTo = backStackEntry.arguments?.getString("to"),
                    )
                }
                composable(Routes.NEWSLETTER) { NewsletterScreen() }
                composable(Routes.LOYALTY_SUBSCRIBE) {
                    LoyaltySubscribeScreen(onSubscribed = {
                        shellNav.navigate(Routes.POS) {
                            popUpTo(Routes.LOYALTY_SUBSCRIBE) { inclusive = true }
                        }
                    })
                }
                composable(Routes.PERSONAL_SHOPPER) { PersonalShopperScreen() }
                composable(BottomNavItem.Plus.route) {
                    PlusMenu(onSelect = { route ->
                        shellNav.navigate(route) {
                            popUpTo(shellNav.graph.findStartDestination().id) { saveState = true }
                            launchSingleTop = true
                        }
                    })
                }
            }
        }
    }
}

private val PLUS_ROUTES = setOf(
    Routes.DASHBOARD, Routes.IA, Routes.ZONES, Routes.ADMIN, Routes.FISCAL,
    Routes.NEWSLETTER, Routes.LOYALTY_SUBSCRIBE, Routes.PERSONAL_SHOPPER,
    Routes.DRAWER, Routes.INVENTORY_IMPORT, "shell/plus",
)

@Composable
private fun PlusMenu(onSelect: (String) -> Unit) {
    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text("Plus", style = MaterialTheme.typography.headlineLarge)
            PlusItem("Tableau de bord", "Vue manager : CA, météo, top produits", Routes.DASHBOARD, onSelect)
            PlusItem("Compagnon IA", "Checklist hebdo, tendances", Routes.IA, onSelect)
            PlusItem("Plan boutique", "Zones et occupation", Routes.ZONES, onSelect)
            PlusItem("Admin", "Transactions, refund, Z-reports, users, audit", Routes.ADMIN, onSelect)
            PlusItem("Export fiscal NF525", "Génération XML/JSON DGFiP signée serveur", Routes.FISCAL, onSelect)
            PlusItem("Newsletter", "Abonnés RGPD, export CSV, droit à l'oubli", Routes.NEWSLETTER, onSelect)
            PlusItem("Adhésion fidélité", "Créer une carte V###### au POS", Routes.LOYALTY_SUBSCRIBE, onSelect)
            PlusItem("Personal Shopper", "Recos IA pour une cliente identifiée", Routes.PERSONAL_SHOPPER, onSelect)
            PlusItem("Caisse — ouverture/fermeture", "Fond, Z-Report, écart", Routes.DRAWER, onSelect)
            PlusItem("Import CSV produits", "Bulk upload depuis tableur, dry-run + commit", Routes.INVENTORY_IMPORT, onSelect)
        }
    }
}

@Composable
private fun PlusItem(title: String, subtitle: String, route: String, onSelect: (String) -> Unit) {
    androidx.compose.material3.Card(
        onClick = { onSelect(route) },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleLarge)
            Text(subtitle, style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private enum class BottomNavItem(val route: String, val label: String, val icon: String) {
    Pos(Routes.POS, "Caisse", "₽"),
    Inventory(Routes.INVENTORY, "Stock", "≡"),
    Clients(Routes.CLIENTS, "Clientes", "♥"),
    Cahier(Routes.CAHIER, "Cahier", "✎"),
    Plus("shell/plus", "Plus", "⋮"),
    Settings(Routes.SETTINGS, "Réglages", "⚙"),
}
