"""
Zaten yuklenmis (private/unlisted) bir videoyu HERKESE ACIK yapar.

Bu, kasitli olarak upload_youtube.py'den AYRI bir script - yukleme ile
yayinlama arasina bilincli bir durak koymak icin. Claude bu script'i
sizin acik onayiniz olmadan calistirmaz.

Kullanim:
    python publish_youtube.py VIDEO_ID
"""
import argparse

from googleapiclient.discovery import build

from youtube_auth import get_credentials


def publish_video(video_id):
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    youtube.videos().update(
        part="status",
        body={"id": video_id, "status": {"privacyStatus": "public"}},
    ).execute()

    print(f"Yayinlandi: https://youtu.be/{video_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id")
    args = parser.parse_args()
    publish_video(args.video_id)
