import java.util.Properties
import java.io.FileInputStream

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Play Store icin gercek imzalama (2026-08-25 - kullanicinin kurulum
// hatasi + "Play Store'a uygun yapmaliyiz" talebi uzerine). key.properties
// ve keystore/*.jks dosyalari BILEREK .gitignore'da - gercek imzalama
// anahtari asla git'e girmemeli. Dosya yoksa (ornek: baska bir makinede
// ilk kurulum) sessizce debug anahtarina duser, build hic kirilmaz.
val keystorePropertiesFile = rootProject.file("key.properties")
val keystoreProperties = Properties()
val hasKeystoreProperties = keystorePropertiesFile.exists()
if (hasKeystoreProperties) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

android {
    namespace = "com.auraapp.assistant"
    // flutter_secure_storage (2026-08-26, PIN/biyometrik kilit icin
    // eklendi) SDK 37 gerektiriyor - flutter.compileSdkVersion (36)
    // yetmiyor, gradle uyarisinin onerdigi gibi sabit 37'ye cikarildi
    // (geriye donuk uyumlu, alt SDK'lari calistiran cihazlari etkilemez).
    compileSdk = 37
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        // flutter_local_notifications (2026-08-26, hatirlatma ozelligi)
        // bunu istiyor - java.time gibi yeni API'leri eski Android
        // surumlerinde de kullanilabilir kilan bir derleme-zamani araci,
        // calisma zamaninda ekstra bir izin/davranis degisikligi yok.
        isCoreLibraryDesugaringEnabled = true
    }

    defaultConfig {
        // NOT (2026-08-24): "com.example.*" varsayilan placeholder'di - Google
        // Play bunu asla kabul etmez, ve bu deger Play Store'a ilk yayindan
        // SONRA bir daha degistirilemez. Gecici olarak makul bir degere
        // cekildi (com.auraapp.assistant) - gercek yayin oncesi kendi
        // marka/domain kararinizla degistirebilirsiniz, henuz KESIN degil.
        applicationId = "com.auraapp.assistant"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasKeystoreProperties) {
            create("release") {
                keyAlias = keystoreProperties["keyAlias"] as String
                keyPassword = keystoreProperties["keyPassword"] as String
                storeFile = file(keystoreProperties["storeFile"] as String)
                storePassword = keystoreProperties["storePassword"] as String
            }
        }
    }

    buildTypes {
        release {
            // key.properties + keystore varsa gercek release anahtariyla
            // imzalar, yoksa (ornek: baska bir gelistirme makinesi) eskisi
            // gibi debug anahtarina duser - build hicbir zaman kirilmaz.
            signingConfig = if (hasKeystoreProperties) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")
}

flutter {
    source = "../.."
}
