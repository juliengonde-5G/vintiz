package fr.vintiz.feature.ia

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.ui.Alignment
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.ia.ChecklistItemDto
import fr.vintiz.data.ia.IaRepository
import fr.vintiz.data.ia.TrendSignalDto
import fr.vintiz.data.trends.TrendsRepository
import fr.vintiz.data.trends.WindowProposalDto
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class IaViewModel @Inject constructor(
    private val repo: IaRepository,
    private val trendsRepo: TrendsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(IaUiState())
    val state: StateFlow<IaUiState> = _state.asStateFlow()

    fun loadAll() {
        viewModelScope.launch {
            (repo.weeklyChecklist() as? VintizResult.Success)?.let { ok ->
                _state.update { it.copy(checklist = ok.value.items) }
            }
            (repo.trends() as? VintizResult.Success)?.let { ok ->
                _state.update {
                    it.copy(social = ok.value.social_signals, retail = ok.value.retail_signals)
                }
            }
            loadWindowDisplay()
        }
    }

    fun loadWindowDisplay() {
        viewModelScope.launch {
            when (val r = trendsRepo.currentWindowDisplay()) {
                is VintizResult.Success -> _state.update {
                    it.copy(
                        windowProposal = r.value,
                        windowOrderedIds = extractProductIds(r.value),
                        windowOrderDirty = false,
                        windowError = null,
                    )
                }
                is VintizResult.Failure -> _state.update { it.copy(windowError = r.error.message) }
            }
        }
    }

    fun regenerateWindowDisplay() {
        _state.update { it.copy(windowLoading = true) }
        viewModelScope.launch {
            when (val r = trendsRepo.regenerateWindowDisplay()) {
                is VintizResult.Success -> _state.update {
                    it.copy(
                        windowLoading = false,
                        windowProposal = r.value,
                        windowOrderedIds = extractProductIds(r.value),
                        windowOrderDirty = false,
                        windowError = null,
                    )
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(windowLoading = false, windowError = r.error.message)
                }
            }
        }
    }

    fun acceptWindowDisplay() {
        val id = _state.value.windowProposal?.id ?: return
        viewModelScope.launch {
            (trendsRepo.acceptWindowDisplay(id) as? VintizResult.Success)?.let { ok ->
                _state.update { it.copy(windowProposal = ok.value) }
            }
        }
    }

    /**
     * Déplace un produit d'une position vers le haut (delta=-1) ou
     * le bas (delta=+1) dans la liste locale. Modifications non
     * persistées jusqu'à `saveWindowOrder()`.
     */
    fun moveWindowItem(fromIndex: Int, delta: Int) {
        val current = _state.value.windowOrderedIds
        val target = fromIndex + delta
        if (fromIndex !in current.indices || target !in current.indices) return
        val mutable = current.toMutableList()
        val moved = mutable.removeAt(fromIndex)
        mutable.add(target, moved)
        _state.update { it.copy(windowOrderedIds = mutable, windowOrderDirty = true) }
    }

    fun saveWindowOrder() {
        val id = _state.value.windowProposal?.id ?: return
        val ids = _state.value.windowOrderedIds
        _state.update { it.copy(windowLoading = true) }
        viewModelScope.launch {
            when (val r = trendsRepo.reorderWindowDisplay(id, ids)) {
                is VintizResult.Success -> _state.update {
                    it.copy(
                        windowLoading = false,
                        windowProposal = r.value,
                        windowOrderedIds = extractProductIds(r.value),
                        windowOrderDirty = false,
                    )
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(windowLoading = false, windowError = r.error.message)
                }
            }
        }
    }

    fun selectTab(i: Int) = _state.update { it.copy(tab = i) }
}

private fun extractProductIds(wp: WindowProposalDto?): List<String> {
    val products = wp?.proposal?.get("products") as? List<*> ?: return emptyList()
    return products.mapNotNull { item ->
        (item as? Map<*, *>)?.get("product_id") as? String
    }
}

data class IaUiState(
    val tab: Int = 0,
    val checklist: List<ChecklistItemDto> = emptyList(),
    val social: List<TrendSignalDto> = emptyList(),
    val retail: List<TrendSignalDto> = emptyList(),
    val windowProposal: WindowProposalDto? = null,
    val windowOrderedIds: List<String> = emptyList(),
    val windowOrderDirty: Boolean = false,
    val windowLoading: Boolean = false,
    val windowError: String? = null,
)

@Composable
fun IaScreen(viewModel: IaViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.loadAll() }

    Scaffold { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            Text("Compagnon IA",
                style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.padding(16.dp))
            TabRow(selectedTabIndex = state.tab) {
                listOf("Checklist", "Tendances", "Retail", "Vitrine").forEachIndexed { i, label ->
                    Tab(selected = state.tab == i, onClick = { viewModel.selectTab(i) }, text = { Text(label) })
                }
            }
            when (state.tab) {
                0 -> ChecklistTab(state.checklist)
                1 -> SignalsTab(state.social, title = "Signaux sociaux")
                2 -> SignalsTab(state.retail, title = "Signaux retail")
                else -> WindowTab(
                    state = state,
                    onRegenerate = viewModel::regenerateWindowDisplay,
                    onAccept = viewModel::acceptWindowDisplay,
                    onMoveItem = viewModel::moveWindowItem,
                    onSaveOrder = viewModel::saveWindowOrder,
                )
            }
        }
    }
}

