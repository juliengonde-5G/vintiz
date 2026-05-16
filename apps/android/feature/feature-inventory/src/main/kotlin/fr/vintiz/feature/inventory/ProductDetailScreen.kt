package fr.vintiz.feature.inventory

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage
import fr.vintiz.core.common.Money
import fr.vintiz.data.inventory.ProductDto
import fr.vintiz.data.inventory.ProductPhotoDto

@Composable
fun ProductDetailScreen(
    productId: String,
    onBack: () -> Unit,
    viewModel: ProductDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current
    LaunchedEffect(productId) { viewModel.load(productId) }

    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture(),
    ) { success ->
        if (success) viewModel.confirmCaptured() else viewModel.cancelCaptured()
    }

    Scaffold { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            TextButton(onClick = onBack) { Text("← Retour") }

            when {
                state.loading -> Box(
                    modifier = Modifier.fillMaxWidth(),
                    contentAlignment = Alignment.Center,
                ) { CircularProgressIndicator() }
                state.error != null -> Text(state.error!!,
                    color = MaterialTheme.colorScheme.error)
                state.product != null -> ProductDetailBody(
                    p = state.product!!,
                    photos = state.photos,
                    uploading = state.uploading,
                    onCapture = {
                        val file = viewModel.newCaptureFile()
                        val uri = FileProvider.getUriForFile(
                            context, "${context.packageName}.fileprovider", file,
                        )
                        cameraLauncher.launch(uri)
                    },
                )
            }
        }
    }
}

@Composable
private fun ProductDetailBody(
    p: ProductDto,
    photos: List<ProductPhotoDto>,
    uploading: Boolean,
    onCapture: () -> Unit,
) {
    if (!p.photo_url.isNullOrBlank()) {
        Card(modifier = Modifier.fillMaxWidth()) {
            AsyncImage(
                model = p.photo_url,
                contentDescription = p.name,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1.6f)
                    .clip(RoundedCornerShape(12.dp)),
            )
        }
    }

    Text(p.name, style = MaterialTheme.typography.headlineMedium)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        AssistChip(onClick = {}, label = { Text(p.status) })
        p.category?.takeIf { it.isNotBlank() }?.let {
            AssistChip(onClick = {}, label = { Text(it) })
        }
    }
    Text(Money(p.price_cents).format(),
        style = MaterialTheme.typography.displaySmall,
        color = MaterialTheme.colorScheme.primary)

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Photos (${photos.size})",
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.titleMedium)
                Button(onClick = onCapture, enabled = !uploading) {
                    Text(if (uploading) "Envoi…" else "+ Photo")
                }
            }
            if (photos.isNotEmpty()) {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(photos, key = { it.id }) { photo ->
                        Box(modifier = Modifier.size(96.dp)) {
                            AsyncImage(
                                model = photo.url,
                                contentDescription = "photo ${photo.id.take(6)}",
                                contentScale = ContentScale.Crop,
                                modifier = Modifier.fillMaxSize().clip(RoundedCornerShape(8.dp)),
                            )
                            if (photo.is_primary) {
                                Text(
                                    "★",
                                    modifier = Modifier.padding(4.dp),
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Caractéristiques", style = MaterialTheme.typography.titleLarge)
            HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))
            DetailRow("Code-barres", p.barcode ?: "—")
            DetailRow("Identifiant", p.id.take(8))
            DetailRow("TVA", "${"%.1f".format(p.tva_rate)} %")
            DetailRow("Statut", p.status)
        }
    }

    Spacer(Modifier.height(8.dp))
    Text(
        "Historique mouvements : à brancher en V2 via " +
            "/api/v1/inventory/products/{id}/history.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row {
        Text(label,
            modifier = Modifier.weight(1f),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodyMedium)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}
