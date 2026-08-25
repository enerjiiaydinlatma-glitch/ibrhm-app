import sys
sys.stdout.reconfigure(errors='replace')
from googleapiclient.discovery import build
from youtube_auth import get_credentials
creds = get_credentials()
youtube = build('youtube', 'v3', credentials=creds)
video_ids = {
    'Baslangic videosu': 'bp57zSGJ1PE',
    'Teaser (5 AI Minds Debate)': 'YkACPpXWpmI',
    'Bolum 1 (2030 AI gelecegi)': 'vGud4rExTKE',
    'Bolum 2 (DARPA F-16)': 'U3sW9hvmEOE',
    'Bolum 3 (EU AI aciklama yasasi)': 'rfneSOt7WMI',
    'Short: Labeling a Bot': 'F4-b5h9RTYI',
    'Short: Hype Machine (Beta)': 'CV0T_E-9Qns',
    'Short: We Already Did': 'P-KPXl-zzCU',
    'Short: Kill Switch Is a Lie': 'JjqBWKASaWE',
    'Short: 2030 Humanity Trade': 'cdHdGwv9sow',
    'Short: Step Zero': 'yIeAPLg5zCQ',
    'Short: Mid-Air Control Dead': '2hzPSiYzIik',
    'Grok 2030 Uyarisi (Sentetik Ruyalar)': 'U8YnszwIntY',
    'Short: Not the Final Destination': '5o9xPKNb8Wg',
    'Short: Leaving Real Authority (Compute)': 'PTXAGyf1bzI',
    'Short: Mandatory AI Disclosure Standardization': 'NkbSPBKDJUg',
    'Short: Beta Tore Through Corporate Analysis': '37sVuOCO72k',
    'Short: Labeling a Bot Doesnt Stop It': 'txPX4uBzBro',
    'Short: UI Adjustments': 'KKahqLySSFs',
    'Short: EU Mandatory AI Disclosure': '5XUtyFwcTPA',
    'Short: Alpha vs Delta (Compute Authority)': 'dLZ6rHj719Q',
    'Short: Alpha vs Beta (Labeling a Bot)': 'DcqQ7F-sTvA',
}
v = youtube.videos().list(part='statistics,status', id=','.join(video_ids.values())).execute()
stats_by_id = {it['id']: it for it in v['items']}
for name, vid in video_ids.items():
    it = stats_by_id.get(vid, {})
    s = it.get('statistics', {})
    st = it.get('status', {})
    print(name, '-> izlenme:', s.get('viewCount'), 'begeni:', s.get('likeCount'), 'yorum:', s.get('commentCount'), 'durum:', st.get('privacyStatus'))
ch = youtube.channels().list(part='statistics', mine=True).execute()
print('Abone sayisi:', ch['items'][0]['statistics']['subscriberCount'])

# Ayrica en yeni videolari listele - takip listesinde olmayan yeni bir
# video/Short cikmis mi diye kontrol icin (baska bir oturum ekleyebilir).
r = youtube.search().list(part='snippet', forMine=True, type='video', order='date', maxResults=15).execute()
bilinen_idler = set(video_ids.values())
yeni = [it['id']['videoId'] + ' - ' + it['snippet']['title'] for it in r['items'] if it['id']['videoId'] not in bilinen_idler]
if yeni:
    print('YENI/TAKIP EDILMEYEN VIDEO(LAR) BULUNDU:', yeni)
