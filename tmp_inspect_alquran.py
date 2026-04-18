import urllib.request
import json
url = 'https://api.alquran.cloud/v1/quran/quran-uthmani'
with urllib.request.urlopen(url, timeout=30) as resp:
    print(resp.status)
    print(resp.getheader('content-type'))
    text = resp.read(1200).decode('utf-8')
    print(text[:1200])
    data = json.loads(text)
    print(type(data), list(data.keys())[:10])
    print(type(data['data']), list(data['data'].keys())[:20])
