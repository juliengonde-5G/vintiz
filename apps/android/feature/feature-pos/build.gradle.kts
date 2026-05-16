plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
}

android {
    namespace = "fr.vintiz.feature.pos"
    compileSdk = 35
    defaultConfig { minSdk = 26 }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
}

dependencies {
    api(project(":core:core-design"))
    implementation(project(":core:core-common"))
    implementation(project(":domain:domain-pos"))
    implementation(project(":domain:domain-inventory"))
    implementation(project(":domain:domain-clients"))
    implementation(project(":data:data-pos"))
    implementation(project(":data:data-inventory"))
    implementation(project(":data:data-clients"))
    implementation(project(":data:data-loyalty"))
    implementation(project(":data:data-personal-shopper"))
    implementation(project(":hardware:hardware-api"))

    implementation(platform(libs.compose.bom))
    implementation(libs.bundles.compose)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.bundles.lifecycle)

    implementation(libs.hilt.android)
    implementation(libs.hilt.navigation.compose)
    ksp(libs.hilt.compiler)

    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.timber)

    testImplementation(libs.bundles.testing)
    testImplementation(project(":core:core-testing"))
}
