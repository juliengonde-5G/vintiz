package fr.vintiz.feature.client.onboarding

import androidx.compose.runtime.remember
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavGraphBuilder
import androidx.navigation.NavHostController
import androidx.navigation.compose.composable
import androidx.navigation.navigation

object OnboardingRoutes {
    const val EMAIL = "onboarding/email"
    const val OTP = "onboarding/otp"
    /** Route racine du sous-graphe — start destination = [EMAIL]. */
    const val GRAPH = "onboarding-graph"
}

/**
 * Sous-graphe de navigation onboarding magic-link.
 *
 * [OnboardingViewModel] est scopé à la `NavBackStackEntry` du parent
 * (`getBackStackEntry(OnboardingRoutes.GRAPH)`), donc l'email saisi en
 * étape 1 est conservé pour l'étape 2 sans repassage en argument.
 */
fun NavGraphBuilder.onboardingNavGraph(
    navController: NavHostController,
    onAuthenticated: () -> Unit,
) {
    navigation(
        route = OnboardingRoutes.GRAPH,
        startDestination = OnboardingRoutes.EMAIL,
    ) {
        composable(OnboardingRoutes.EMAIL) {
            val parentEntry = remember(it) {
                navController.getBackStackEntry(OnboardingRoutes.GRAPH)
            }
            val vm: OnboardingViewModel = hiltViewModel(parentEntry)
            EmailRequestScreen(
                onCodeSent = { navController.navigate(OnboardingRoutes.OTP) },
                viewModel = vm,
            )
        }
        composable(OnboardingRoutes.OTP) {
            val parentEntry = remember(it) {
                navController.getBackStackEntry(OnboardingRoutes.GRAPH)
            }
            val vm: OnboardingViewModel = hiltViewModel(parentEntry)
            OtpVerifyScreen(
                onAuthenticated = onAuthenticated,
                onBack = { navController.popBackStack() },
                viewModel = vm,
            )
        }
    }
}
