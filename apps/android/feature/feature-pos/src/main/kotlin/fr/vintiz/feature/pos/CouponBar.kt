package fr.vintiz.feature.pos

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import fr.vintiz.core.common.Money
import fr.vintiz.data.loyalty.CouponPreviewDto

@Composable
fun CouponBar(
    code: String,
    preview: CouponPreviewDto?,
    onCodeChange: (String) -> Unit,
    onValidate: () -> Unit,
    onClear: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(modifier = modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = code,
                    onValueChange = onCodeChange,
                    label = { Text("Code promo") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                Button(onClick = onValidate, enabled = code.isNotBlank() && preview == null) {
                    Text("Vérifier")
                }
            }
            preview?.let { p ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            "${p.code} — remise ${Money(p.discount_cents).format()}" +
                                if (p.discount_percent > 0) " (${p.discount_percent} %)" else "",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        Text(
                            "Nouveau total : ${Money(p.new_total_cents).format()}",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                    TextButton(onClick = onClear) { Text("Retirer") }
                }
            }
        }
    }
}
