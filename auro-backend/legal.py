"""Yasal metinler (2026-09-06, yayin hazirligi B adimi).

DIKKAT - TASLAK: Bu metinler bir hukukcu tarafindan INCELENMEDI. Yayindan
once KVKK/GDPR uzmanı bir avukata gozden gecirtilmeli. Sirket unvani, veri
saklama suresi, saklama bolgesi ve iletisim adresi gibi [KOSELI PARANTEZ]
alanlar doldurulmali.

Iceriik Aura'nin GERCEK veri islemesini yansitir:
- Toplanan: e-posta (hesap kaydedilirse) + sifre hash'i, isim, sohbet
  mesajlari, cikarilan hafiza bilgileri, ruh hali kayitlari, mesajlardan
  cikarilan hatirlatmalar, uslup vektoru (4 sayi), kullanim sayaclari,
  (opsiyonel) konum lat/lon/sehir - hava ozelligi icin.
- Analiz icin gonderilen foto/PDF: modele iletilir, uzun sure saklanmaz.
- Ses: goruntulu/sesli gorusme sirasinda modele akitilir, kaydedilmez.
- Isleyen ucuncu taraflar: Google (Gemini API + Gemini Live), Groq (arka
  plan hafiza cikarimi + yedek metin uretimi), ElevenLabs / self-host
  Chatterbox (seslendirme). Barindirma: Railway.
"""

_CSS = """
body{margin:0;background:#0b0c14;color:#e8e8ef;font-family:-apple-system,
Segoe UI,Roboto,system-ui,sans-serif;line-height:1.7}
.wrap{max-width:760px;margin:0 auto;padding:48px 22px 90px}
h1{font-size:1.7rem;margin:0 0 .2em}
h2{font-size:1.15rem;margin:2em 0 .4em;color:#c9c6ff}
p,li{color:#c3c4d0;font-size:.98rem}
a{color:#9c8fff}
.draft{background:#2a2012;border:1px solid #4a3a1a;color:#e0ac5b;
padding:12px 16px;border-radius:10px;font-size:.88rem;margin:1.4em 0}
.langbar{font-size:.85rem;margin-bottom:1.5em}
.langbar a{margin-right:14px}
.meta{color:#71768a;font-size:.82rem;border-top:1px solid #23252f;
margin-top:3em;padding-top:1.2em}
"""

