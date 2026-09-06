import "dart:ui" show PlatformDispatcher;

/// Hafif arayuz cevirisi (2026-09-06, "hedef dunya" karari).
///
/// Sohbetin KENDISI zaten kullanicinin diline uyum sagliyor (backend
/// DIL_UYUMU_ILKESI). Bu modul yalnizca uygulama KABUGU icin: butonlar,
/// onam ekrani, giris ekrani, hata mesajlari. Codegen yok - basit bir
/// harita; yeni anahtar eklemek tek satir.
///
/// Dil secimi: cihaz dili "tr" ise Turkce, degilse Ingilizce. Kullaniciya
/// bir dil secici GOSTERILMEZ (urun felsefesi: "dil ayari yok").
class I18n {
  static String lang = "tr";

  static void init() {
    try {
      final code = PlatformDispatcher.instance.locale.languageCode
          .toLowerCase();
      lang = code == "tr" ? "tr" : "en";
    } catch (_) {
      lang = "tr";
    }
  }

  static String t(String key) {
    final entry = _s[key];
    if (entry == null) return key;
    return entry[lang] ?? entry["tr"] ?? key;
  }

  static const Map<String, Map<String, String>> _s = {
    // --- Genel / ortak ---
    "common.loading": {"tr": "Yükleniyor", "en": "Loading"},
    "common.cancel": {"tr": "Vazgeç", "en": "Cancel"},
    "common.continue": {"tr": "Devam et", "en": "Continue"},
    "common.retry": {"tr": "Tekrar dene", "en": "Try again"},
    "common.connectionError": {
      "tr": "Bağlantı hatası. Tekrar dener misin?",
      "en": "Connection error. Please try again.",
    },

    // --- Splash ---
    "splash.loading": {"tr": "Aura yükleniyor", "en": "Loading Aura"},

    // --- Onam ekrani ---
    "consent.title": {"tr": "Başlamadan önce", "en": "Before you begin"},
    "consent.blurb": {
      "tr":
          "Aura kişisel bir yapay zekâ arkadaştır — bir terapist, doktor, "
          "avukat ya da mali danışman değildir. Sohbetlerin ve seni "
          "tanımaya yarayan bilgiler, hizmeti sunmak için işlenir. "
          "Detaylar aşağıdaki metinlerde.",
      "en":
          "Aura is a personal AI companion — not a therapist, doctor, lawyer "
          "or financial adviser. Your conversations and the details that "
          "help Aura get to know you are processed to provide the "
          "service. See the documents below for details.",
    },
    "consent.age": {"tr": "18 yaşından büyüğüm.", "en": "I am 18 or older."},
    "consent.acceptPrefix": {
      "tr": "Okudum, kabul ediyorum: ",
      "en": "I have read and accept: ",
    },
    "consent.and": {"tr": " ve ", "en": " and "},
    "consent.privacy": {"tr": "Gizlilik Politikası", "en": "Privacy Policy"},
    "consent.terms": {"tr": "Kullanım Şartları", "en": "Terms of Use"},
    "consent.kvkk": {
      "tr": "KVKK Aydınlatma Metni",
      "en": "Data Processing Notice",
    },
    "consent.button": {"tr": "Kabul et ve başla", "en": "Accept and start"},
    "consent.linkFailed": {
      "tr": "Bağlantı açılamadı",
      "en": "Couldn't open the link",
    },

    // --- Giris / kayit ---
    "auth.subtitle": {
      "tr": "Kişisel yapay zeka asistanın",
      "en": "Your personal AI companion",
    },
    "auth.startFailed": {
      "tr": "Aura başlatılamadı.",
      "en": "Aura couldn't start.",
    },
    "auth.starting": {"tr": "Aura başlatılıyor", "en": "Starting Aura"},
    "auth.sessionEnded": {
      "tr":
          "Başka bir cihazdan giriş yapıldığı için oturumun sona erdi. "
          "Tekrar giriş yap.",
      "en":
          "Your session ended because you signed in on another device. "
          "Please sign in again.",
    },
    "auth.login": {"tr": "Giriş Yap", "en": "Sign In"},
    "auth.register": {"tr": "Kayıt Ol", "en": "Sign Up"},
    "auth.createAccount": {"tr": "Hesap Oluştur", "en": "Create Account"},
    "auth.loggingIn": {"tr": "Giriş yapılıyor", "en": "Signing in"},
    "auth.creatingAccount": {
      "tr": "Hesap oluşturuluyor",
      "en": "Creating account",
    },
    "auth.name": {"tr": "İsmin", "en": "Your name"},
    "auth.email": {"tr": "Email", "en": "Email"},
    "auth.password": {"tr": "Şifre", "en": "Password"},
    "auth.needEmailPass": {
      "tr": "Email ve şifre gerekli.",
      "en": "Email and password are required.",
    },
    "auth.needName": {"tr": "İsim gerekli.", "en": "Name is required."},
    "auth.genericError": {
      "tr": "Bir hata oluştu.",
      "en": "Something went wrong.",
    },
    "auth.backendError": {
      "tr": "Bağlantı hatası. Backend çalışıyor mu?",
      "en": "Connection error. Is the server reachable?",
    },
  };
}
