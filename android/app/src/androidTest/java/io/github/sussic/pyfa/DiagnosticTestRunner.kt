package io.github.sussic.pyfa

import android.os.Bundle
import androidx.test.runner.AndroidJUnitRunner

/** Legacy direct-engine probes never open or alter the user's persisted graph. */
class DiagnosticTestRunner : AndroidJUnitRunner() {
    override fun onCreate(arguments: Bundle) {
        if (!arguments.containsKey("b02_phase") && !arguments.containsKey("b03_phase") && !arguments.containsKey("b032_phase")) EngineRuntime.useEphemeralStorageForDiagnostics()
        super.onCreate(arguments)
    }
}
