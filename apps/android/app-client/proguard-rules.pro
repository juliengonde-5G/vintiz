# Vintiz Client (B2C) — règles ProGuard / R8.
# Aligné sur :app-pos/proguard-rules.pro pour les libs partagées
# (Retrofit, Moshi, Hilt, Coroutines). Voir docs/ANDROID_SECURITY_AUDIT.md §7.3.

# Diagnostic stack-traces post-mortem (mais pas le code source).
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# Retrofit 2 — interfaces réseau lues par réflexion.
-keepattributes Signature, InnerClasses, EnclosingMethod
-keepattributes RuntimeVisibleAnnotations, RuntimeInvisibleAnnotations
-keepattributes RuntimeVisibleParameterAnnotations, RuntimeInvisibleParameterAnnotations
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response

# Moshi codegen — JsonClass generateAdapter génère un Adapter ".kt"
# qu'on doit garder accessible par nom.
-keep class **JsonAdapter { *; }
-keep,allowobfuscation,allowshrinking @com.squareup.moshi.JsonClass class *
-keep @com.squareup.moshi.JsonClass class * extends com.squareup.moshi.JsonAdapter

# Coroutines — internals lus par réflexion par le debug agent.
-keepclassmembernames class kotlinx.** { volatile <fields>; }

# Hilt / Dagger — composants générés.
-keep class dagger.hilt.** { *; }
-keep class * extends androidx.lifecycle.ViewModel { <init>(...); }
-keepclassmembers class * extends androidx.lifecycle.ViewModel { <init>(...); }

# OkHttp / Conscrypt — runtime selection optional.
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
