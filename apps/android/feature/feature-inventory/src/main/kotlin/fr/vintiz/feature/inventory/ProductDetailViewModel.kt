package fr.vintiz.feature.inventory

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import fr.vintiz.core.common.VintizResult
import fr.vintiz.data.inventory.InventoryRepository
import fr.vintiz.data.inventory.ProductDto
import fr.vintiz.data.inventory.ProductPhotoDto
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File

@HiltViewModel
class ProductDetailViewModel @Inject constructor(
    private val repo: InventoryRepository,
    @ApplicationContext private val context: Context,
) : ViewModel() {

    private val _state = MutableStateFlow(ProductDetailUiState())
    val state: StateFlow<ProductDetailUiState> = _state.asStateFlow()

    fun load(productId: String) {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val r = repo.byId(productId)) {
                is VintizResult.Success -> _state.update {
                    it.copy(loading = false, product = r.value)
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.error.message)
                }
            }
            (repo.photos(productId) as? VintizResult.Success)?.let { ok ->
                _state.update { it.copy(photos = ok.value) }
            }
        }
    }

    /** Génère un File temporaire pour qu'Intent IMAGE_CAPTURE y écrive. */
    fun newCaptureFile(): File {
        val dir = File(context.cacheDir, "captures").apply { mkdirs() }
        val file = File(dir, "capture-${System.currentTimeMillis()}.jpg")
        _state.update { it.copy(pendingCaptureFile = file) }
        return file
    }

    /** Appelé après ACTION_IMAGE_CAPTURE succès → upload le fichier. */
    fun confirmCaptured() {
        val file = _state.value.pendingCaptureFile ?: return
        val productId = _state.value.product?.id ?: return
        _state.update { it.copy(uploading = true, error = null) }
        viewModelScope.launch {
            when (val r = repo.uploadPhoto(productId, file)) {
                is VintizResult.Success -> _state.update {
                    it.copy(
                        uploading = false,
                        photos = it.photos + r.value,
                        pendingCaptureFile = null,
                    )
                }
                is VintizResult.Failure -> _state.update {
                    it.copy(uploading = false, error = r.error.message)
                }
            }
        }
    }

    fun cancelCaptured() {
        _state.value.pendingCaptureFile?.delete()
        _state.update { it.copy(pendingCaptureFile = null) }
    }
}

data class ProductDetailUiState(
    val loading: Boolean = false,
    val product: ProductDto? = null,
    val photos: List<ProductPhotoDto> = emptyList(),
    val pendingCaptureFile: File? = null,
    val uploading: Boolean = false,
    val error: String? = null,
)
