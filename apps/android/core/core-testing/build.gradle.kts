plugins {
    alias(libs.plugins.kotlin.jvm)
}

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
kotlin { jvmToolchain(17) }

dependencies {
    api(project(":core:core-common"))
    api(project(":core:core-security"))
    api(project(":hardware:hardware-api"))
    api(libs.kotlinx.coroutines.core)
    api(libs.kotlinx.coroutines.test)
    api(libs.bundles.testing)
}

tasks.withType<Test> { useJUnitPlatform() }
