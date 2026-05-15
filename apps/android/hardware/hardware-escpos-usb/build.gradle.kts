plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "fr.vintiz.hardware.escpos.usb"
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
    api(project(":core:core-common"))
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.timber)
    testImplementation(libs.bundles.testing)
}
