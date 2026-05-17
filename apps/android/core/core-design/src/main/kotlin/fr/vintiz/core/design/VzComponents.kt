package fr.vintiz.core.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * TopAppBar Vintiz : fond crème vz-bg, titre en Fraunces semibold,
 * sous-titre en Manrope mute, bouton retour optionnel à gauche.
 *
 * Match visuel de la barre d'en-tête web (apps/web/src/components/Header.tsx).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VzTopBar(
    title: String,
    subtitle: String? = null,
    onBack: (() -> Unit)? = null,
    actions: @Composable () -> Unit = {},
) {
    TopAppBar(
        title = {
            Column {
                Text(
                    title,
                    style = MaterialTheme.typography.headlineSmall,
                    color = VzColors.Ink,
                )
                subtitle?.takeIf { it.isNotBlank() }?.let {
                    Text(
                        it,
                        style = MaterialTheme.typography.labelSmall,
                        color = VzColors.InkMute,
                    )
                }
            }
        },
        navigationIcon = {
            onBack?.let {
                IconButton(onClick = it) {
                    Text(
                        "←",
                        style = MaterialTheme.typography.headlineMedium,
                        color = VzColors.Teal,
                    )
                }
            }
        },
        actions = { actions() },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = VzColors.Bg,
            scrolledContainerColor = VzColors.BgAlt,
        ),
    )
}

/**
 * Scaffold standard Vintiz : VzTopBar + content avec scroll vertical
 * et padding standard. Utiliser dans tous les écrans principaux pour
 * uniformité visuelle. Ajout bottomBar optionnel (pour le Shell).
 */
@Composable
fun VzScreenScaffold(
    title: String,
    subtitle: String? = null,
    onBack: (() -> Unit)? = null,
    topBarActions: @Composable () -> Unit = {},
    bottomBar: @Composable () -> Unit = {},
    scrollable: Boolean = true,
    content: @Composable (PaddingValues) -> Unit,
) {
    Scaffold(
        topBar = {
            VzTopBar(title = title, subtitle = subtitle, onBack = onBack, actions = topBarActions)
        },
        bottomBar = bottomBar,
        containerColor = VzColors.Bg,
    ) { padding ->
        if (scrollable) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .verticalScroll(rememberScrollState()),
            ) {
                content(PaddingValues(0.dp))
            }
        } else {
            content(padding)
        }
    }
}

/**
 * Section sur fond Surface, radius doux, ombre légère, padding
 * généreux. Sert de "card" principale dans les écrans Vintiz.
 * Plus chic que `Card` par défaut Material 3.
 */
@Composable
fun VzCardSection(
    modifier: Modifier = Modifier,
    title: String? = null,
    actions: @Composable () -> Unit = {},
    content: @Composable () -> Unit,
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 6.dp),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = VzColors.Surface,
            contentColor = VzColors.Ink,
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (title != null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        title,
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                        color = VzColors.Ink,
                    )
                    actions()
                }
            }
            content()
        }
    }
}

/**
 * Chip de statut / tag Vintiz — accent teal soft par défaut, accent
 * rose pour les alertes/saturé, gold pour fidélité haut de gamme.
 */
@Composable
fun VzStatusChip(
    label: String,
    kind: VzChipKind = VzChipKind.Neutral,
    onClick: () -> Unit = {},
) {
    val (bg, fg) = when (kind) {
        VzChipKind.Primary -> VzColors.TealSoft to VzColors.TealDeep
        VzChipKind.Accent -> VzColors.AccentSoft to VzColors.Ink
        VzChipKind.Warning -> Color(0xFFFFE6CC) to Color(0xFF7A4A00)
        VzChipKind.Neutral -> VzColors.BgAlt to VzColors.InkSoft
    }
    AssistChip(
        onClick = onClick,
        label = { Text(label, color = fg, style = MaterialTheme.typography.labelMedium) },
        colors = AssistChipDefaults.assistChipColors(containerColor = bg),
    )
}

enum class VzChipKind { Primary, Accent, Warning, Neutral }

/**
 * Espacement standard Vintiz pour les colonnes principales d'écran.
 */
object VzSpacing {
    val PageHorizontal = 16.dp
    val SectionGap = 12.dp
    val ItemGap = 8.dp
}
