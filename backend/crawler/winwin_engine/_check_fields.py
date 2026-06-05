import json, os, glob

db_files = glob.glob(r'c:\programing\윈윈크롤러2\backend\crawled_products*.json')
print(f"DB 파일 수: {len(db_files)}")
for f in db_files:
    print(f"  {os.path.basename(f)}: {os.path.getsize(f):,} bytes")

if db_files:
    target = max(db_files, key=os.path.getsize)
    with open(target, 'r', encoding='utf-8') as f:
        data = json.load(f)
    products = data if isinstance(data, list) else data.get('products', [])
    print(f"\n총 상품: {len(products)}개")
    if products:
        p = products[0]
        print(f"필드 키: {sorted(p.keys())}")
        
        img_files = p.get('image_files', []) or []
        img_urls = p.get('image_urls', []) or []
        local_paths = p.get('local_image_paths', []) or []
        
        print(f"image_files: {len(img_files)}개 -> {img_files[:2]}")
        print(f"image_urls: {len(img_urls)}개")
        print(f"local_image_paths: {len(local_paths)}개")
        print(f"local_image_dir: {p.get('local_image_dir', 'NONE')}")
        print(f"price_input: [{p.get('price_input', 'NONE')}]")
        print(f"sale_price: [{p.get('sale_price', 'NONE')}]")
        print(f"price_detected: {p.get('price_detected', 'NONE')}")
        
        no_price = sum(1 for pp in products if not pp.get('price_input') or str(pp.get('price_input', '')) in ('-', '0', ''))
        print(f"\n가격 없는 상품: {no_price}/{len(products)} ({no_price/len(products)*100:.0f}%)")
        
        has_files = sum(1 for pp in products if pp.get('image_files'))
        has_urls = sum(1 for pp in products if pp.get('image_urls'))
        has_local = sum(1 for pp in products if pp.get('local_image_paths'))
        print(f"image_files 있음: {has_files}")
        print(f"image_urls 있음: {has_urls}")
        print(f"local_image_paths 있음: {has_local}")
