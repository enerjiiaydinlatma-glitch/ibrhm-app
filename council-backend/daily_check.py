"""Gunluk kontrol + kendini degerlendirme raporu.

Calistir:  python daily_check.py
- Bugun kac video yuklendi? (gunluk sinir: DAILY_LIMIT)
- Son videolarin izlenme/begeni/yorum + yasa gore saatlik hiz
- Gecmis kaydi daily_history.jsonl'e eklenir (gun gun karsilastirma icin)
Sadece okur; yukleme yapmaz, kilitlere dokunmaz.
"""
import sys
import json
import datetime as dt
from pathlib import Path

sys.stdout.reconfigure(errors='replace')
from googleapiclient.discovery import build
from youtube_auth import get_credentials

DAILY_LIMIT = 2
LOOKBACK = 25
HISTORY = Path(__file__).with_name('daily_history.jsonl')


def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))


def main():
    yt = build('youtube', 'v3', credentials=get_credentials())
    ch = yt.channels().list(part='statistics,contentDetails', mine=True).execute()['items'][0]
    uploads = ch['contentDetails']['relatedPlaylists']['uploads']
    subs = int(ch['statistics']['subscriberCount'])

    pl = yt.playlistItems().list(part='contentDetails', playlistId=uploads,
                                 maxResults=LOOKBACK).execute()
    ids = [i['contentDetails']['videoId'] for i in pl['items']]
    vids = yt.videos().list(part='snippet,statistics,status', id=','.join(ids)).execute()['items']

    now = dt.datetime.now(dt.timezone.utc)
    today = dt.datetime.now().astimezone().date()
    rows = []
    for v in vids:
        pub = parse_ts(v['snippet']['publishedAt'])
        age_h = max((now - pub).total_seconds() / 3600, 0.5)
        s = v['statistics']
        views = int(s.get('viewCount', 0))
        rows.append({
            'id': v['id'], 'title': v['snippet']['title'],
            'published': pub.isoformat(), 'views': views,
            'likes': int(s.get('likeCount', 0)), 'comments': int(s.get('commentCount', 0)),
            'age_h': round(age_h, 1), 'views_per_h': round(views / age_h, 2),
            'privacy': v['status']['privacyStatus'],
        })
    rows.sort(key=lambda r: r['published'], reverse=True)

    today_n = sum(1 for r in rows if parse_ts(r['published']).astimezone().date() == today)
    print(f'=== {today}  abone: {subs} ===')
    print(f'Bugun yuklenen: {today_n}/{DAILY_LIMIT}',
          '(LIMIT DOLU)' if today_n >= DAILY_LIMIT else '(slot var)')
    if today_n > DAILY_LIMIT:
        print('UYARI: gunluk sinir asildi - kilidi kontrol et!')

    print('\nSon videolar (yeniden eskiye):')
    for r in rows[:10]:
        print(f"  {r['published'][:16]}  {r['views']:>5} izl  {r['likes']:>3} beg  "
              f"{r['comments']:>2} yor  {r['views_per_h']:>6}/saat  {r['title'][:60]}")

    done = [r for r in rows if r['age_h'] >= 24]
    if done:
        avg = sum(r['views'] for r in done) / len(done)
        best = max(done, key=lambda r: r['views_per_h'])
        worst = min(done, key=lambda r: r['views_per_h'])
        print(f'\n24s+ videolarda ortalama izlenme: {avg:.1f}')
        print(f"En iyi hiz : {best['views_per_h']}/saat - {best['title'][:60]}")
        print(f"En zayif   : {worst['views_per_h']}/saat - {worst['title'][:60]}")
        print('-> Yeni videonun basligini/hook\'unu en iyi 3 videonun ortak noktasina gore sec.')

    with HISTORY.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'date': str(today), 'subs': subs, 'today_uploads': today_n,
                            'videos': rows[:10]}, ensure_ascii=False) + '\n')
    print(f'\nKayit eklendi: {HISTORY.name}')


if __name__ == '__main__':
    main()
