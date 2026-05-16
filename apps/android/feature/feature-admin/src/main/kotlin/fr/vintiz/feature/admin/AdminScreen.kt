package fr.vintiz.feature.admin

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import fr.vintiz.core.common.Money
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.admin.AdminRepository
import fr.vintiz.data.admin.AdminTransactionDto
import fr.vintiz.data.admin.AuditLogDto
import fr.vintiz.data.admin.PaymentAttemptDto
import fr.vintiz.data.admin.RefundItemDto
import fr.vintiz.data.admin.UserDto
import fr.vintiz.data.reports.ReportsRepository
import fr.vintiz.data.reports.ZReportDto
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

@HiltViewModel
class AdminViewModel @Inject constructor(
    private val admin: AdminRepository,
    private val reports: ReportsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(AdminUiState())
    val state: StateFlow<AdminUiState> = _state.asStateFlow()

    fun loadAll() {
        viewModelScope.launch {
            (admin.transactions() as? VintizResult.Success)?.let { ok ->
                _state.update { it.copy(transactions = ok.value) }
            }
            (admin.users() as? VintizResult.Success)?.let { ok ->
                _state.update { it.copy(users = ok.value) }
            }
            (reports.zReports() as? VintizResult.Success)?.let { ok ->
                _state.update { it.copy(zReports = ok.value) }
            }
            (admin.auditLogs() as? VintizResult.Success)?.let { ok ->
                _state.update { it.copy(auditLogs = ok.value) }
            }
            (admin.paymentAttempts() as? VintizResult.Success)?.let { ok ->
                _state.update { it.copy(paymentAttempts = ok.value) }
            }
        }
    }

    fun selectTab(i: Int) = _state.update { it.copy(tab = i) }

    fun startRefund(tx: AdminTransactionDto) =
        _state.update { it.copy(refundCandidate = tx) }

    fun cancelRefund() = _state.update { it.copy(refundCandidate = null) }

    fun confirmRefund(amountCents: Long, method: String) {
        val tx = _state.value.refundCandidate ?: return
        viewModelScope.launch {
            val item = RefundItemDto(amount_cents = amountCents)
            when (val r = admin.refund(tx.id, listOf(item), method, reason = null)) {
                is VintizResult.Success -> {
                    _state.update {
                        it.copy(refundCandidate = null, lastRefundId = r.value.id)
                    }
                    loadAll()
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(error = r.error.message)
                }
            }
        }
    }
}

data class AdminUiState(
    val tab: Int = 0,
    val transactions: List<AdminTransactionDto> = emptyList(),
    val users: List<UserDto> = emptyList(),
    val zReports: List<ZReportDto> = emptyList(),
    val auditLogs: List<AuditLogDto> = emptyList(),
    val paymentAttempts: List<PaymentAttemptDto> = emptyList(),
    val refundCandidate: AdminTransactionDto? = null,
    val lastRefundId: String? = null,
    val error: String? = null,
)

@Composable
fun AdminScreen(
    onExportPeriod: (from: String?, to: String?) -> Unit = { _, _ -> },
    viewModel: AdminViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsState()
    LaunchedEffect(Unit) { viewModel.loadAll() }

    Scaffold { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            TabRow(selectedTabIndex = state.tab) {
                listOf("Ventes", "Z-Reports", "Utilisateurs", "CB", "Audit").forEachIndexed { i, label ->
                    Tab(selected = state.tab == i, onClick = { viewModel.selectTab(i) }, text = { Text(label) })
                }
            }
            when (state.tab) {
                0 -> TransactionsTab(state.transactions, onRefund = viewModel::startRefund)
                1 -> ZReportsTab(state.zReports, onExportPeriod = onExportPeriod)
                2 -> UsersTab(state.users)
                3 -> PaymentAttemptsTab(state.paymentAttempts)
                else -> AuditTab(state.auditLogs)
            }
        }
    }

    state.refundCandidate?.let { tx ->
        RefundDialog(
            tx = tx,
            onCancel = viewModel::cancelRefund,
            onConfirm = { amount, method -> viewModel.confirmRefund(amount, method) },
        )
    }
}

@Composable
private fun TransactionsTab(items: List<AdminTransactionDto>, onRefund: (AdminTransactionDto) -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        items(items, key = { it.id }) { tx ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(Money(tx.total_cents).format(), style = MaterialTheme.typography.titleMedium)
                        Text("${tx.timestamp} • ${tx.payment_method} • ${tx.cashier_name ?: "—"}",
                            style = MaterialTheme.typography.labelSmall)
                    }
                    Button(onClick = { onRefund(tx) }, enabled = tx.status == "completed") {
                        Text("Refund")
                    }
                }
            }
        }
    }
}

