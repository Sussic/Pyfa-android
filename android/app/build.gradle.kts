plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.chaquo.python")
}

val bundleLicense by tasks.registering(Copy::class) {
    from(rootProject.file("../LICENSE"))
    into(layout.buildDirectory.dir("generated/licenseAssets"))
}

android {
    namespace = "io.github.sussic.pyfa"
    compileSdk = 36
    buildToolsVersion = "35.0.0"

    defaultConfig {
        applicationId = "io.github.sussic.pyfa"
        minSdk = 24
        targetSdk = 36
        versionCode = 10
        versionName = "0.1.0-b04.1"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
        testInstrumentationRunner = "io.github.sussic.pyfa.DiagnosticTestRunner"
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".dev"
        }
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    sourceSets["main"].assets.srcDir(bundleLicense)
    sourceSets["main"].assets.srcDir(rootProject.file("build/engine/assets"))
    sourceSets["androidTest"].assets.srcDir(rootProject.file("build/engine/testAssets"))
    lint {
        abortOnError = true
        // Newer releases are reviewed as toolchain changes, not lint failures.
        disable += setOf("GradleDependency", "AndroidGradlePluginVersion")
    }
}

kotlin { jvmToolchain(17) }

chaquopy {
    defaultConfig {
        version = "3.11"
        pip {
            options("--no-index", "--find-links", rootProject.file("build/python-wheels").absolutePath)
            install("Logbook==1.7.0.post0")
            install("SQLAlchemy==1.4.50")
            install("greenlet==3.0.1")
            install("chaquopy-libcxx==180000")
        }
        // Keep source available for development traceback/provenance inspection.
        pyc { src = false }
    }
    sourceSets.getByName("main") {
        // Explicit sources replace Chaquopy's default directory convention.
        setSrcDirs(listOf(file("src/main/python"), rootProject.file("build/engine/python")))
    }
}

val verifyEngineInputs by tasks.registering {
    doLast {
        check(rootProject.file("build/engine/assets/engine/eve.db").isFile) {
            "Run Python 3.11 android/prepare-engine.py before Gradle. See android/README.md."
        }
        check(rootProject.file("build/python-wheels").listFiles()?.count { it.extension == "whl" } == 6) {
            "Run android/prepare-dependencies.py before Gradle."
        }
    }
}

// AGP resolves this legacy source directory without retaining its producer's
// task dependency. Make the license available before the asset merge.
tasks.named("preBuild") { dependsOn(bundleLicense, verifyEngineInputs) }

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.10.01")
    implementation(composeBom)
    implementation("androidx.activity:activity-compose:1.11.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")

    androidTestImplementation(composeBom)
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.test:runner:1.7.0")
}
