import urllib.request, json

resp = urllib.request.urlopen('http://localhost:8001/api/collected_products', timeout=10)
data = json.loads(resp.read().decode())
products = data.get('products', [])
print(f"총 상품 수: {len(products)}")

if products:
    p = products[0]
    imgs = p.get('image_urls', []) or p.get('image_files', [])
    print(f"첫 상품 이미지 수: {len(imgs)}")
    for img in imgs[:3]:
        print(f"  IMG: {str(img)[:120]}")
    
    thumb = p.get('thumbnail', '')
    first_img = p.get('first_image', '')
    print(f"thumbnail: {str(thumb)[:120]}")
    print(f"first_image: {str(first_img)[:120]}")
    
    # 이미지가 로컬 파일인지 URL인지 확인
    if imgs:
        sample = str(imgs[0])
        if sample.startswith('http'):
            print("이미지 타입: 외부 URL")
        elif sample.startswith('/') or sample.startswith('C:'):
            print("이미지 타입: 로컬 파일 경로")
        else:
            print(f"이미지 타입: 알 수 없음 ({sample[:50]})")
