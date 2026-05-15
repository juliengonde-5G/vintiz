package fr.vintiz.feature.zones

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp

/**
 * Plan boutique isométrique simplifié — pour la version 1 du portage,
 * on rend un plan 2D top-down (le rendu isométrique 3D viendra avec
 * `Path` + transformation affine en V2). Les zones sont cliquables et
 * affichent leur taux d'occupation.
 *
 * Référence UX : `apps/web/src/components/zones/IsoCanvas.tsx` 281 L.
 */
@Composable
fun ZonesScreen() {
    var selected by remember { mutableStateOf<Zone?>(null) }
    val zones = DemoZones.all

    Scaffold { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            Text(
                "Plan boutique",
                style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.padding(16.dp),
            )
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(360.dp)
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .padding(8.dp),
            ) {
                ZonesCanvas(
                    zones = zones,
                    onTapZone = { selected = it },
                    selectedId = selected?.id,
                )
            }
            selected?.let { z ->
                Row(modifier = Modifier.fillMaxWidth().padding(16.dp),
                    horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(12.dp)) {
                    Text(z.name, modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.titleLarge)
                    Text("Occupation : ${(z.occupancy * 100).toInt()} %",
                        style = MaterialTheme.typography.titleMedium)
                }
            }
        }
    }
}

@Composable
internal fun ZonesCanvas(
    zones: List<Zone>,
    onTapZone: (Zone) -> Unit,
    selectedId: String?,
) {
    val outline = MaterialTheme.colorScheme.outline
    val primary = MaterialTheme.colorScheme.primary
    Canvas(
        modifier = Modifier
            .fillMaxSize()
            .pointerInput(zones) {
                detectTapGestures { tap ->
                    val sx = size.width.toFloat() / WORLD_W
                    val sy = size.height.toFloat() / WORLD_H
                    val zone = zones.firstOrNull { z ->
                        val x = z.posX * sx
                        val y = z.posY * sy
                        val w = z.width * sx
                        val h = z.height * sy
                        tap.x in x..(x + w) && tap.y in y..(y + h)
                    }
                    zone?.let(onTapZone)
                }
            },
    ) {
        val sx = size.width / WORLD_W
        val sy = size.height / WORLD_H
        for (z in zones) {
            val topLeft = Offset(z.posX * sx, z.posY * sy)
            val s = Size(z.width * sx, z.height * sy)
            drawRect(color = z.color, topLeft = topLeft, size = s)
            // Fill ratio overlay (gradient pseudo : un sous-rect plus foncé)
            val fillH = s.height * z.occupancy
            drawRect(
                color = z.color.copy(alpha = 0.6f),
                topLeft = Offset(topLeft.x, topLeft.y + (s.height - fillH)),
                size = Size(s.width, fillH),
            )
            val borderColor = if (z.id == selectedId) primary else outline
            drawRect(
                color = borderColor,
                topLeft = topLeft,
                size = s,
                style = Stroke(width = if (z.id == selectedId) 4f else 2f),
            )
        }
    }
}

private const val WORLD_W = 260f
private const val WORLD_H = 200f
