package fr.vintiz.core.design

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

/**
 * Mappe les tokens Vintiz vers Material 3.
 *
 * Le mode sombre est activé uniquement côté back-office Vintiz
 * (la tablette caisse reste claire pour la lisibilité boutique).
 * Voir docs/DESIGN_SYSTEM.md §Mode sombre.
 */
private val VzLightColors = lightColorScheme(
    primary = VzColors.Teal,
    onPrimary = VzColors.Surface,
    primaryContainer = VzColors.TealSoft,
    onPrimaryContainer = VzColors.TealDeep,
    secondary = VzColors.Gold,
    onSecondary = VzColors.Surface,
    tertiary = VzColors.Accent,
    onTertiary = VzColors.Surface,
    tertiaryContainer = VzColors.AccentSoft,
    onTertiaryContainer = VzColors.Ink,
    background = VzColors.Bg,
    onBackground = VzColors.Ink,
    surface = VzColors.Surface,
    onSurface = VzColors.Ink,
    surfaceVariant = VzColors.BgAlt,
    onSurfaceVariant = VzColors.InkSoft,
    outline = VzColors.Line,
    outlineVariant = VzColors.Line,
)

private val VzDarkColors = darkColorScheme(
    primary = VzColors.TealSoft,
    onPrimary = VzColors.TealDeep,
    primaryContainer = VzColors.TealDeep,
    onPrimaryContainer = VzColors.TealSoft,
    background = VzColors.Ink,
    onBackground = VzColors.Bg,
    surface = VzColors.InkSoft,
    onSurface = VzColors.Bg,
    surfaceVariant = VzColors.InkSoft,
    onSurfaceVariant = VzColors.Line,
    outline = VzColors.InkMute,
)

@Composable
fun VzTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) VzDarkColors else VzLightColors
    MaterialTheme(
        colorScheme = colorScheme,
        typography = VzTypography,
        content = content,
    )
}
