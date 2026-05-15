plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
}

android {
    namespace = "fr.vintiz.pos"
    compileSdk = 35

    defaultConfig {
        applicationId = "fr.vintiz.pos"
        minSdk = 26
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
            buildConfigField("String", "API_BASE_URL", "\"https://api.dev.vintiz.fr/\"")
            buildConfigField("String", "CLIENT_ID", "\"vintiz-android-dev\"")
        }
        create("prod") {
            dimension = "env"
            buildConfigField("String", "API_BASE_URL", "\"https://api.vintiz.fr/\"")
            buildConfigField("String", "CLIENT_ID", "\"vintiz-android\"")
        }
    }

    signingConfigs {
        create("release") {
            val keystorePath = System.getenv("VINTIZ_KEYSTORE_PATH")
            if (keystorePath != null) {
                storeFile = file(keystorePath)
                storePassword = System.getenv("VINTIZ_KEYSTORE_PASSWORD")
                keyAlias = "vintiz-release"
                keyPassword = System.getenv("VINTIZ_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            applicationIdSuffix = ".debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
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
}

dependencies {
    implementation(project(":core:core-design"))
    implementation(project(":core:core-common"))
    implementation(project(":core:core-network"))
    implementation(project(":core:core-security"))
    implementation(project(":core:core-datastore"))
    implementation(project(":core:core-database"))
    implementation(project(":data:data-auth"))
    implementation(project(":data:data-pos"))
    implementation(project(":data:data-inventory"))
    implementation(project(":data:data-clients"))
    implementation(project(":data:data-hardware"))
    implementation(project(":data:data-cahier"))
    implementation(project(":data:data-reports"))
    implementation(project(":data:data-admin"))
    implementation(project(":data:data-ia"))
    implementation(project(":data:data-notifications"))
    implementation(project(":hardware:hardware-api"))
    implementation(project(":hardware:hardware-escpos-tcp"))
    implementation(project(":hardware:hardware-escpos-usb"))
    implementation(project(":hardware:hardware-zpl-tcp"))
    implementation(project(":hardware:hardware-scanner-hid"))
    implementation(project(":hardware:hardware-scanner-camera"))
    implementation(project(":hardware:hardware-nfc"))
    implementation(project(":hardware:hardware-sumup-rest"))
    implementation(project(":feature:feature-auth"))
    implementation(project(":feature:feature-pos"))
    implementation(project(":feature:feature-inventory"))
    implementation(project(":feature:feature-clients"))
    implementation(project(":feature:feature-settings"))
    implementation(project(":feature:feature-dashboard"))
    implementation(project(":feature:feature-cahier"))
    implementation(project(":feature:feature-admin"))
    implementation(project(":feature:feature-ia"))
    implementation(project(":feature:feature-zones"))

    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)
    implementation(libs.retrofit)
    implementation(libs.androidx.work.runtime)

    implementation(libs.androidx.core.ktx)
    implementation(libs.bundles.lifecycle)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)

    implementation(platform(libs.compose.bom))
    implementation(libs.bundles.compose)
    debugImplementation(libs.compose.ui.tooling)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.navigation.compose)

    implementation(libs.timber)

    testImplementation(libs.bundles.testing)
}
