"""
YouTube kanalina yukleme izni icin TEK SEFERLIK yetkilendirme.

Bu script'i SIZ calistirip Google hesabinizla ("Sign Council kanalinin
bagli oldugu hesap") tarayicidan onay vermeniz gerekiyor - bu adimi
Claude sizin adiniza yapamaz. Onay verdikten sonra bir yenileme
anahtari (youtube_token.json) diskte saklanir, bundan sonraki
yuklemeler bu dosyayi kullanir, tekrar giris istemez.

On kosul (YOUTUBE_SETUP.md'de detayli):
1. Google Cloud Console'da bir proje acin, "YouTube Data API v3"u
   etkinlestirin.
2. Bir OAuth Client ID (tur: Desktop app) olusturun, indirin, bu
   dosyayla ayni dizine "client_secret.json" adiyla koyun.
3. Bu script'i calistirin: python youtube_auth.py

Kullanim:
    python youtube_auth.py
"""
import os

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    # Yorum yazma/duzenleme icin ayrica bu kapsam gerekiyor - "youtube"
    # kapsaminin kapsamadigi tek sey bu.
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

CLIENT_SECRET_PATH = os.path.join(os.path.dirname(__file__), "client_secret.json")
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "youtube_token.json")


def get_credentials():
    """Var olan bir token varsa onu (gerekirse yenileyerek) kullanir;
    yoksa tarayici acip tek seferlik onay ister."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        return creds

    if not os.path.exists(CLIENT_SECRET_PATH):
        raise RuntimeError(
            "client_secret.json bulunamadi - once YOUTUBE_SETUP.md'deki "
            "adimlari tamamlayip Google Cloud Console'dan indirdiginiz "
            "dosyayi council-backend/client_secret.json olarak kaydedin."
        )

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
    # open_browser=False: bu ortamda otomatik tarayici acma sessizce
    # basarisiz oluyordu - bunun yerine URL'yi basip kullaniciya
    # kendi tarayicisinda actiriyoruz. Yerel sunucu (localhost:port)
    # ayni makinede calistigi icin geri donus (redirect) yine calisir.
    creds = flow.run_local_server(port=0, open_browser=False)

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    return creds


if __name__ == "__main__":
    get_credentials()
    print(f"Yetkilendirme tamamlandi -> {TOKEN_PATH}")
    print("Artik upload_youtube.py bu dosyayi kullanarak yukleme yapabilir.")
