plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.ksp)
}

android {
    namespace = "fr.vintiz.data.clients"
    compileSdk = 35
    defaultConfig { minSdk = 26 }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    api(project(":core:core-common"))
    api(project(":core:core-network"))
    api(project(":core:core-database"))
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.timber)
    ksp("com.squareup.moshi:moshi-kotlin-codegen:1.15.1")

    testImplementation(libs.bundles.testing)
}
