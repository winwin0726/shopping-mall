import urllib.request
import json
import re

url = 'http://127.0.0.1:8001/api/logs'
try:
    data = json.loads(urllib.request.urlopen(url).read().decode('utf-8'))
    for log in data['logs']:
        if 'http' in log or 'URL' in log or 'theme_detail' in log or 'shop_detail' in log or '남신19' in log:
            try:
                print(log.encode('utf-8', errors='ignore').decode('utf-8'))
            except:
                pass
except Exception as e:
    print(e)
