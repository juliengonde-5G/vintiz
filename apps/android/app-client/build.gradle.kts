plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
}

android {
    namespace = "fr.vintiz.client"
    compileSdk = 35

    defaultConfig {
        applicationId = "fr.vintiz.client"
        // minSdk 28 (vs 26 :app-pos) — biométrie + FCM stables sur les
        // smartphones/tablettes de moins de 5 ans, cible B2C 2026.
        minSdk = 28
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables { useSupportLibrary = true }
    }

    flavorDimensions += "env"
    productFlavors {
        create("dev") {
            dimension = "env"
            applicationIdSuffix = ".dev"
            versionNameSuffix = "-dev"
            // Tant que api.dev.vintiz.fr n'existe pas en DNS, dev pointe
            // sur prod (sideload boutique + login fonctionnel).
            buildConfigField("String", "API_BASE_URL", "\"https://api.vintiz.fr/\"")
            buildConfigField("String", "CLIENT_ID", "\"vintiz-android-client-dev\"")
        }
        create("prod") {
            dimension = "env"
            buildConfigField("String", "API_BASE_URL", "\"https://api.vintiz.fr/\"")
            buildConfigField("String", "CLIENT_ID", "\"vintiz-android-client\"")
        }
    }

    signingConfigs {
        create("release") {
            val keystorePath = System.getenv("VINTIZ_CLIENT_KEYSTORE_PATH")
                ?: System.getenv("VINTIZ_KEYSTORE_PATH")
            if (keystorePath != null) {
                storeFile = file(keystorePath)
                storePassword = System.getenv("VINTIZ_CLIENT_KEYSTORE_PASSWORD")
                    ?: System.getenv("VINTIZ_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("VINTIZ_CLIENT_KEY_ALIAS") ?: "vintiz-client-release"
                keyPassword = System.getenv("VINTIZ_CLIENT_KEY_PASSWORD")
                    ?: System.getenv("VINTIZ_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            isDebuggable = true
            applicationIdSuffix = ".debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            isDebuggable = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }

    lint {
        abortOnError = false
        warningsAsErrors = false
        checkReleaseBuilds = true
    }
}

dependencies {
    // Core modules — réutilisés tels quels depuis le POS
    implementation(project(":core:core-design"))
    implementation(project(":core:core-common"))
    implementation(project(":core:core-network"))
    implementation(project(":core:core-security"))

    // Data + Feature spécifiques à l'app cliente (Sprint A)
    implementation(project(":data:data-auth-client"))
    implementation(project(":feature:feature-client-onboarding"))
    implementation(project(":feature:feature-client-shell"))

    implementation(libs.androidx.core.ktx)
    implementation(libs.bundles.lifecycle)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)

    // Thème XML de base utilisé par AndroidManifest avant que Compose
    // ne prenne la main.
    implementation("com.google.android.material:material:1.12.0")

    implementation(platform(libs.compose.bom))
    implementation(libs.bundles.compose)
    debugImplementation(libs.compose.ui.tooling)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.navigation.compose)

    // Retrofit + Moshi sont déjà exposés en api() par :core:core-network,
    // pas besoin de les redéclarer ici.
    implementation(libs.timber)
    implementation(libs.kotlinx.coroutines.android)

    testImplementation(libs.bundles.testing)
}
