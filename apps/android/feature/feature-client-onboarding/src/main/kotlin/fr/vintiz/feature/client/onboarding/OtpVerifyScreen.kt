package fr.vintiz.feature.client.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

/**
 * Écran 2/2 du onboarding : saisie de l'OTP 6 chiffres.
 *
 * Sur succès, le repo persiste JWT + email + n° de carte fidélité dans
 * [ClientTokenStorage] et appelle [onAuthenticated] pour passer au shell.
 */
@Composable
fun OtpVerifyScreen(
    onAuthenticated: () -> Unit,
    onBack: () -> Unit,
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
                text = "Votre code",
                style = MaterialTheme.typography.headlineMedium,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = "Un code à 6 chiffres a été envoyé à ${state.email}. Il est valable 10 minutes.",
                style = MaterialTheme.typography.bodyMedium,
            )
            Spacer(Modifier.height(24.dp))
            OutlinedTextField(
                value = state.code,
                onValueChange = viewModel::onCodeChanged,
                label = { Text("Code (6 chiffres)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.NumberPassword,
                    imeAction = ImeAction.Done,
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
                onClick = { viewModel.verifyOtp(onSuccess = onAuthenticated) },
                enabled = !state.loading && state.code.length == 6,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (state.loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.height(20.dp),
                        strokeWidth = 2.dp,
                    )
                } else {
                    Text("Me connecter")
                }
            }
            Spacer(Modifier.height(8.dp))
            TextButton(
                onClick = onBack,
                enabled = !state.loading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Changer d'adresse e-mail")
            }
        }
    }
}
