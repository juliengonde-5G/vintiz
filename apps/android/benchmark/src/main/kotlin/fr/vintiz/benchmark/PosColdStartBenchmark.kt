package fr.vintiz.benchmark

import androidx.benchmark.macro.CompilationMode
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.StartupTimingMetric
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Cold start de l'app POS. Cible : < 1.5 s sur Lenovo Tab M11
 * (cf. docs/MIGRATION_ANDROID_NATIVE.md §5.1).
 *
 * Exécuter avec :
 *   ./gradlew :benchmark:connectedReleaseAndroidTest \
 *     -P android.testInstrumentationRunnerArguments.androidx.benchmark.enabledRules=Macrobenchmark
 */
@RunWith(AndroidJUnit4::class)
class PosColdStartBenchmark {

    @get:Rule
    val benchmark = MacrobenchmarkRule()

    @Test
    fun coldStartNoCompilation() = measure(CompilationMode.None())

    @Test
    fun coldStartPartial() = measure(CompilationMode.Partial())

    private fun measure(mode: CompilationMode) {
        benchmark.measureRepeated(
            packageName = TARGET_PACKAGE,
            metrics = listOf(StartupTimingMetric()),
            compilationMode = mode,
            startupMode = StartupMode.COLD,
            iterations = 5,
            setupBlock = { pressHome() },
        ) {
            startActivityAndWait()
        }
    }

    private companion object {
        const val TARGET_PACKAGE = "fr.vintiz.pos.dev"
    }
}