@Composable
private fun ZReportsTab(
    items: List<ZReportDto>,
    onExportPeriod: (from: String?, to: String?) -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        if (items.isNotEmpty()) {
            val periodFrom = items.minOf { it.opened_at }.take(10)
            val periodTo = items.maxOf { it.closed_at }.take(10)
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Text(
                    "Période affichée : $periodFrom → $periodTo",
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.bodyMedium,
                )
                androidx.compose.material3.Button(onClick = { onExportPeriod(periodFrom, periodTo) }) {
                    Text("Exporter période fiscale")
                }
            }
            androidx.compose.material3.HorizontalDivider(Modifier.padding(vertical = 8.dp))
        }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            items(items, key = { it.id }) { z ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text("Caisse ${z.drawer_id} — ${z.opened_at}",
                            style = MaterialTheme.typography.titleMedium)
                        Text("Espèces ${Money(z.total_cash_cents).format()} • " +
                            "CB ${Money(z.total_card_cents).format()} • " +
                            "Chèque ${Money(z.total_cheque_cents).format()}",
                            style = MaterialTheme.typography.bodySmall)
                        val color = when {
                            z.diff_cents > 0 -> MaterialTheme.colorScheme.primary
                            z.diff_cents < 0 -> MaterialTheme.colorScheme.error
                            else -> MaterialTheme.colorScheme.onSurfaceVariant
                        }
                        Text("Écart : ${Money(z.diff_cents).format()}", color = color)
                    }
                }
            }
        }
    }
}

@Composable
private fun UsersTab(items: List<UserDto>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        items(items, key = { it.id }) { u ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(u.username, style = MaterialTheme.typography.titleMedium)
                        Text(u.role, style = MaterialTheme.typography.bodySmall)
                    }
                    if (u.has_pin) Text("PIN ✓") else Text("PIN —",
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun PaymentAttemptsTab(items: List<PaymentAttemptDto>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        if (items.isEmpty()) {
            item {
                Text("Aucune tentative CB enregistrée.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        items(items, key = { it.id }) { a ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(modifier = Modifier.fillMaxWidth().padding(12.dp),
                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(Money(a.amount_cents).format(),
                            style = MaterialTheme.typography.titleMedium)
                        Text(
                            "${a.attempted_at.take(16).replace("T", " à ")} • " +
                                "${a.card_brand ?: "—"} ${a.card_last4 ?: ""} " +
                                (if (a.error_detail != null) "• ${a.error_detail}" else ""),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    val color = when (a.status.lowercase()) {
                        "paid" -> MaterialTheme.colorScheme.primary
                        "pending" -> MaterialTheme.colorScheme.onSurfaceVariant
                        else -> MaterialTheme.colorScheme.error
                    }
                    Text(a.status.uppercase(),
                        style = MaterialTheme.typography.labelLarge,
                        color = color)
                }
            }
        }
    }
}

@Composable
private fun AuditTab(items: List<AuditLogDto>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        items(items, key = { it.id }) { e ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text("${e.entity} • ${e.action}", style = MaterialTheme.typography.titleSmall)
                    Text("${e.timestamp} • ${e.client ?: "—"}",
                        style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

@Composable
private fun RefundDialog(
    tx: AdminTransactionDto,
    onCancel: () -> Unit,
    onConfirm: (Long, String) -> Unit,
) {
    val amount = remember(tx.id) { mutableStateOf(tx.total_cents.toString()) }
    val method = remember(tx.id) { mutableStateOf("cash") }
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Remboursement ${tx.id.take(8)}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = amount.value,
                    onValueChange = { amount.value = it.filter { c -> c.isDigit() } },
                    label = { Text("Montant en cents") },
                )
                HorizontalDivider()
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("cash", "card", "cheque", "credit").forEach { m ->
                        Button(
                            onClick = { method.value = m },
                            enabled = method.value != m,
                        ) { Text(m) }
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = {
                val cents = amount.value.toLongOrNull() ?: 0L
                if (cents > 0) onConfirm(cents, method.value)
            }) { Text("Confirmer") }
        },
        dismissButton = { Button(onClick = onCancel) { Text("Annuler") } },
    )
}

