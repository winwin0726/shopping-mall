import sys
import os

# Set absolute path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.database import SessionLocal, engine, Base
from backend.models import HQProduct, Category

def seed_pending_products():
    db = SessionLocal()
    try:
        # Create tables just in case we are running fresh
        Base.metadata.create_all(bind=engine)
        
        # Check if products already exist to avoid spamming
        existing = db.query(HQProduct).filter(HQProduct.status == "PENDING").count()
        if existing > 0:
            print(f"이미 {existing}개의 PENDING 상품이 있습니다. 시드를 종료합니다.")
            return

        print("Tinder UI 연동 테스트를 위해 3개의 가상 PENDING 상품을 DB에 삽입합니다...")
        
        # Create dummy category first to satisfy category_id constraint
        cat = db.query(Category).first()
        if not cat:
            cat = Category(name="임시 카테고리", slug="temp-cat")
            db.add(cat)
            db.commit()
            db.refresh(cat)

        p1 = HQProduct(
            category_id=cat.id,
            cn_name="韩版潮流修身小西装", 
            kr_name="[실데이터 연동] 한국풍 트렌디 슬림핏 블레이저", 
            kr_description="자동 크롤링 테스트 데이터",
            base_price=45000, 
            ai_fitting_image_url="https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=500&q=80",
            status="PENDING"
        )
        
        p2 = HQProduct(
            category_id=cat.id,
            cn_name="复古港味高腰牛仔裤", 
            kr_name="[실데이터 연동] 레트로 하이웨이스트 데님 팬츠", 
            kr_description="자동 크롤링 테스트 데이터",
            base_price=32000, 
            ai_fitting_image_url="https://images.unsplash.com/photo-1542272827-b49dfce3de70?w=500&q=80",
            status="PENDING"
        )

        p3 = HQProduct(
            category_id=cat.id,
            cn_name="夏季法式桔梗裙", 
            kr_name="[실데이터 연동] 여름 프렌치 린넨 원피스", 
            kr_description="자동 크롤링 테스트 데이터",
            base_price=58000, 
            ai_fitting_image_url="https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=500&q=80",
            status="PENDING"
        )

        db.add_all([p1, p2, p3])
        db.commit()
        
        print("✅ DB 삽입 완료! Admin 페이지를 새로고침 해보세요.")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_pending_products()
