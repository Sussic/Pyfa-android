package io.github.sussic.pyfa

import android.os.Bundle
import androidx.test.runner.AndroidJUnitRunner

/** Legacy direct-engine probes never open or alter the user's persisted graph. */
class DiagnosticTestRunner : AndroidJUnitRunner() {
    override fun onCreate(arguments: Bundle) {
        if (!arguments.containsKey("b02_phase") && !arguments.containsKey("b03_phase") &&
            !arguments.containsKey("b032_phase") && !arguments.containsKey("b041_phase") &&
            !arguments.containsKey("b0421_phase") && !arguments.containsKey("b0422_phase") &&
            !arguments.containsKey("b04231_phase") && !arguments.containsKey("b04232_phase") &&
            !arguments.containsKey("b04233_phase") && !arguments.containsKey("b051_phase") &&
            !arguments.containsKey("b052_phase") && !arguments.containsKey("b053_phase") &&
            !arguments.containsKey("b054_phase") && !arguments.containsKey("b061_phase") &&
            !arguments.containsKey("b062_phase"))
            EngineRuntime.useEphemeralStorageForDiagnostics()
        super.onCreate(arguments)
    }
}
