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
    "common.error": {"tr": "Hata", "en": "Error"},
    "common.remove": {"tr": "Kaldır", "en": "Remove"},
    "common.saving": {"tr": "Kaydediliyor", "en": "Saving"},
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

    // --- Kilit ekrani / PIN tus takimi (lock_screen + set_pin_screen) ---
    "lock.title": {"tr": "Aura kilitli", "en": "Aura is locked"},
    "lock.wrongPin": {"tr": "Yanlış PIN", "en": "Wrong PIN"},
    "lock.tooManyAttempts": {
      "tr": "5 kez yanlış girdin, 30 saniye bekle",
      "en": "5 wrong tries — wait 30 seconds",
    },
    "lock.secondsShort": {"tr": "sn", "en": "s"},
    "lock.unlockBiometric": {
      "tr": "Biyometrik ile aç",
      "en": "Unlock with biometrics",
    },
    "pin.appBarTitle": {"tr": "PIN Belirle", "en": "Set PIN"},
    "pin.choose": {
      "tr": "4 haneli bir PIN belirle",
      "en": "Choose a 4-digit PIN",
    },
    "pin.reenter": {"tr": "PIN'i tekrar gir", "en": "Re-enter your PIN"},
    "pin.mismatch": {
      "tr": "PIN'ler eşleşmedi, baştan dene",
      "en": "PINs didn't match — start over",
    },
    "pin.a11yField": {"tr": "4 haneli PIN", "en": "4-digit PIN"},
    "pin.a11yDigitsEntered": {"tr": "hane girildi", "en": "digits entered"},
    "pin.a11yBackspace": {"tr": "Sil", "en": "Delete"},

    // --- Gizli sohbetler ekrani ---
    "hidden.appBarTitle": {"tr": "Gizli Sohbetler", "en": "Hidden Chats"},
    "hidden.loading": {
      "tr": "Gizli sohbetler yükleniyor",
      "en": "Loading hidden chats",
    },
    "hidden.loadFailed": {
      "tr": "Gizli sohbetler yüklenemedi.",
      "en": "Couldn't load hidden chats.",
    },
    "hidden.empty": {
      "tr":
          "Henüz gizli bir sohbet yok. Kod cümleni tek başına bir mesaj "
          "olarak gönderirsen, o andan sonraki konuşma burada saklanır.",
      "en":
          "No hidden chats yet. Send your code phrase on its own as a "
          "message and everything said after that is kept here.",
    },

    // --- Ayarlar ekrani ---
    "settings.loading": {"tr": "Ayarlar yükleniyor", "en": "Loading settings"},
    "settings.saved": {"tr": "Ayarlar kaydedildi", "en": "Settings saved"},
    "settings.sectionPersonal": {
      "tr": "Kişisel Bilgiler",
      "en": "Personal details",
    },
    "settings.sectionBehavior": {
      "tr": "Aura Nasıl Davransın",
      "en": "How Aura should behave",
    },
    "settings.sectionPrivacy": {"tr": "Gizlilik", "en": "Privacy"},
    "settings.sectionFreeInstruction": {
      "tr": "Serbest Talimat",
      "en": "Free-form instruction",
    },
    "settings.sectionMemory": {"tr": "Hafızam", "en": "My memory"},
    "settings.proNoLimit": {
      "tr": "Pro hesap - günlük kullanım sınırın yok.",
      "en": "Pro account — no daily usage limit.",
    },
    "settings.usageToday": {
      "tr": "Bugünkü ücretsiz kullanım",
      "en": "Today's free usage",
    },
    "settings.resetsTomorrow": {
      "tr": "yarın sıfırlanır",
      "en": "resets tomorrow",
    },
    "settings.usageMessages": {"tr": "Mesaj", "en": "Messages"},
    "settings.messagesLeftSuffix": {
      "tr": "mesaj kaldı",
      "en": "messages left",
    },
    "settings.minutesLeftSuffix": {"tr": "dk kaldı", "en": "min left"},
    "settings.unitMin": {"tr": "dk", "en": "min"},
    "settings.a11yUsed": {"tr": "kullanıldı", "en": "used"},
    "settings.styleBalanced": {"tr": "Dengeli", "en": "Balanced"},
    "settings.styleWarmth": {"tr": "Sıcaklık", "en": "Warmth"},
    "settings.styleDistant": {"tr": "Mesafeli", "en": "Distant"},
    "settings.styleWarm": {"tr": "Sıcak", "en": "Warm"},
    "settings.styleFormality": {"tr": "Resmiyet", "en": "Formality"},
    "settings.styleFormal": {"tr": "Resmi", "en": "Formal"},
    "settings.styleCasual": {"tr": "Samimi", "en": "Casual"},
    "settings.styleHumor": {"tr": "Mizah", "en": "Humor"},
    "settings.stylePlain": {"tr": "Düz", "en": "Plain"},
    "settings.stylePlayful": {"tr": "Şakacı", "en": "Playful"},
    "settings.behaviorBlurb": {
      "tr":
          "Artık burada elle ayar yok — Aura, konuşma tarzından kendi "
          "kendine öğreniyor ve zamanla sana uyum sağlıyor.",
      "en":
          "No manual sliders here anymore — Aura learns from how you talk "
          "and adapts to you over time.",
    },
    "settings.styleLearning": {
      "tr":
          "Henüz öğreniyor — birkaç mesaj sonra burada nasıl bir uyum "
          "sağladığını görebileceksin.",
      "en":
          "Still learning — after a few messages you'll see how it's "
          "adapting here.",
    },
    "settings.freeInstructionA11y": {
      "tr": "Aura için serbest talimat",
      "en": "Free-form instruction for Aura",
    },
    "settings.freeInstructionHint": {
      "tr": "Örnek: Beni şakacı bul ama iş konularında ciddi ol.",
      "en": "Example: Be playful with me, but serious about work.",
    },
    "settings.lockToggleTitle": {
      "tr": "Uygulama kilidi (PIN)",
      "en": "App lock (PIN)",
    },
    "settings.lockToggleSub": {
      "tr": "Aura'yı her açışında PIN sorulsun",
      "en": "Ask for a PIN every time you open Aura",
    },
    "settings.hidePreviewTitle": {
      "tr": "Bildirim önizlemesini gizle",
      "en": "Hide notification previews",
    },
    "settings.hidePreviewSub": {
      "tr": "Kilit ekranında hatırlatma içeriği yerine \"Aura\" yazsın",
      "en": "Show \"Aura\" on the lock screen instead of the reminder text",
    },
    "settings.changePin": {"tr": "PIN'i değiştir", "en": "Change PIN"},
    "settings.biometricSub": {
      "tr": "Parmak izi / yüz tanıma ile hızlı giriş",
      "en": "Quick unlock with fingerprint / face recognition",
    },
    "settings.secretPhraseTitle": {
      "tr": "Gizli mod kod cümlesi",
      "en": "Hidden-mode code phrase",
    },
    "settings.secretPhraseSetInfo": {
      "tr":
          "Bir kod belirlendi. Sohbette bu cümleyi tek başına gönderirsen "
          "gizli mod açılır/kapanır.",
      "en":
          "A code is set. Send this phrase on its own in chat to toggle "
          "hidden mode on or off.",
    },
    "settings.secretPhraseUnsetInfo": {
      "tr":
          "Kendi cümleni belirle. Sohbette bunu tek başına bir mesaj olarak "
          "gönderirsen, o andan sonraki konuşma normal geçmişte görünmez.",
      "en":
          "Set your own phrase. Send it on its own as a message in chat and "
          "everything said after that stays out of your normal history.",
    },
    "settings.secretPhraseHint": {
      "tr": "örn: bugün ay çok parlak",
      "en": "e.g. the moon is bright tonight",
    },
    "settings.secretPhraseSaveTooltip": {
      "tr": "Gizli mod kodunu kaydet",
      "en": "Save hidden-mode code",
    },
    "settings.secretPhraseSet": {
      "tr": "Gizli mod kodu ayarlandı",
      "en": "Hidden-mode code set",
    },
    "settings.secretPhraseSetFailed": {
      "tr": "Kod ayarlanamadı, tekrar dene",
      "en": "Couldn't set the code, try again",
    },
    "settings.secretPhraseRemoveTitle": {
      "tr": "Gizli mod kodunu kaldır",
      "en": "Remove hidden-mode code",
    },
    "settings.secretPhraseRemoveBody": {
      "tr":
          "Kod kaldırılınca gizli mod bir daha tetiklenemez. Zaten "
          "kaydedilmiş gizli sohbetler etkilenmez.",
      "en":
          "Once removed, hidden mode can't be triggered again. Hidden chats "
          "already saved are not affected.",
    },
    "settings.removeCode": {"tr": "Kodu kaldır", "en": "Remove code"},
    "settings.viewHiddenChats": {
      "tr": "Gizli sohbetleri gör",
      "en": "View hidden chats",
    },
    "settings.lockRemoveTitle": {"tr": "Kilidi kaldır", "en": "Remove lock"},
    "settings.lockRemoveBody": {
      "tr": "Uygulama kilidini kapatmak istediğine emin misin?",
      "en": "Are you sure you want to turn off the app lock?",
    },
    "settings.lockRemoveBodyWithPhrase": {
      "tr":
          "Uygulama kilidini kapatmak istediğine emin misin? Gizli mod kod "
          "cümlen de birlikte kaldırılacak (gizli sohbetlere bir daha "
          "erişilemez).",
      "en":
          "Are you sure you want to turn off the app lock? Your hidden-mode "
          "code phrase will be removed too (hidden chats become "
          "permanently inaccessible).",
    },
    "settings.memoryBlurb": {
      "tr":
          "Aura senin hakkında bunları hatırlıyor. İstemediğini "
          "silebilirsin.",
      "en":
          "Aura remembers these things about you. You can delete anything "
          "you'd rather it forgot.",
    },
    "settings.memoryLoading": {
      "tr": "Hafıza yükleniyor",
      "en": "Loading memory",
    },
    "settings.memoryLoadFailed": {
      "tr": "Hafıza yüklenemedi",
      "en": "Couldn't load memory",
    },
    "settings.memoryEmpty": {
      "tr": "Henüz hiçbir şey hatırlamıyor.",
      "en": "Nothing remembered yet.",
    },
    "settings.memoryTreeA11yPre": {"tr": "Hafıza ağacı —", "en": "Memory tree —"},
    "settings.memoryTreeA11yPost": {
      "tr": "kayıt, kategorilere göre görsel özet",
      "en": "entries, a visual summary by category",
    },
    "settings.pinTooltip": {
      "tr": "Hep hatırla (sabitle)",
      "en": "Always remember (pin)",
    },
    "settings.unpinTooltip": {
      "tr": "Sabitlemeyi kaldır",
      "en": "Unpin",
    },
    "settings.forgetTooltip": {"tr": "Unut", "en": "Forget"},
    "settings.pinnedMsg": {
      "tr": "Sabitlendi, hep net hatırlanacak",
      "en": "Pinned — it'll always be remembered clearly",
    },
    "settings.unpinnedMsg": {
      "tr": "Sabitleme kaldırıldı, zamanla soluklaşabilir",
      "en": "Unpinned — it may fade over time",
    },
    "settings.memoryForgottenSuffix": {"tr": "unutuldu", "en": "forgotten"},
    "settings.deleteFailed": {
      "tr": "Silinemedi, tekrar dene",
      "en": "Couldn't delete, try again",
    },
    "settings.actionFailed": {
      "tr": "İşlem başarısız, tekrar dene",
      "en": "Action failed, try again",
    },
    "settings.logout": {"tr": "Çıkış yap", "en": "Sign out"},
    "settings.logoutBody": {
      "tr":
          "Hesabın kaydedilmediyse (anonimse) bu cihazdan çıktığında "
          "geçmişine bir daha erişemeyebilirsin.",
      "en":
          "If your account isn't saved (anonymous), you may lose access to "
          "your history when you sign out on this device.",
    },
    "settings.deleteAccountTitle": {"tr": "Hesabı sil", "en": "Delete account"},
    "settings.deleteAccountLink": {
      "tr": "Hesabı ve tüm verileri sil",
      "en": "Delete account and all data",
    },
    "settings.deleteAccountBody": {
      "tr":
          "Tüm sohbet geçmişin, hafızan ve hesabın kalıcı olarak silinecek. "
          "Bu işlem geri alınamaz.\n\nOnaylamak için aşağıya {word} yaz.",
      "en":
          "Your entire chat history, memory and account will be permanently "
          "deleted. This can't be undone.\n\nType {word} below to confirm.",
    },
    "settings.deleteConfirmWord": {"tr": "SIL", "en": "DELETE"},
    "settings.deletePermanently": {
      "tr": "Kalıcı olarak sil",
      "en": "Delete permanently",
    },
    "settings.deleteAccountFailed": {
      "tr": "Silme başarısız, tekrar dene.",
      "en": "Deletion failed, try again.",
    },
  };
}
