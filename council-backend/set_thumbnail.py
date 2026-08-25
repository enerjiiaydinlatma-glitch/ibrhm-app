"""
Var olan bir videoya kucuk resim (thumbnail) baglar.

Kullanim:
    python set_thumbnail.py VIDEO_ID assets/thumbnails/bolum_3.png
"""
import argparse

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from youtube_auth import get_credentials


def set_thumbnail(video_id, image_path):
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)
    media = MediaFileUpload(image_path, mimetype="image/png")
    youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
    print(f"Thumbnail baglandi -> https://youtu.be/{video_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id")
    parser.add_argument("image_path")
    args = parser.parse_args()
    set_thumbnail(args.video_id, args.image_path)
