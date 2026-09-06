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

    // --- Sohbet ekrani (kabuk) ---
    "chat.online": {"tr": "Aura, çevrimiçi", "en": "Aura, online"},
    "chat.settings": {"tr": "Ayarlar", "en": "Settings"},
    "chat.saveAccount": {"tr": "Hesabını Kaydet", "en": "Save your account"},
    "chat.inputHint": {"tr": "Mesaj yaz...", "en": "Type a message..."},
    "chat.send": {"tr": "Gönder", "en": "Send"},
    "chat.a11yAddPhoto": {
      "tr": "Fotoğraf veya belge ekle",
      "en": "Add a photo or document",
    },
    "chat.a11yVoiceStart": {
      "tr": "Sesli görüşme başlat",
      "en": "Start voice call",
    },
    "chat.a11yVoiceEnd": {
      "tr": "Sesli görüşmeyi bitir",
      "en": "End voice call",
    },
    "chat.a11yVideoStart": {
      "tr": "Görüntülü görüşme başlat",
      "en": "Start video call",
    },
    "chat.a11yYou": {"tr": "Senin mesajın", "en": "Your message"},
    "chat.a11yAura": {"tr": "Aura", "en": "Aura"},
    "chat.a11ySaid": {"tr": "Söylediğin", "en": "What you said"},
    "chat.typing": {"tr": "Aura yazıyor", "en": "Aura is typing"},
    "chat.a11ySentPhoto": {
      "tr": "Gönderdiğin fotoğraf",
      "en": "Photo you sent",
    },
    "chat.a11ySentPdf": {"tr": "Gönderdiğin PDF belgesi", "en": "PDF you sent"},
    "chat.attachGallery": {"tr": "Galeri", "en": "Gallery"},
    "chat.attachCamera": {"tr": "Kamera", "en": "Camera"},
    "chat.attachPdf": {"tr": "Belge (PDF)", "en": "Document (PDF)"},
    "chat.voiceIntroTitle": {"tr": "Sesli görüşme", "en": "Voice call"},
    "chat.voiceIntroBody": {
      "tr":
          "Aura ile gerçek zamanlı konuşmak üzeresin. Şimdi telefonun/"
          "tarayıcın mikrofon izni isteyecek - onaylarsan konuşmaya hemen "
          "başlayabilirsin.",
      "en":
          "You're about to talk with Aura in real time. Your phone/browser "
          "will now ask for microphone permission - once you allow it you "
          "can start talking right away.",
    },
    "chat.claimTitle": {"tr": "Hesabını Kaydet", "en": "Save your account"},
    "chat.claimBody": {
      "tr":
          "Bu bilgilerle başka bir cihazdan giriş yapıp hafızana "
          "ulaşabilirsin.",
      "en":
          "With these details you can sign in from another device and reach "
          "your memory.",
    },
    "chat.claimInvalid": {
      "tr": "Geçerli bir email ve en az 6 karakter şifre gir.",
      "en": "Enter a valid email and a password of at least 6 characters.",
    },
    "chat.pwHint": {
      "tr": "Şifre (en az 6 karakter)",
      "en": "Password (at least 6 characters)",
    },
    "chat.save": {"tr": "Kaydet", "en": "Save"},
    "chat.accountSaved": {
      "tr": "Hesabın kaydedildi.",
      "en": "Your account is saved.",
    },
    "chat.genericError": {
      "tr": "Bir hata oluştu.",
      "en": "Something went wrong.",
    },
    "chat.feedbackQ": {"tr": "Bu cevap nasıldı?", "en": "How was this reply?"},
    "chat.feedbackHelp": {
      "tr": "Aura'yı geliştirmemize yardım eder",
      "en": "It helps us improve Aura",
    },
    "chat.feedbackGood": {"tr": "İyi", "en": "Good"},
    "chat.feedbackBad": {"tr": "Kötü", "en": "Bad"},
    "chat.feedbackThanks": {
      "tr": "Teşekkürler, kaydedildi.",
      "en": "Thanks, noted.",
    },
    "chat.a11yMarkGood": {
      "tr": "İyi cevap olarak işaretle",
      "en": "Mark as a good reply",
    },
    "chat.a11yMarkBad": {
      "tr": "Kötü cevap olarak işaretle",
      "en": "Mark as a bad reply",
    },
    "chat.photoTooBig": {
      "tr": "Bu fotoğraf çok büyük (en fazla ~11MB).",
      "en": "This photo is too large (max ~11MB).",
    },
    "chat.pdfTooBig": {
      "tr": "Bu PDF çok büyük (en fazla ~11MB).",
      "en": "This PDF is too large (max ~11MB).",
    },
    "chat.photoPickFailed": {
      "tr": "Fotoğraf seçilemedi.",
      "en": "Couldn't pick a photo.",
    },
    "chat.pdfPickFailed": {
      "tr": "Belge seçilemedi.",
      "en": "Couldn't pick a document.",
    },
    "chat.cameraUnavailable": {
      "tr": "Kamera bu cihazda kullanılamıyor.",
      "en": "The camera isn't available on this device.",
    },
    "chat.cameraFailed": {
      "tr": "Kamera açılamadı.",
      "en": "Couldn't open the camera.",
    },
    "chat.videoUnavailable": {
      "tr": "Görüntülü görüşme bu cihazda kullanılamıyor.",
      "en": "Video calls aren't available on this device.",
    },

    // --- Sesli / goruntulu gorusme ---
    "call.connecting": {"tr": "Bağlanıyor...", "en": "Connecting..."},
    "call.listening": {"tr": "Dinliyorum", "en": "Listening"},
    "call.auraSpeaking": {"tr": "Aura konuşuyor", "en": "Aura is speaking"},
    "call.connectionIssue": {"tr": "Bağlantı sorunu", "en": "Connection issue"},
    "call.back": {"tr": "Geri", "en": "Back"},
    "call.videoTitle": {"tr": "Görüntülü görüşme", "en": "Video call"},
    "call.voiceTitle": {"tr": "Sesli görüşme", "en": "Voice call"},
    "call.startFailed": {
      "tr": "Görüşme başlatılamadı.",
      "en": "Couldn't start the call.",
    },
    "call.auraListeningYou": {
      "tr": "Aura görüşmede, seni dinliyor",
      "en": "Aura is on the call, listening to you",
    },
    "call.yourCameraOn": {
      "tr": "Kendi kameran açık",
      "en": "Your camera is on",
    },
    "call.takePhoto": {"tr": "Fotoğraf çek", "en": "Take a photo"},
    "call.endCall": {"tr": "Görüşmeyi bitir", "en": "End call"},
    "call.reconnect": {"tr": "Yeniden bağlan", "en": "Reconnect"},
    "call.cameraOpening": {
      "tr": "Kamera açılıyor...",
      "en": "Opening camera...",
    },
    "call.cameraRetry": {
      "tr": "Kamerayı tekrar dene",
      "en": "Try the camera again",
    },
    "call.cameraOn": {"tr": "Kamerayı aç", "en": "Turn camera on"},
    "call.cameraOff": {"tr": "Kamerayı kapat", "en": "Turn camera off"},
    "call.cameraFailedLong": {
      "tr":
          "Kamera açılamadı. Tarayıcı/telefon ayarlarından kamera iznini "
          "ver, sonra tekrar dene — sesli konuşmaya bu arada devam "
          "edebilirsin.",
      "en":
          "Couldn't open the camera. Grant camera permission in your "
          "browser/phone settings, then try again — you can keep talking "
          "meanwhile.",
    },
    "call.cameraOffLong": {
      "tr":
          "Kamera kapalı. \"Kamerayı aç\" diyebilir ya da aşağıdaki butona "
          "dokunabilirsin — sesli konuşma açık.",
      "en":
          "Camera is off. Say \"turn camera on\" or tap the button below — "
          "voice is still on.",
    },
    "call.photoAdded": {
      "tr": "Fotoğraf sohbete eklendi ✨",
      "en": "Photo added to the chat ✨",
    },
    "call.photoFailed": {
      "tr": "Fotoğraf çekilemedi, tekrar dener misin?",
      "en": "Couldn't take the photo, try again?",
    },
    "call.retryBtn": {"tr": "Tekrar Dene", "en": "Retry"},
    "call.endBtn": {"tr": "Görüşmeyi Bitir", "en": "End Call"},
    "call.pushToTalk": {"tr": "Basılı tut, konuş", "en": "Hold to talk"},
    "call.pushToTalkA11y": {
      "tr": "Basılı tut ve konuş",
      "en": "Hold and speak",
    },
    "call.pushToTalkHint": {
      "tr": "Basılı tutarken konuş, bırak",
      "en": "Speak while holding, then release",
    },
    "call.recording": {
      "tr": "Kaydediyor, bırakınca gönderilir",
      "en": "Recording, sends when you release",
    },
    "call.micDenied": {
      "tr": "Mikrofon izni verilmedi - cihaz ayarlarından açabilirsin.",
      "en": "Microphone permission denied - you can enable it in settings.",
    },
    "call.audioSendFailed": {
      "tr": "Ses gönderilemedi, tekrar dener misin?",
      "en": "Couldn't send audio, try again?",
    },
  };
}