@Composable
private fun ChecklistTab(items: List<ChecklistItemDto>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(items, key = { it.id }) { item ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Row {
                        Text(item.title,
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.titleMedium)
                        AssistChip(onClick = {}, label = { Text(item.priority) })
                    }
                    item.rationale?.let {
                        Text(it, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
private fun WindowTab(
    state: IaUiState,
    onRegenerate: () -> Unit,
    onAccept: () -> Unit,
    onMoveItem: (index: Int, delta: Int) -> Unit,
    onSaveOrder: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Proposition vitrine", style = MaterialTheme.typography.titleLarge)
        Text(
            "Calculée chaque lundi matin (06:00) à partir des produits " +
                "à fort trend_score qui ne sont pas en vitrine. Manager : " +
                "réordonne avec ▲ ▼ puis enregistre l'ordre avant validation.",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            androidx.compose.material3.Button(
                onClick = onRegenerate,
                enabled = !state.windowLoading,
            ) { Text(if (state.windowLoading) "Calcul…" else "Régénérer maintenant") }

            if (state.windowOrderDirty) {
                androidx.compose.material3.Button(
                    onClick = onSaveOrder,
                    enabled = !state.windowLoading,
                ) { Text("Enregistrer l'ordre") }
            }
            state.windowProposal?.takeIf {
                it.accepted_at.isNullOrBlank() && !state.windowOrderDirty
            }?.let {
                androidx.compose.material3.Button(onClick = onAccept) { Text("Valider") }
            }
        }

        state.windowProposal?.let { wp ->
            WindowProposalCard(wp, state.windowOrderedIds, onMoveItem)
        } ?: state.windowError?.let {
            Text(it, color = MaterialTheme.colorScheme.error)
        } ?: Text(
            "Aucune proposition pour la semaine en cours. Cliquer Régénérer.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun WindowProposalCard(
    wp: WindowProposalDto,
    orderedIds: List<String>,
    onMoveItem: (index: Int, delta: Int) -> Unit,
) {
    val productsByIdRaw = (wp.proposal["products"] as? List<*>).orEmpty()
        .mapNotNull { it as? Map<*, *> }
        .associateBy { it["product_id"] as? String ?: "" }
    val orderedProducts = orderedIds.mapNotNull { productsByIdRaw[it] }
    val theme = wp.proposal["theme"] as? String
    val rationale = wp.proposal["rationale"] as? String
    val accepted = !wp.accepted_at.isNullOrBlank()

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Semaine ISO ${wp.iso_week}", style = MaterialTheme.typography.titleMedium)
            Text(
                if (wp.used_llm) "Générée par Claude Haiku"
                else "Générée par règles déterministes",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (accepted) {
                Text("Validée le ${wp.accepted_at!!.take(16).replace("T", " à ")}",
                    color = MaterialTheme.colorScheme.primary)
            } else {
                Text("En attente de validation",
                    color = MaterialTheme.colorScheme.error)
            }
            theme?.takeIf { it.isNotBlank() }?.let {
                Text("Thème : $it", style = MaterialTheme.typography.titleSmall)
            }
            rationale?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("Produits proposés : ${orderedProducts.size}",
                style = MaterialTheme.typography.titleSmall)

            orderedProducts.forEachIndexed { index, m ->
                val name = m["name"] as? String ?: "Produit ${index + 1}"
                val priceCents = (m["price_cents"] as? Number)?.toLong()
                val isFirst = index == 0
                val isLast = index == orderedProducts.lastIndex
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("${index + 1}.",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.width(8.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(name, style = MaterialTheme.typography.bodyMedium)
                        priceCents?.let {
                            Text(
                                fr.vintiz.core.common.Money(it).format(),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    if (!accepted) {
                        IconButton(
                            onClick = { onMoveItem(index, -1) },
                            enabled = !isFirst,
                        ) { Text("▲") }
                        IconButton(
                            onClick = { onMoveItem(index, +1) },
                            enabled = !isLast,
                        ) { Text("▼") }
                    }
                }
            }
            if (!accepted) {
                Text(
                    "Drag-and-drop tactile fluide en V3. Pour l'instant : " +
                        "boutons ▲▼ position par position.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun SignalsTab(signals: List<TrendSignalDto>, title: String) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item { Text(title, style = MaterialTheme.typography.titleLarge) }
        items(signals, key = { it.label }) { s ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(s.label, style = MaterialTheme.typography.titleSmall)
                        Text(s.source, style = MaterialTheme.typography.labelSmall)
                    }
                    Text("${(s.score * 100).toInt()} %")
                }
            }
        }
    }
}
