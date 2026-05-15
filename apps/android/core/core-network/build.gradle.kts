plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.ksp)
}

android {
    namespace = "fr.vintiz.core.network"
    compileSdk = 35

    defaultConfig { minSdk = 26 }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions { jvmTarget = "17" }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    api(project(":core:core-common"))
    api(project(":core:core-security"))

    api(libs.retrofit)
    api(libs.retrofit.converter.moshi)
    api(libs.okhttp)
    implementation(libs.okhttp.logging)
    api(libs.moshi)
    api(libs.moshi.kotlin)
    ksp("com.squareup.moshi:moshi-kotlin-codegen:1.15.1")

    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.timber)

    testImplementation(libs.bundles.testing)
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
}
