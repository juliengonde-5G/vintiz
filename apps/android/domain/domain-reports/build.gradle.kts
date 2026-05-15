plugins { alias(libs.plugins.kotlin.jvm) }
java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
kotlin { jvmToolchain(17) }
dependencies {
    api(project(":core:core-common"))
    testImplementation(libs.bundles.testing)
}
tasks.withType<Test> { useJUnitPlatform() }
