plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "fr.vintiz.hardware.scanner.camera"
    compileSdk = 35
    defaultConfig { minSdk = 26 }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    api(project(":hardware:hardware-api"))
    api(project(":domain:domain-inventory"))

    api("androidx.camera:camera-core:1.4.1")
    api("androidx.camera:camera-camera2:1.4.1")
    api("androidx.camera:camera-lifecycle:1.4.1")
    api("androidx.camera:camera-view:1.4.1")
    api("com.google.mlkit:barcode-scanning:17.3.0")

    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.timber)
}