_DOCS = {
    "privacy": {
        "tr": ("Gizlilik Politikası", """
<div class="draft">TASLAK — bu metin bir hukukçu tarafından incelenmemiştir.
Nihai sürüm yayından önce onaylanacaktır.</div>
<h2>1. Kimiz</h2>
<p>Aura, kişisel bir yapay zekâ arkadaş uygulamasıdır. Bu politikada
"biz" ifadesi uygulamayı işleten [ŞİRKET/KİŞİ UNVANI]'nı belirtir. İletişim:
[E-POSTA ADRESİ].</p>
<h2>2. Hangi verileri işliyoruz</h2>
<ul>
<li><b>Hesap:</b> Hesabını kaydedersen e‑posta adresin ve şifrenin
şifrelenmiş (hash) hâli; adın.</li>
<li><b>Sohbet:</b> Aura'ya yazdığın mesajlar ve Aura'nın yanıtları.</li>
<li><b>Hafıza:</b> Sohbetlerinden çıkarılan, seni tanımaya yarayan bilgiler
(örn. mesleğin, ilgi alanların). Bunları Ayarlar > Hafızam'dan görebilir ve
silebilirsin.</li>
<li><b>Ruh hâli ve hatırlatmalar:</b> Mesajlarından çıkarılan ruh hâli
sinyalleri ve tarih içeren hatırlatmalar.</li>
<li><b>Kullanım:</b> Günlük mesaj/görüşme sayaçları; uygulama içi
tercihlerin.</li>
<li><b>Konum (isteğe bağlı):</b> Hava durumuna duyarlı öneriler için
yaklaşık konumun. İzin vermezsen kullanılmaz.</li>
<li><b>Fotoğraf/PDF:</b> İncelenmesi için gönderdiğin dosyalar analiz için
yapay zekâ modeline iletilir; sunucumuzda uzun süre saklanmaz.</li>
<li><b>Ses:</b> Sesli/görüntülü görüşme sırasında sesin gerçek zamanlı
olarak modele aktarılır; ses kaydı tutulmaz.</li>
</ul>
<h2>3. Neden işliyoruz</h2>
<p>Sohbeti yürütmek, seni zamanla tanıyıp tutarlı bir arkadaş gibi
davranabilmek, güvenlik (kriz durumlarında doğru yönlendirme), kötüye
kullanımı önlemek ve hizmeti geliştirmek için.</p>
<h2>4. Kimlerle paylaşıyoruz</h2>
<p>Verilerini satmıyoruz. Yapay zekâ yanıtlarını üretmek için hizmet
sağlayıcı olarak şu taraflarla çalışıyoruz: <b>Google</b> (Gemini),
<b>Groq</b> (arka plan işlemleri), seslendirme için <b>ElevenLabs</b> veya
kendi barındırdığımız ses motoru. Barındırma: <b>Railway</b>. Bu sağlayıcılar
verini yalnızca hizmeti sunmak için işler.</p>
<h2>5. Ne kadar saklıyoruz</h2>
<p>Sohbet geçmişin ve hafızan, sen silene ya da hesabını kapatana kadar
saklanır. Hesabını sildiğinde tüm verilerin kalıcı olarak silinir.
[SAKLAMA SÜRESİ DETAYI — hukuk incelemesinde netleştirilecek.]</p>
<h2>6. Haklarını nasıl kullanırsın</h2>
<p>KVKK md. 11 ve ilgili mevzuat uyarınca verilerine erişme, düzeltme,
silme ve işlenmesine itiraz etme hakkın var. Uygulama içinden:
Ayarlar > Hafızam (hafıza silme), Ayarlar > Çıkış, ve <b>hesap silme</b>
seçenekleriyle bunların çoğunu doğrudan yapabilirsin. Diğer talepler için:
[E‑POSTA ADRESİ].</p>
<h2>7. Güvenlik</h2>
<p>Şifreler hash'lenerek saklanır. Bağlantılar şifrelidir (HTTPS). Gizli
mod'da işaretlediğin sohbetler normal geçmişte görünmez.</p>
<h2>8. Çocuklar</h2>
<p>Aura 18 yaş ve üzeri kullanıcılar içindir. 18 yaşından küçüksen
uygulamayı kullanma.</p>
<h2>9. Değişiklikler</h2>
<p>Bu politikayı güncelleyebiliriz; önemli değişiklikleri uygulama içinde
bildiririz.</p>
"""),
        "en": ("Privacy Policy", """
<div class="draft">DRAFT — this text has not been reviewed by a lawyer. A
final version will be approved before public launch.</div>
<h2>1. Who we are</h2>
<p>Aura is a personal AI companion app. "We" refers to [COMPANY/OPERATOR
NAME]. Contact: [EMAIL].</p>
<h2>2. What we process</h2>
<ul>
<li><b>Account:</b> If you save an account, your email and a hashed form of
your password; your name.</li>
<li><b>Chat:</b> Messages you send Aura and Aura's replies.</li>
<li><b>Memory:</b> Facts extracted from your chats to help Aura know you
(e.g. your profession, interests). Viewable and deletable in
Settings &gt; My Memory.</li>
<li><b>Mood &amp; reminders:</b> Mood signals inferred from messages and
date‑based reminders parsed from them.</li>
<li><b>Usage:</b> Daily message/call counters; in‑app preferences.</li>
<li><b>Location (optional):</b> Approximate location for weather‑aware
suggestions. Not used without permission.</li>
<li><b>Photos/PDFs:</b> Files you send for review are forwarded to the AI
model for analysis; not retained long‑term on our server.</li>
<li><b>Voice:</b> During voice/video calls your audio is streamed to the
model in real time; no recording is kept.</li>
</ul>
<h2>3. Why</h2>
<p>To run the conversation, to remember you over time and behave like a
consistent companion, for safety (correct signposting in crisis), to
prevent abuse, and to improve the service.</p>
<h2>4. Who we share with</h2>
<p>We do not sell your data. To generate AI responses we use these
processors: <b>Google</b> (Gemini), <b>Groq</b> (background tasks),
<b>ElevenLabs</b> or our self‑hosted voice engine for speech. Hosting:
<b>Railway</b>. They process your data only to provide the service.</p>
<h2>5. Retention</h2>
<p>Your chat history and memory are kept until you delete them or close your
account. Deleting your account permanently erases your data.
[RETENTION DETAIL — to be finalised in legal review.]</p>
<h2>6. Your rights</h2>
<p>Under GDPR / Turkish KVKK you can access, rectify, erase and object to
processing. In‑app: Settings &gt; My Memory (delete memories),
Settings &gt; Log out, and <b>delete account</b>. Other requests:
[EMAIL].</p>
<h2>7. Security</h2>
<p>Passwords are stored hashed. Connections are encrypted (HTTPS). Chats you
mark as hidden do not appear in normal history.</p>
<h2>8. Children</h2>
<p>Aura is for users aged 18 and over. Do not use the app if you are under
18.</p>
<h2>9. Changes</h2>
<p>We may update this policy; we will notify significant changes in‑app.</p>
"""),
    },
    "terms": {
        "tr": ("Kullanım Şartları", """
<div class="draft">TASLAK — bir hukukçu tarafından incelenmemiştir.</div>
<h2>1. Hizmet</h2>
<p>Aura, yapay zekâ ile sohbet eden kişisel bir arkadaş uygulamasıdır.
Bir insan, terapist, doktor, avukat ya da mali danışman DEĞİLDİR ve bunların
yerine geçmez.</p>
<h2>2. Yaş</h2>
<p>Uygulamayı kullanmak için 18 yaşında veya daha büyük olmalısın.</p>
<h2>3. Tıbbi / hukuki / finansal içerik</h2>
<p>Aura genel bilgi verebilir ama kişiye özel teşhis, ilaç/doz önerisi ya da
yatırım tavsiyesi vermez. Ciddi konularda bir uzmana danış. Acil bir
durumda (kendine/başkasına zarar riski) 112'yi ara veya en yakın acil
servise başvur.</p>
<h2>4. Kabul edilebilir kullanım</h2>
<p>Yasa dışı, zararlı, başkalarını aldatmaya/taciz etmeye yönelik ya da
sistemi kötüye kullanmaya (jailbreak, otomatik kötüye kullanım) yönelik
kullanım yasaktır. Aura bu tür istekleri reddeder.</p>
<h2>5. İçerik</h2>
<p>Yazdıkların sana aittir. Uygulamayı çalıştırmak için bu içeriği işlememize
izin vermiş olursun (bkz. Gizlilik Politikası).</p>
<h2>6. Hizmetin sunumu</h2>
<p>Hizmet "olduğu gibi" sunulur. Kesintisiz veya hatasız olacağını garanti
etmeyiz. Ücretsiz kullanım için günlük sınırlar uygulanabilir.</p>
<h2>7. Sorumluluğun sınırı</h2>
<p>Yürürlükteki hukukun izin verdiği ölçüde, Aura'nın verdiği yanıtlara
dayanarak aldığın kararlardan doğan zararlardan sorumlu değiliz.
[SORUMLULUK SINIRI — hukuk incelemesinde netleştirilecek.]</p>
<h2>8. Fesih</h2>
<p>Hesabını istediğin zaman silebilirsin. Şartları ihlal eden hesapları
askıya alabilir veya kapatabiliriz.</p>
<h2>9. Uygulanacak hukuk</h2>
<p>[YETKİLİ HUKUK VE MAHKEME — doldurulacak.]</p>
"""),
        "en": ("Terms of Use", """
<div class="draft">DRAFT — not reviewed by a lawyer.</div>
<h2>1. The service</h2>
<p>Aura is a personal AI companion app for conversation. It is NOT a human,
therapist, doctor, lawyer or financial adviser and is not a substitute for
one.</p>
<h2>2. Age</h2>
<p>You must be 18 or older to use the app.</p>
<h2>3. Medical / legal / financial content</h2>
<p>Aura may give general information but does not provide personal diagnosis,
medication/dosage advice or investment advice. Consult a professional for
serious matters. In an emergency (risk of harm to self or others) call your
local emergency number or go to the nearest emergency department.</p>
<h2>4. Acceptable use</h2>
<p>Illegal, harmful, deceptive/harassing use, or attempts to abuse the system
(jailbreak, automated abuse) are prohibited. Aura refuses such requests.</p>
<h2>5. Content</h2>
<p>What you write is yours. You grant us permission to process it to run the
app (see Privacy Policy).</p>
<h2>6. Availability</h2>
<p>The service is provided "as is". We do not guarantee it will be
uninterrupted or error‑free. Daily limits may apply to free use.</p>
<h2>7. Limitation of liability</h2>
<p>To the extent permitted by applicable law, we are not liable for decisions
you make relying on Aura's responses.
[LIABILITY CAP — to be finalised in legal review.]</p>
<h2>8. Termination</h2>
<p>You can delete your account at any time. We may suspend or close accounts
that breach these terms.</p>
<h2>9. Governing law</h2>
<p>[GOVERNING LAW AND JURISDICTION — to be filled in.]</p>
"""),
    },
    "kvkk": {
        "tr": ("KVKK Aydınlatma Metni", """
<div class="draft">TASLAK — 6698 sayılı KVKK kapsamında hazırlanmış olup
bir hukukçu tarafından incelenmemiştir.</div>
<h2>Veri Sorumlusu</h2>
<p>[ŞİRKET/KİŞİ UNVANI], [ADRES]. İletişim: [E‑POSTA].</p>
<h2>İşlenen Kişisel Veriler</h2>
<p>Kimlik (ad), iletişim (e‑posta), işlem güvenliği (şifre hash'i, oturum),
kullanıcı içerikleri (sohbet mesajları, gönderilen fotoğraf/PDF), çıkarılan
profil bilgileri (hafıza kayıtları, ruh hâli, hatırlatmalar, üslup vektörü),
kullanım verileri ve isteğe bağlı konum.</p>
<h2>İşleme Amaçları</h2>
<p>Hizmetin sunulması ve sürdürülmesi; kullanıcıyı tanıyarak kişiselleştirme;
kullanıcı güvenliği ve kriz durumlarında yönlendirme; kötüye kullanımın
önlenmesi; hizmetin iyileştirilmesi; hukuki yükümlülüklerin yerine
getirilmesi.</p>
<h2>Hukuki Sebepler</h2>
<p>Sözleşmenin kurulması/ifası (md. 5/2‑c), meşru menfaat (md. 5/2‑f) ve
açık rıza (konum ve isteğe bağlı özellikler için).</p>
<h2>Aktarım</h2>
<p>Veriler, yapay zekâ yanıtlarının üretilmesi ve barındırma amacıyla yurt
dışındaki hizmet sağlayıcılara (Google, Groq, ElevenLabs, Railway)
aktarılabilir. Bu aktarım, hizmetin teknik olarak sunulabilmesi için
zorunludur ve KVKK md. 9 çerçevesinde yapılır.</p>
<h2>Haklarınız (md. 11)</h2>
<p>Kişisel verilerinizin işlenip işlenmediğini öğrenme, bilgi talep etme,
amacına uygun kullanılıp kullanılmadığını öğrenme, düzeltilmesini veya
silinmesini isteme, aktarıldığı üçüncü kişileri bilme ve zararın
giderilmesini talep etme haklarına sahipsiniz. Başvuru: [E‑POSTA].</p>
"""),
        "en": ("Data Processing Notice (KVKK/GDPR)", """
<div class="draft">DRAFT — prepared under Turkish KVKK (Law 6698) / GDPR
principles; not reviewed by a lawyer.</div>
<h2>Data controller</h2>
<p>[COMPANY/OPERATOR NAME], [ADDRESS]. Contact: [EMAIL].</p>
<h2>Personal data processed</h2>
<p>Identity (name), contact (email), transaction security (password hash,
session), user content (chat messages, submitted photos/PDFs), derived
profile data (memory records, mood, reminders, style vector), usage data,
and optional location.</p>
<h2>Purposes</h2>
<p>Providing and maintaining the service; personalisation by getting to know
the user; user safety and crisis signposting; abuse prevention; service
improvement; meeting legal obligations.</p>
<h2>Legal bases</h2>
<p>Performance of a contract, legitimate interest, and explicit consent (for
location and optional features).</p>
<h2>Transfers</h2>
<p>Data may be transferred to service providers outside your country (Google,
Groq, ElevenLabs, Railway) for AI response generation and hosting. This is
necessary to deliver the service technically.</p>
<h2>Your rights</h2>
<p>You may ask whether your data is processed, request information, ask for
correction or erasure, learn the third parties it is shared with, and
request remedy for damage. Requests: [EMAIL].</p>
"""),
    },
}

_DOC_ALIASES = {"gizlilik": "privacy", "sartlar": "terms", "terms-of-use": "terms"}


def render(doc: str, lang: str = "tr") -> str:
    doc = _DOC_ALIASES.get(doc, doc)
    lang = "en" if lang == "en" else "tr"
    entry = _DOCS.get(doc)
    if not entry:
        return "<h1>404</h1>"
    title, body = entry[lang]
    other = "en" if lang == "tr" else "tr"
    other_label = "English" if lang == "tr" else "Türkçe"
    updated = "2026-09-06"
    foot_tr = ("Bu bir taslaktır ve yayından önce hukuki incelemeden "
               "geçirilecektir. Son güncelleme: ")
    foot_en = ("This is a draft and will undergo legal review before public "
               "launch. Last updated: ")
    foot = (foot_en if lang == "en" else foot_tr) + updated
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Aura</title><style>{_CSS}</style></head><body><div class="wrap">
<div class="langbar"><a href="?lang={other}">{other_label}</a></div>
<h1>{title}</h1>{body}
<p class="meta">{foot}</p>
</div></body></html>"""
