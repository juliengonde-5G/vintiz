plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "fr.vintiz.hardware.sumup.sdk"
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

    // Le SDK SumUp Android n'est pas inclus tant que les credentials
    // (Affiliate Key + App ID) ne sont pas configurés côté Mac dev —
    // voir docs/ANDROID_PROD_OPS.md §1. Quand prêt, décommenter :
    //
    //   implementation("com.sumup:merchant-sdk:5.+")
    //
    // et brancher SumUpAPI.openLoginActivity() / openCheckoutActivity()
    // dans SumUpSdkTerminal.pay().

    testImplementation(libs.bundles.testing)
}
