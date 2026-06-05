"""실제 상품 데이터의 이미지 필드를 세포 단위로 분석"""
import json, os, urllib.request

# API에서 직접 데이터 가져오기 (타임아웃 길게)
try:
    req = urllib.request.Request('http://localhost:8001/api/crawled_products')
    resp = urllib.request.urlopen(req, timeout=60)
    raw = resp.read().decode('utf-8')
    data = json.loads(raw)
    products = data if isinstance(data, list) else data.get('products', data)
except Exception as e:
    print(f"API 실패: {e}")
    products = []

if not products:
    print("상품 데이터 없음")
    exit()

print(f"총 상품: {len(products)}개\n")

# 처음 5개 상품의 이미지 필드 상세 분석
for idx in range(min(5, len(products))):
    p = products[idx]
    print(f"{'='*60}")
    print(f"상품 #{idx+1}: {(p.get('title','') or '')[:30]}")
    print(f"  vendor_name: {p.get('vendor_name','NONE')}")
    
    img_files = p.get('image_files', []) or []
    img_urls = p.get('image_urls', []) or []
    local_paths = p.get('local_image_paths', []) or []
    local_dir = p.get('local_image_dir', '')
    
    print(f"  image_files: {len(img_files)}개")
    print(f"  image_urls: {len(img_urls)}개")
    print(f"  local_image_paths: {len(local_paths)}개")
    print(f"  local_image_dir: [{local_dir}]")
    
    # image_files 샘플
    if img_files:
        for i, f in enumerate(img_files[:3]):
            print(f"    image_files[{i}]: {f}")
            # 실제 파일 존재 확인
            if local_dir:
                full_path = os.path.join(local_dir, f)
                exists = os.path.isfile(full_path)
                print(f"      경로: {full_path}")
                print(f"      존재: {exists}")
        if len(img_files) > 3:
            print(f"    ... 외 {len(img_files)-3}개")
    
    # image_urls 샘플
    if img_urls:
        for i, u in enumerate(img_urls[:2]):
            print(f"    image_urls[{i}]: {str(u)[:80]}")
    
    # local_image_paths 샘플
    if local_paths:
        for i, lp in enumerate(local_paths[:2]):
            print(f"    local_image_paths[{i}]: {str(lp)[:80]}")
            exists = os.path.isfile(str(lp))
            print(f"      존재: {exists}")
    
    print()

# 전체 통계
print(f"{'='*60}")
print(f"=== 전체 통계 ===")
has_dir = sum(1 for p in products if p.get('local_image_dir'))
has_files = sum(1 for p in products if p.get('image_files'))
has_urls = sum(1 for p in products if p.get('image_urls'))
has_local = sum(1 for p in products if p.get('local_image_paths'))
empty_dir = sum(1 for p in products if p.get('image_files') and not p.get('local_image_dir'))
print(f"local_image_dir 있음: {has_dir}/{len(products)}")
print(f"image_files 있음: {has_files}/{len(products)}")
print(f"image_urls 있음: {has_urls}/{len(products)}")
print(f"local_image_paths 있음: {has_local}/{len(products)}")
print(f"image_files는 있지만 local_image_dir 없음: {empty_dir}/{len(products)}")
