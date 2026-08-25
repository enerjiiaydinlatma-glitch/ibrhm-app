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


def upload_video(file_path, title, description, tags=None, privacy_status="private"):
    """privacy_status: 'private' (varsayilan, guvenli), 'unlisted' veya
    'public'. 'public' HICBIR ZAMAN varsayilan olarak kullanilmamali -
    bu fonksiyonu 'public' ile cagirmadan once kullanicidan aciktan
    onay alinmis olmali."""
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "28",  # Science & Technology
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Yukleniyor: %{int(status.progress() * 100)}")

    video_id = response["id"]
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
