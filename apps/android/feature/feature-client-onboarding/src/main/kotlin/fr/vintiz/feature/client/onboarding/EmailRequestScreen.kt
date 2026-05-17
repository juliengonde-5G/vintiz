package fr.vintiz.feature.client.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

/**
 * Écran 1/2 du onboarding magic-link : saisie de l'adresse e-mail.
 *
 * Sur succès, déclenche `POST /api/auth/magic-link/request` puis
 * appelle [onCodeSent] pour passer à [OtpVerifyScreen].
 */
@Composable
fun EmailRequestScreen(
    onCodeSent: () -> Unit,
    viewModel: OnboardingViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()

    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                text = "Bienvenue chez Vintiz",
                style = MaterialTheme.typography.headlineMedium,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Saisissez votre adresse e-mail. Vous recevrez un code à 6 chiffres pour vous connecter.",
                style = MaterialTheme.typography.bodyMedium,
            )
            Spacer(Modifier.height(24.dp))
            OutlinedTextField(
                value = state.email,
                onValueChange = viewModel::onEmailChanged,
                label = { Text("Adresse e-mail") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Email,
                    imeAction = ImeAction.Send,
                ),
                modifier = Modifier.fillMaxWidth(),
                enabled = !state.loading,
                isError = state.error != null,
            )
            state.error?.let { msg ->
                Spacer(Modifier.height(8.dp))
                Text(
                    text = msg,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Spacer(Modifier.height(24.dp))
            Button(
                onClick = { viewModel.requestOtp(onSuccess = onCodeSent) },
                enabled = !state.loading && state.email.isNotBlank(),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (state.loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(20.dp),
                        strokeWidth = 2.dp,
                    )
                } else {
                    Text("Recevoir mon code")
                }
            }
        }
    }
}
