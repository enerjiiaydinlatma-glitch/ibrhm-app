"""
Aura Influencer - YouTube Data API v3 ile RESMI, tarayici otomasyonu OLMAYAN
yayinlama araci. publish_youtube.py (Selenium) denendi ve calismadi: Google,
webdriver ile kontrol edilen oturumlari otomasyon olarak tespit edip aninda
dusuruyor (--login basarili gorunse de saniyeler icinde "oturum kapatildi"
oluyor). Bu script onun yerine gecer - tarayici hic acilmaz, dogrudan
Google'in resmi API'siyle konusulur, bot-tespiti riski yoktur.

Ilk kurulum (bir kere, operatorun kendi Google hesabiyla, tarayicida NORMAL
bir onay ekrani - otomasyon degil):
    1. console.cloud.google.com'da bir proje ac, "YouTube Data API v3"u
       Enable et, OAuth istemci kimligi (Masaustu uygulamasi) olustur,
       client_secret.json'u indirip bu klasore (_studio/) koy.
    2. python publish_youtube_api.py --auth
       -> Tarayici acilir, Google hesabinla normal bir izin ekraninda onay
          verirsin (bu otomasyon degil, senin gercek tikladigin bir ekran).
          token.json bu klasore kaydedilir, bir dahaki calistirmada tekrar
          sormaz (refresh token ile kendini yeniler).

Gunluk kullanim:
    python publish_youtube_api.py --video output\\aura_day13_x.mp4 \\
        --title "AI Without the Friction" \\
        --description-file output\\day13_description.txt \\
        --tr-srt output\\day13_tr.srt
"""
import argparse
import os
import sys

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

HERE = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_FILE = os.path.join(HERE, "client_secret.json")
TOKEN_FILE = os.path.join(HERE, "token.json")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def get_authenticated_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET_FILE):
                sys.exit(
                    f"HATA: {CLIENT_SECRET_FILE} bulunamadi. Google Cloud Console'dan "
                    "OAuth istemci kimligi (Masaustu uygulamasi) indirip bu isimle "
                    "_studio/ klasorune koy, sonra --auth ile calistir."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, video_path, title, description, tags=None,
                  category_id="28", privacy="public"):
    video_path = os.path.abspath(video_path)
    if not os.path.exists(video_path):
        raise FileNotFoundError(video_path)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)

    print(f"Yukleniyor: '{title}' ({video_path})...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  %{int(status.progress() * 100)}")

    video_id = response["id"]
    print(f"YUKLENDI. Video ID: {video_id}")
    print(f"Link: https://youtu.be/{video_id}")
    return video_id


def add_turkish_caption(youtube, video_id, srt_path):
    srt_path = os.path.abspath(srt_path)
    if not os.path.exists(srt_path):
        print(f"  [uyari] SRT bulunamadi: {srt_path}")
        return
    print("Turkce CC ekleniyor...")
    media = MediaFileUpload(srt_path, mimetype="application/octet-stream")
    request = youtube.captions().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": video_id,
                "language": "tr",
                "name": "Türkçe",
                "isDraft": False,
            }
        },
        media_body=media,
    )
    try:
        response = request.execute()
        print(f"  Turkce CC eklendi (caption id: {response.get('id')})")
    except HttpError as e:
        print(f"  [uyari] Turkce CC eklenemedi: {e}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--auth", action="store_true", help="Ilk kurulum: OAuth izin ekranini ac, token.json uret")
    p.add_argument("--video", help="Yuklenecek .mp4 dosyasi")
    p.add_argument("--title", help="Video basligi")
    p.add_argument("--description", help="Aciklama metni (kisa ise)")
    p.add_argument("--description-file", help="Aciklama metnini bu dosyadan oku")
    p.add_argument("--tags", help="Virgulle ayrilmis etiketler")
    p.add_argument("--tr-srt", help="Turkce alt yazi .srt dosyasi (opsiyonel)")
    p.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    args = p.parse_args()

    if args.auth:
        get_authenticated_service()
        print("Yetkilendirme tamamlandi ->", TOKEN_FILE)
        sys.exit(0)

    if not args.video or not args.title:
        p.error("--video ve --title gerekli (veya --auth ile once yetkilendir)")

    desc = args.description or ""
    if args.description_file:
        with open(args.description_file, encoding="utf-8") as f:
            desc = f.read()
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else None

    yt = get_authenticated_service()
    vid = upload_video(yt, args.video, args.title, desc, tags=tags, privacy=args.privacy)
    if args.tr_srt:
        add_turkish_caption(yt, vid, args.tr_srt)
