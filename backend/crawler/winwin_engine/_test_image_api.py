"""서버의 /api/image 엔드포인트에 실제 요청을 보내서 이미지 로딩 여부를 확인"""
import urllib.request, json, urllib.parse

# API에서 상품 데이터 가져오기
resp = urllib.request.urlopen('http://localhost:8001/api/crawled_products', timeout=60)
data = json.loads(resp.read().decode())
products = data if isinstance(data, list) else data.get('products', data)

print(f"총 상품: {len(products)}개\n")

# 처음 3개 상품의 각 이미지 파일을 실제로 /api/image에 요청해서 HTTP 상태 확인
for idx in range(min(3, len(products))):
    p = products[idx]
    img_dir = p.get('local_image_dir', '')
    img_files = p.get('image_files', []) or []
    local_paths = p.get('local_image_paths', []) or []
    
    print(f"=== 상품 #{idx+1} ({len(img_files)}장) ===")
    print(f"  local_image_dir: [{img_dir}]")
    print(f"  dir 길이: {len(img_dir)}")
    print(f"  dir repr: {repr(img_dir[-40:])}")
    
    # 방법1: image_files[i] 기반 (dir + / + filename)
    for i, f in enumerate(img_files):
        path = img_dir + '/' + f
        url = f'http://localhost:8001/api/image?path={urllib.parse.quote(path)}'
        try:
            req = urllib.request.Request(url, method='HEAD')
            r = urllib.request.urlopen(req, timeout=5)
            status = r.status
            content_type = r.headers.get('content-type', '?')
        except urllib.error.HTTPError as e:
            status = e.code
            content_type = 'ERROR'
        except Exception as e:
            status = f'FAIL:{e}'
            content_type = ''
        ok = '✅' if status == 200 else '❌'
        print(f"  {ok} image_files[{i}]: {f} -> HTTP {status} ({content_type})")
    
    # 방법2: local_image_paths[i] 기반 (절대 경로 직접)
    if local_paths:
        print(f"  --- local_image_paths 방식 ---")
        for i, lp in enumerate(local_paths[:3]):
            url = f'http://localhost:8001/api/image?path={urllib.parse.quote(str(lp))}'
            try:
                req = urllib.request.Request(url, method='HEAD')
                r = urllib.request.urlopen(req, timeout=5)
                status = r.status
            except urllib.error.HTTPError as e:
                status = e.code
            except Exception as e:
                status = f'FAIL:{e}'
            ok = '✅' if status == 200 else '❌'
            print(f"  {ok} local_paths[{i}]: ...{str(lp)[-30:]} -> HTTP {status}")
    
    print()
