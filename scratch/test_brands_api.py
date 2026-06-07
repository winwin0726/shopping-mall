# -*- coding: utf-8 -*-
import os
import sys

# 프로젝트 루트를 path에 추가하여 backend 임포트가 가능하게 설정
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_BASE_DIR)

from fastapi.testclient import TestClient
from backend.main import app

def test_api():
    client = TestClient(app)
    
    # 1. 카테고리 필터가 없는 전체 브랜드 조회
    res_all = client.get("/api/products/brands")
    all_data = res_all.json()
    print(f"[1] No filter: returned {len(all_data)} brands (Expect: 67)")
    
    # 2. '신발' 카테고리 브랜드 조회
    # 기대: 신발 특화 브랜드(22개) + 종합 브랜드(14개) = 36개 브랜드
    res_shoes = client.get("/api/products/brands?category_name=신발")
    shoes_data = res_shoes.json()
    print(f"[2] Category '신발': returned {len(shoes_data)} brands")
    print("    First few shoes brands:")
    for b in shoes_data[:5]:
        print(f"      - {b['eng_name']} ({b['category_group']})")
        
    # 3. '시계' 카테고리 브랜드 조회
    # 기대: 시계 특화 브랜드(23개) + 종합 브랜드(14개) = 37개 브랜드
    res_watches = client.get("/api/products/brands?category_name=시계")
    watches_data = res_watches.json()
    print(f"[3] Category '시계': returned {len(watches_data)} brands")
    print("    First few watches brands:")
    for b in watches_data[:5]:
        print(f"      - {b['eng_name']} ({b['category_group']})")

    # 4. '가방' 카테고리 브랜드 조회
    # 기대: 가방 특화 브랜드(8개) + 종합 브랜드(14개) = 22개 브랜드
    res_bags = client.get("/api/products/brands?category_name=가방")
    bags_data = res_bags.json()
    print(f"[4] Category '가방': returned {len(bags_data)} brands")
    print("    First few bags brands:")
    for b in bags_data[:5]:
        print(f"      - {b['eng_name']} ({b['category_group']})")

if __name__ == "__main__":
    test_api()
