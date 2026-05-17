package fr.vintiz.feature.zones

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import fr.vintiz.domain.zones.Zone

@Composable
fun ZonesScreen(viewModel: ZonesViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.load() }

    Scaffold { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            Text(
                "Plan boutique",
                style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.padding(16.dp),
            )

            when {
                state.loading -> Box(modifier = Modifier.fillMaxWidth().padding(32.dp),
                    contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
                state.error != null -> Column(modifier = Modifier.padding(16.dp)) {
                    Text(state.error!!, color = MaterialTheme.colorScheme.error)
                    Spacer(Modifier.height(8.dp))
                    Button(onClick = viewModel::load) { Text("Réessayer") }
                }
                state.zones.isEmpty() -> Text(
                    "Aucune zone définie côté serveur.",
                    modifier = Modifier.padding(16.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                else -> ZonesContent(state, onSelect = viewModel::selectZone)
            }
        }
    }
}

@Composable
internal fun ZonesContent(state: ZonesUiState, onSelect: (String?) -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(420.dp)
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(8.dp),
    ) {
        IsoZonesCanvas(
            zones = state.zones,
            onTapZone = { onSelect(it.id) },
            selectedId = state.selectedId,
        )
    }
    state.selected?.let { z -> ZoneDetailPanel(z) }
    Spacer(Modifier.height(8.dp))
    ZonesList(state.zones, state.selectedId, onSelect = { onSelect(it.id) })
}

@Composable
internal fun ZonesCanvas(
    zones: List<Zone>,
    onTapZone: (Zone) -> Unit,
    selectedId: String?,
) {
    val outline = MaterialTheme.colorScheme.outline
    val primary = MaterialTheme.colorScheme.primary
    val bbox = remember(zones) { computeBoundingBox(zones) }

    Canvas(
        modifier = Modifier
            .fillMaxSize()
            .pointerInput(zones, bbox) {
                detectTapGestures { tap ->
                    val sx = size.width.toFloat() / bbox.width
                    val sy = size.height.toFloat() / bbox.height
                    val zone = zones.firstOrNull { z ->
                        val x = (z.posX - bbox.minX) * sx
                        val y = (z.posY - bbox.minY) * sy
                        val w = z.width * sx
                        val h = z.height * sy
                        tap.x in x..(x + w) && tap.y in y..(y + h)
                    }
                    if (zone != null) onTapZone(zone)
                }
            },
    ) {
        val sx = size.width / bbox.width
        val sy = size.height / bbox.height
        for (z in zones) {
            val topLeft = Offset((z.posX - bbox.minX) * sx, (z.posY - bbox.minY) * sy)
            val zoneSize = Size(z.width * sx, z.height * sy)
            val baseColor = z.composeColor()
            drawRect(color = baseColor, topLeft = topLeft, size = zoneSize)
            // Occupation : surface remplie depuis le bas selon ratio.
            val fillH = zoneSize.height * z.occupancyRatio
            drawRect(
                color = baseColor.darken(0.15f),
                topLeft = Offset(topLeft.x, topLeft.y + (zoneSize.height - fillH)),
                size = Size(zoneSize.width, fillH),
            )
            // Bord rouge si zone saturée.
            val borderColor = when {
                z.id == selectedId -> primary
                z.isSaturated -> Color(0xFFE84E8B)
                else -> outline
            }
            val borderWidth = if (z.id == selectedId) 4f else 2f
            drawRect(color = borderColor, topLeft = topLeft, size = zoneSize,
                style = Stroke(width = borderWidth))
        }
    }
}

