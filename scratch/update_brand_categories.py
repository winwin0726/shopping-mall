# -*- coding: utf-8 -*-
import sqlite3
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "sql_app.db")

print(f"Connecting to DB for seeding brand categories: {_DB_PATH}")

# 브랜드 카테고리 매핑 정의
# slug 기준으로 매핑합니다.
brand_mappings = {
    # 1. 종합 명품 브랜드 (기본 all)
    "chanel": "all",
    "louis-vuitton": "all",
    "gucci": "all",
    "prada": "all",
    "hermes": "all",
    "dior": "all",
    "bottega-veneta": "all",
    "miu-miu": "all",
    "balenciaga": "all",
    "saint-laurent": "all",
    "fendi": "all",
    "burberry": "all",
    "goyard": "all",
    "loewe": "all",

    # 2. 가방/지갑 전문 브랜드
    "celine": "bag,wallet",
    "chloe": "bag,wallet",
    "givenchy": "bag,wallet",
    "the-row": "bag,wallet",
    "loro-piana": "bag,wallet",
    "maison-margiela": "bag,wallet",
    "delvaux": "bag,wallet",
    "alaia": "bag,wallet",

    # 3. 신발 전문 브랜드 (+의류 하이브리드 포함)
    "valentino": "shoes",
    "dolce-gabbana": "shoes",
    "christian-louboutin": "shoes",
    "golden-goose": "shoes",
    "marc-jacobs": "shoes",
    "isabel-marant": "shoes",
    "lanvin": "shoes",
    "bally": "shoes",
    "ugg": "shoes",
    "giuseppe-zanotti": "shoes",
    "john-lobb": "shoes",
    "thom-browne": "shoes,clothing",
    "boss": "shoes",
    "alexander-wang": "shoes",
    "tods": "shoes",
    "dsquared2": "shoes",
    "ferragamo": "shoes,wallet",
    "zegna": "shoes",
    "roger-vivier": "shoes",
    "moncler": "shoes,clothing",
    "philipp-plein": "shoes",
    "armani": "shoes,clothing",

    # 4. 시계 전문 및 하이브리드 브랜드
    "audemars-piguet": "watch",
    "bell-ross": "watch",
    "blancpain": "watch",
    "breguet": "watch",
    "breitling": "watch",
    "bvlgari": "watch,accessory",
    "cartier": "watch,accessory",
    "chopard": "watch",
    "franck-muller": "watch",
    "hublot": "watch",
    "iwc": "watch",
    "jaeger-lecoultre": "watch",
    "longines": "watch",
    "montblanc": "watch,wallet,accessory",
    "panerai": "watch",
    "omega": "watch",
    "patek-pilippe": "watch",
    "piaget": "watch",
    "roger-dubuis": "watch",
    "rolex": "watch",
    "tag-heuer": "watch",
    "ulysse-nardin": "watch",
    "vacheron-constantin": "watch",
}

try:
    conn = sqlite3.connect(_DB_PATH)
    cursor = conn.cursor()
    
    updated_count = 0
    not_found_count = 0
    
    for slug, cat_group in brand_mappings.items():
        # 존재 여부 확인
        cursor.execute("SELECT id, name FROM brands WHERE slug = ?", (slug,))
        row = cursor.fetchone()
        
        if row:
            brand_id, name = row
            cursor.execute("UPDATE brands SET category_group = ? WHERE id = ?", (cat_group, brand_id))
            print(f"  └ Updated brand: {name} (slug: {slug}) -> category_group: {cat_group}")
            updated_count += 1
        else:
            print(f"  ⚠️ Brand not found for slug: {slug}")
            not_found_count += 1
            
    conn.commit()
    print(f"\n[SUCCESS] Brand categories mapping complete. Updated: {updated_count}, Not Found: {not_found_count}")
    
    # 미매핑 상태로 남아있는 활성 브랜드가 있는지 확인
    cursor.execute("SELECT name, slug, category_group FROM brands WHERE is_active = 1")
    all_brands = cursor.fetchall()
    print("\n=== Current Brands Mapping Result ===")
    for b_name, b_slug, b_group in all_brands:
        try:
            print(f"Name: {b_name} | Slug: {b_slug} | Group: {b_group}")
        except UnicodeEncodeError:
            print(f"Name: (Unicode Error) | Slug: {b_slug} | Group: {b_group}")
        
except Exception as e:
    print(f"[ERROR] Database error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
