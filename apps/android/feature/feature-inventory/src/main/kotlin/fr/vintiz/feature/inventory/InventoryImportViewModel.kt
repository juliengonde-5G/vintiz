package fr.vintiz.feature.inventory

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.inventory.CsvImportResultDto
import fr.vintiz.data.inventory.InventoryRepository
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File

@HiltViewModel
class InventoryImportViewModel @Inject constructor(
    private val repo: InventoryRepository,
    @ApplicationContext private val context: Context,
) : ViewModel() {

    private val _state = MutableStateFlow(ImportUiState())
    val state: StateFlow<ImportUiState> = _state.asStateFlow()

    fun pickFile(uri: Uri) {
        // On copie le contenu dans cacheDir pour avoir un File stable
        // — l'Uri ACTION_OPEN_DOCUMENT n'est pas garanti accessible
        // après la callback.
        val target = File(context.cacheDir, "import-${System.currentTimeMillis()}.csv")
        viewModelScope.launch {
            try {
                context.contentResolver.openInputStream(uri)?.use { input ->
                    target.outputStream().use { output -> input.copyTo(output) }
                }
                _state.update {
                    it.copy(
                        file = target,
                        fileSize = target.length(),
                        result = null,
                        error = null,
                    )
                }
            } catch (t: Throwable) {
                _state.update { it.copy(error = "Lecture fichier impossible : ${t.message}") }
            }
        }
    }

    fun previewImport() = runImport(dryRun = true)
    fun confirmImport() = runImport(dryRun = false)

    private fun runImport(dryRun: Boolean) {
        val file = _state.value.file ?: return
        _state.update { it.copy(running = true, result = null, error = null) }
        viewModelScope.launch {
            when (val r = repo.importCsv(file, dryRun)) {
                is VintizResult.Success -> _state.update {
                    it.copy(running = false, result = r.value)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(running = false, error = r.error.message)
                }
            }
        }
    }

    fun reset() {
        _state.value.file?.delete()
        _state.value = ImportUiState()
    }
}

data class ImportUiState(
    val file: File? = null,
    val fileSize: Long = 0L,
    val running: Boolean = false,
    val result: CsvImportResultDto? = null,
    val error: String? = null,
)