@Composable
private fun ZoneDetailPanel(z: Zone) {
    Card(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(z.name, modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.titleLarge)
                if (z.isSaturated) AssistChip(onClick = {}, label = { Text("Saturée") })
                else if (z.isUnderused) AssistChip(onClick = {}, label = { Text("Sous-rempli") })
            }
            z.description?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodyMedium)
            }
            Row {
                Text("Produits : ${z.nProducts}/${z.capacity ?: "—"}",
                    modifier = Modifier.weight(1f))
                z.occupancyPct?.let {
                    Text("Occupation : ${"%.0f".format(it)} %",
                        style = MaterialTheme.typography.titleMedium)
                }
            }
            z.avgScore?.let {
                Text("Score moyen : ${"%.1f".format(it)} • ${z.scoreBucket.label}",
                    style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun ZonesList(zones: List<Zone>, selectedId: String?, onSelect: (Zone) -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        items(zones, key = { it.id }) { z ->
            Card(
                onClick = { onSelect(z) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(modifier = Modifier.fillMaxWidth().padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(z.name, style = MaterialTheme.typography.titleMedium)
                        Text("${z.nProducts} produits • ${z.scoreBucket.label}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    z.occupancyPct?.let {
                        Text("${"%.0f".format(it)} %",
                            style = if (z.id == selectedId) MaterialTheme.typography.titleLarge
                            else MaterialTheme.typography.titleMedium,
                            color = if (z.isSaturated) MaterialTheme.colorScheme.error
                            else MaterialTheme.colorScheme.primary)
                    }
                }
            }
        }
    }
}

internal data class BoundingBox(val minX: Int, val minY: Int, val width: Float, val height: Float)

internal fun computeBoundingBox(zones: List<Zone>): BoundingBox {
    if (zones.isEmpty()) return BoundingBox(0, 0, 1f, 1f)
    val minX = zones.minOf { it.posX }
    val minY = zones.minOf { it.posY }
    val maxX = zones.maxOf { it.posX + it.width }
    val maxY = zones.maxOf { it.posY + it.height }
    val w = (maxX - minX).coerceAtLeast(1).toFloat()
    val h = (maxY - minY).coerceAtLeast(1).toFloat()
    return BoundingBox(minX, minY, w, h)
}

private fun Color.darken(amount: Float): Color = Color(
    red = (red * (1 - amount)).coerceIn(0f, 1f),
    green = (green * (1 - amount)).coerceIn(0f, 1f),
    blue = (blue * (1 - amount)).coerceIn(0f, 1f),
    alpha = alpha,
)

/**
 * Plan boutique isométrique 2.5D — projette chaque zone rectangulaire
 * en parallélépipède iso (vue ¾) avec épaisseur ZONE_DEPTH, occupation
 * en remplissage de la face supérieure, tap → sélection.
 *
 * Projection (vue cabinet 30°) :
 *   screenX = (x - y) * cos(30°) ≈ 0.866
 *   screenY = (x + y) * sin(30°) ≈ 0.5
 *
 * Hit-test : on teste si le tap appartient au polygone supérieur
 * (face haute du parallélépipède).
 */
@Composable
internal fun IsoZonesCanvas(
    zones: List<Zone>,
    onTapZone: (Zone) -> Unit,
    selectedId: String?,
) {
    val outline = MaterialTheme.colorScheme.outline
    val primary = MaterialTheme.colorScheme.primary
    val bbox = remember(zones) { computeBoundingBox(zones) }

    Canvas(
        modifier = Modifier
            .fillMaxSize()
            .pointerInput(zones, bbox) {
                detectTapGestures { tap ->
                    val proj = isoProjector(size.width.toFloat(), size.height.toFloat(), bbox)
                    val zone = zones.firstOrNull { z ->
                        pointInQuad(tap, proj.topFace(z))
                    }
                    if (zone != null) onTapZone(zone)
                }
            },
    ) {
        val proj = isoProjector(size.width, size.height, bbox)
        // Tri Z : on dessine d'abord les zones du fond (plus grand x+y).
        val sorted = zones.sortedBy { -(it.posX + it.posY + it.width + it.height) }
        for (z in sorted) {
            val quad = proj.topFace(z)
            val base = z.composeColor()
            val side = base.darken(0.25f)

            // Face latérale droite (x = posX + width)
            val rightSide = listOf(
                quad[1], quad[2],
                Offset(quad[2].x, quad[2].y + ZONE_DEPTH),
                Offset(quad[1].x, quad[1].y + ZONE_DEPTH),
            )
            drawQuad(rightSide, side)

            // Face latérale gauche (y = posY + height)
            val frontSide = listOf(
                quad[3], quad[2],
                Offset(quad[2].x, quad[2].y + ZONE_DEPTH),
                Offset(quad[3].x, quad[3].y + ZONE_DEPTH),
            )
            drawQuad(frontSide, base.darken(0.4f))

            // Face supérieure (la zone elle-même)
            drawQuad(quad, base)

            // Occupation : sub-quad au-dessus du sol scalé par occupancyRatio
            val ratio = z.occupancyRatio
            if (ratio > 0f) {
                val occQuad = quad.map { it } // copy
                drawQuad(occQuad, base.darken(0.15f), alpha = ratio.coerceIn(0f, 1f))
            }

            // Bordure (sélection ou saturé)
            val borderColor = when {
                z.id == selectedId -> primary
                z.isSaturated -> Color(0xFFE84E8B)
                else -> outline
            }
            val borderWidth = if (z.id == selectedId) 4f else 2f
            strokeQuad(quad, borderColor, borderWidth)
        }
    }
}

private const val ZONE_DEPTH = 14f

private data class IsoProjector(
    val sx: Float,
    val sy: Float,
    val originX: Float,
    val originY: Float,
    val bbox: BoundingBox,
) {
    fun project(x: Float, y: Float): Offset {
        val nx = (x - bbox.minX)
        val ny = (y - bbox.minY)
        return Offset(
            originX + (nx - ny) * sx,
            originY + (nx + ny) * sy,
        )
    }

    fun topFace(z: Zone): List<Offset> {
        val x0 = z.posX.toFloat()
        val y0 = z.posY.toFloat()
        val x1 = x0 + z.width
        val y1 = y0 + z.height
        return listOf(
            project(x0, y0), // top-back
            project(x1, y0), // right-back
            project(x1, y1), // right-front
            project(x0, y1), // left-front
        )
    }
}

private fun isoProjector(
    canvasW: Float,
    canvasH: Float,
    bbox: BoundingBox,
): IsoProjector {
    // Largeur projetée = (bbox.width + bbox.height) * sx
    // Hauteur projetée = (bbox.width + bbox.height) * sy
    val cos30 = 0.866f
    val sin30 = 0.5f
    val totalW = bbox.width + bbox.height
    val totalH = bbox.width + bbox.height
    val sxRaw = canvasW / (totalW * cos30)
    val syRaw = (canvasH - ZONE_DEPTH) / (totalH * sin30)
    val s = minOf(sxRaw, syRaw) * 0.95f
    val sx = s * cos30
    val sy = s * sin30
    // Origine = haut, centré
    val projW = (totalW) * sx
    val originX = (canvasW - projW) / 2f + bbox.height * sx
    val originY = 8f
    return IsoProjector(sx, sy, originX, originY, bbox)
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawQuad(
    quad: List<Offset>,
    color: Color,
    alpha: Float = 1f,
) {
    val path = androidx.compose.ui.graphics.Path().apply {
        moveTo(quad[0].x, quad[0].y)
        for (i in 1 until quad.size) lineTo(quad[i].x, quad[i].y)
        close()
    }
    drawPath(path = path, color = color, alpha = alpha)
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.strokeQuad(
    quad: List<Offset>,
    color: Color,
    width: Float,
) {
    val path = androidx.compose.ui.graphics.Path().apply {
        moveTo(quad[0].x, quad[0].y)
        for (i in 1 until quad.size) lineTo(quad[i].x, quad[i].y)
        close()
    }
    drawPath(path = path, color = color, style = Stroke(width = width))
}

/** Point-in-polygon ray-casting (suffisant pour quad iso). */
private fun pointInQuad(point: Offset, quad: List<Offset>): Boolean {
    var inside = false
    var j = quad.lastIndex
    for (i in quad.indices) {
        val xi = quad[i].x; val yi = quad[i].y
        val xj = quad[j].x; val yj = quad[j].y
        if (((yi > point.y) != (yj > point.y)) &&
            (point.x < (xj - xi) * (point.y - yi) / (yj - yi + 1e-6f) + xi)) {
            inside = !inside
        }
        j = i
    }
    return inside
}

