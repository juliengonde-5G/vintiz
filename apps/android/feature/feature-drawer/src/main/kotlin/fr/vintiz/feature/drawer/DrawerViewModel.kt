package fr.vintiz.feature.drawer

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.Money
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.pos.PosApi
import fr.vintiz.data.pos.dto.DrawerCloseRequest
import fr.vintiz.data.pos.dto.DrawerOpenRequest
import fr.vintiz.data.pos.dto.DrawerResponse
import fr.vintiz.data.reports.ReportsApi
import fr.vintiz.data.reports.ZReportDto
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import timber.log.Timber
import java.io.IOException
import retrofit2.HttpException

/**
 * Gestion ouverture / fermeture de la caisse + Z-Report.
 *
 * Workflow :
 *  1. État `Idle` au mount → fetch /pos/drawer/current. Soit on a
 *     une caisse ouverte (DrawerResponse), soit null.
 *  2. État `Open` quand drawer ouvert : affichage fond initial,
 *     bouton "Fermer".
 *  3. État `Close` : saisie du montant compté → POST /drawer/close →
 *     bascule sur `Closed` avec Z-Report fetched depuis /pos/z-reports.
 *  4. Sinon `Empty` (pas de drawer) → saisie fond initial → POST
 *     /drawer/open → bascule sur `Open`.
 */
@HiltViewModel
class DrawerViewModel @Inject constructor(
    private val pos: PosApi,
    private val reports: ReportsApi,
) : ViewModel() {

    private val _state = MutableStateFlow(DrawerUiState())
    val state: StateFlow<DrawerUiState> = _state.asStateFlow()

    fun refresh() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            val current = try {
                pos.drawerCurrent()
            } catch (io: IOException) {
                _state.update { it.copy(loading = false, error = "Connexion indisponible") }
                return@launch
            } catch (http: HttpException) {
                if (http.code() == 404) null
                else {
                    _state.update { it.copy(loading = false, error = "Erreur HTTP ${http.code()}") }
                    return@launch
                }
            }
            _state.update {
                it.copy(
                    loading = false,
                    current = current,
                    phase = if (current?.status == "open") DrawerPhase.Open else DrawerPhase.Empty,
                )
            }
        }
    }

    fun onOpeningAmountChange(v: String) {
        _state.update { it.copy(openingAmountInput = v.filter { c -> c.isDigit() }) }
    }

    fun onClosingAmountChange(v: String) {
        _state.update { it.copy(closingAmountInput = v.filter { c -> c.isDigit() }) }
    }

    fun openDrawer() {
        // Backend accepte EUR Decimal pas cents. L'input UI est en
        // cents (numpad) → on divise par 100 avant d'envoyer.
        val amount = (_state.value.openingAmountInput.toLongOrNull() ?: 0L) / 100.0
        _state.update { it.copy(submitting = true, error = null) }
        viewModelScope.launch {
            try {
                val resp = pos.drawerOpen(DrawerOpenRequest(opening_amount = amount))
                _state.update {
                    it.copy(
                        submitting = false,
                        current = resp,
                        phase = DrawerPhase.Open,
                        openingAmountInput = "",
                    )
                }
            } catch (t: Throwable) {
                Timber.w(t, "drawerOpen KO")
                _state.update {
                    it.copy(submitting = false, error = "Ouverture caisse impossible")
                }
            }
        }
    }

    fun startClose() {
        _state.update { it.copy(phase = DrawerPhase.Close, closingAmountInput = "") }
    }

    fun closeDrawer() {
        val amount = (_state.value.closingAmountInput.toLongOrNull() ?: 0L) / 100.0
        _state.update { it.copy(submitting = true, error = null) }
        viewModelScope.launch {
            try {
                val closed = pos.drawerClose(DrawerCloseRequest(closing_amount = amount))
                // Une fois fermé, on récupère le Z-Report correspondant.
                val zReport = try {
                    reports.zReports().firstOrNull { it.drawer_id == closed.drawer_id }
                } catch (t: Throwable) {
                    Timber.w(t, "Z-Report fetch KO — UI affichera juste les totaux drawer")
                    null
                }
                _state.update {
                    it.copy(
                        submitting = false,
                        current = closed,
                        zReport = zReport,
                        phase = DrawerPhase.Closed,
                        closingAmountInput = "",
                    )
                }
            } catch (t: Throwable) {
                Timber.w(t, "drawerClose KO")
                _state.update {
                    it.copy(submitting = false, error = "Fermeture caisse impossible")
                }
            }
        }
    }

    fun cancelClose() {
        _state.update { it.copy(phase = DrawerPhase.Open, closingAmountInput = "") }
    }

    /** Retour à l'état post-fermeture vers une nouvelle ouverture. */
    fun reset() {
        _state.value = DrawerUiState()
        refresh()
    }
}

enum class DrawerPhase { Loading, Empty, Open, Close, Closed }

data class DrawerUiState(
    val phase: DrawerPhase = DrawerPhase.Loading,
    val loading: Boolean = false,
    val submitting: Boolean = false,
    val current: DrawerResponse? = null,
    val zReport: ZReportDto? = null,
    val openingAmountInput: String = "",
    val closingAmountInput: String = "",
    val error: String? = null,
) {
    val openingAmount: Money?
        get() = current?.opening_amount?.let { Money((it * 100).toLong()) }

    val closingAmount: Money?
        get() = current?.closing_amount?.let { Money((it * 100).toLong()) }
}
