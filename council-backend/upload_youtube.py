"""
YouTube'a video yukler - ama GUVENLIK ICIN VARSAYILAN OLARAK HERKESE
ACIK YAPMAZ. Yuklenen video "private" olarak durur; herkese acik hale
getirmek AYRI bir adim (publish_youtube.py) ve HER SEFERINDE ayri bir
onay gerektirir - otomatik yukleme, otomatik yayinlama demek DEGIL.

On kosul: once youtube_auth.py calistirilmis olmali (bkz. YOUTUBE_SETUP.md).

Kullanim:
    python upload_youtube.py video.mp4 --title "..." --description "..." --tags "a,b,c"
"""
import argparse

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from youtube_auth import get_credentials


def upload_video(file_path, title, description, tags=None, privacy_status="private",
                 publish_at=None):
    """privacy_status: 'private' (varsayilan, guvenli), 'unlisted' veya
    'public'. 'public' HICBIR ZAMAN varsayilan olarak kullanilmamali -
    bu fonksiyonu 'public' ile cagirmadan once kullanicidan aciktan
    onay alinmis olmali.

    publish_at: ISO-8601 UTC (or. '2026-09-06T15:00:00Z'). Verilirse video
    'private' yuklenir ve o anda otomatik HERKESE ACIK olur - butun abonelere
    ayni anda bildirim gider ('koordineli dusum': ilk saatteki yorum hizi =
    algoritma sinyali, bos canli yayin riski YOK)."""
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    status = {"selfDeclaredMadeForKids": False}
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    else:
        status["privacyStatus"] = privacy_status

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "28",  # Science & Technology
        },
        "status": status,
    }

    def _yukle():
        # her denemede YENI oturum (410 'Gone' = eski resumable oturum gecersiz)
        media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            ilerleme, response = request.next_chunk()
            if ilerleme:
                print(f"Yukleniyor: %{int(ilerleme.progress() * 100)}")
        return response

    from yukleme_dene import dene
    response = dene(_yukle)
    video_id = response["id"]
    if publish_at:
        print(f"Yuklendi (ZAMANLANMIS -> {publish_at} otomatik herkese acik): "
              f"https://youtu.be/{video_id}")
    elif privacy_status == "public":
        print(f"Yuklendi (HERKESE ACIK): https://youtu.be/{video_id}")
    else:
        print(f"Yuklendi (privacyStatus={privacy_status}): https://youtu.be/{video_id}")
        print("Bu video henuz HERKESE ACIK DEGIL - yayinlamak icin: "
              f"python publish_youtube.py {video_id}")
    return video_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Yuklenecek video dosyasi")
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--tags", default="", help="virgulle ayrilmis etiketler")
    parser.add_argument(
        "--privacy", default="private", choices=["private", "unlisted", "public"],
        help="varsayilan 'private' - 'public' sadece bilerek/onayla kullanilmali",
    )
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    upload_video(args.file, args.title, args.description, tags, args.privacy)
