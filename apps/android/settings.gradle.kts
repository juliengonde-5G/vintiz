pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "vintiz-android"

include(":app")

// Core (transverse)
include(":core:core-design")
include(":core:core-common")
include(":core:core-network")
include(":core:core-security")
include(":core:core-datastore")
include(":core:core-database")
include(":core:core-testing")

// Hardware
include(":hardware:hardware-api")
include(":hardware:hardware-escpos-tcp")
include(":hardware:hardware-escpos-usb")
include(":hardware:hardware-zpl-tcp")
include(":hardware:hardware-scanner-hid")
include(":hardware:hardware-scanner-camera")
include(":hardware:hardware-nfc")
include(":hardware:hardware-sumup-rest")

// Data
include(":data:data-auth")
include(":data:data-pos")
include(":data:data-inventory")
include(":data:data-clients")
include(":data:data-hardware")
include(":data:data-cahier")
include(":data:data-reports")
include(":data:data-admin")
include(":data:data-ia")
include(":data:data-notifications")

// Domain
include(":domain:domain-pos")
include(":domain:domain-inventory")
include(":domain:domain-clients")
include(":domain:domain-cahier")
include(":domain:domain-reports")

// Feature (Compose)
include(":feature:feature-auth")
include(":feature:feature-pos")
include(":feature:feature-inventory")
include(":feature:feature-clients")
include(":feature:feature-settings")
include(":feature:feature-dashboard")
include(":feature:feature-cahier")
include(":feature:feature-admin")
include(":feature:feature-ia")
include(":feature:feature-zones")

// Benchmark / Baseline Profile
include(":benchmark")
