# -*- coding: utf-8 -*-
import os
import sys

# 프로젝트 루트를 path에 추가하여 backend 임포트가 가능하게 설정
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(_BASE_DIR)

from backend.database import SessionLocal
from backend.utils.brand_detector import detect_brand_id
from backend.models import Brand

def run_tests():
    db = SessionLocal()
    try:
        # DB에 있는 브랜드 정보 출력 (테스트용)
        chanel = db.query(Brand).filter(Brand.slug == "chanel").first()
        goldengoose = db.query(Brand).filter(Brand.slug == "golden-goose").first()
        rolex = db.query(Brand).filter(Brand.slug == "rolex").first()
        
        print(f"Chanel Mapping: {chanel.name if chanel else 'None'} -> {chanel.category_group if chanel else 'None'}")
        print(f"Golden Goose Mapping: {goldengoose.name if goldengoose else 'None'} -> {goldengoose.category_group if goldengoose else 'None'}")
        print(f"Rolex Mapping: {rolex.name if rolex else 'None'} -> {rolex.category_group if rolex else 'None'}")
        print("-" * 50)
        
        # 시나리오 A: 카테고리 = "가방", 텍스트 = "샤넬 클래식 플랩백 백팩"
        # 기대 결과: 샤넬 감지 (Chanel의 category_group = 'all')
        brand_id_a = detect_brand_id(db, "샤넬 클래식 플랩백 백팩", category_name="가방")
        brand_a = db.query(Brand).filter(Brand.id == brand_id_a).first() if brand_id_a else None
        print(f"[A] Category: 가방 | Text: '샤넬 클래식 플랩백 백팩'")
        print(f"    -> Result: {brand_a.name if brand_a else 'None'} (Expected: 샤넬)")
        
        # 시나리오 B: 카테고리 = "가방", 텍스트 = "골든구스 가죽 가방"
        # 기대 결과: None (Golden Goose의 category_group = 'shoes'이므로 'bag' 쿼리 시 제외되어 오탐 차단)
        brand_id_b = detect_brand_id(db, "골든구스 가죽 가방", category_name="가방")
        brand_b = db.query(Brand).filter(Brand.id == brand_id_b).first() if brand_id_b else None
        print(f"[B] Category: 가방 | Text: '골든구스 가죽 가방'")
        print(f"    -> Result: {brand_b.name if brand_b else 'None'} (Expected: None)")

        # 시나리오 C: 카테고리 = "신발", 텍스트 = "골든구스 슈퍼스타 스니커즈"
        # 기대 결과: 골든구스 감지 (shoes 카테고리이므로 매칭되어야 함)
        brand_id_c = detect_brand_id(db, "골든구스 슈퍼스타 스니커즈", category_name="신발")
        brand_c = db.query(Brand).filter(Brand.id == brand_id_c).first() if brand_id_c else None
        print(f"[C] Category: 신발 | Text: '골든구스 슈퍼스타 스니커즈'")
        print(f"    -> Result: {brand_c.name if brand_c else 'None'} (Expected: 골든구스)")

        # 시나리오 D: 카테고리 = "시계", 텍스트 = "롤렉스 서브마리너 메탈 시계"
        # 기대 결과: 롤렉스 감지 (watch 카테고리이므로 매칭되어야 함)
        brand_id_d = detect_brand_id(db, "롤렉스 서브마리너 메탈 시계", category_name="시계")
        brand_d = db.query(Brand).filter(Brand.id == brand_id_d).first() if brand_id_d else None
        print(f"[D] Category: 시계 | Text: '롤렉스 서브마리너 메탈 시계'")
        print(f"    -> Result: {brand_d.name if brand_d else 'None'} (Expected: 롤렉스)")

    except Exception as e:
        print(f"Test execution error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
