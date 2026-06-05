"""GET 방식으로 이미지 API 테스트"""
import urllib.request, json, urllib.parse

resp = urllib.request.urlopen('http://localhost:8001/api/crawled_products', timeout=60)
data = json.loads(resp.read().decode())
products = data if isinstance(data, list) else data.get('products', data)

# 처음 2개 상품, 각 2장만 GET으로 테스트
for idx in range(2):
    p = products[idx]
    img_dir = p.get('local_image_dir', '')
    img_files = p.get('image_files', []) or []
    
    print(f"=== 상품 #{idx+1} ===")
    print(f"  dir: {img_dir}")
    
    for i, f in enumerate(img_files[:3]):
        path = img_dir + '/' + f
        encoded = urllib.parse.quote(path, safe='')
        url = f'http://localhost:8001/api/image?path={encoded}'
        print(f"  [{i}] GET URL: ...{url[-80:]}")
        try:
            r = urllib.request.urlopen(url, timeout=5)
            ct = r.headers.get('content-type', '?')
            cl = r.headers.get('content-length', '?')
            print(f"      => HTTP {r.status}, type={ct}, size={cl}")
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')[:200]
            print(f"      => HTTP {e.code}: {body}")
        except Exception as e:
            print(f"      => FAIL: {e}")
    
    # local_image_paths 방식도 테스트
    local_paths = p.get('local_image_paths', []) or []
    if local_paths:
        lp = local_paths[0]
        encoded = urllib.parse.quote(str(lp), safe='')
        url = f'http://localhost:8001/api/image?path={encoded}'
        print(f"  [local_path] GET URL: ...{url[-80:]}")
        try:
            r = urllib.request.urlopen(url, timeout=5)
            print(f"      => HTTP {r.status}, size={r.headers.get('content-length','?')}")
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')[:200]
            print(f"      => HTTP {e.code}: {body}")
    print()
