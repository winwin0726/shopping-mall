import os
import sys
import json
import logging
from types import ModuleType
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import HQProduct, Category
from backend.config import settings

logger = logging.getLogger(__name__)

# --- PyQt5 Mocking to bypass GUI dependency in backend ---
if "PyQt5" not in sys.modules:
    pyqt5 = ModuleType("PyQt5")
    sys.modules["PyQt5"] = pyqt5
    
    qtcore = ModuleType("PyQt5.QtCore")
    class DummyQThread:
        def __init__(self, parent=None):
            self.parent = parent
        def start(self):
            self.run()
        def isRunning(self):
            return False
        def is_alive(self):
            return False
            
    class DummyPyqtSignal:
        def __init__(self, *args, **kwargs):
            self.handlers = []
        def connect(self, handler):
            self.handlers.append(handler)
        def emit(self, *args, **kwargs):
            for handler in self.handlers:
                try:
                    handler(*args)
                except Exception as e:
                    logger.error(f"Error in dummy signal handler: {e}")
                    
    qtcore.QThread = DummyQThread
    qtcore.pyqtSignal = DummyPyqtSignal
    sys.modules["PyQt5.QtCore"] = qtcore

# 윈윈크롤러3 폴더를 sys.path에 임포트 경로로 추가
CRAWLER_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.join(CRAWLER_DIR, "winwin_engine")
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

from winwin_engine.weishang_crawling_thread import WeishangCrawlingThread
from backend.routers.crawler import extract_sizes_from_text

def scrape_weishang_album_sync(
    vendor_url: str,
    target_count: int,
    exchange_rate: float,
    margin_rate: float,
    category_id: int,
    db: Session
) -> list:
    """
    웨이상 앨범 URL에서 상품을 긁어와 AI 번역 가공 및 사이즈 캐치 후,
    자동으로 DB에 99개씩 재고 할당 등록하고 등록된 상품 리스트를 리턴합니다.
    """
    # 1. 카테고리 정보 조회
    cat = db.query(Category).filter(Category.id == category_id).first()
    category_name = cat.name if cat else "미분류"
    
    # 윈윈크롤러3에 연동할 번역 옵션
    trans_options = {
        "enable": True,
        "api_key": settings.GEMINI_API_KEY or "",
        "naver_fx": exchange_rate,
        "prefix": "WINWIN",
        "category": category_name
    }
    
    # 저장 대상 디렉토리 (임시)
    dest_dir = os.path.join(ENGINE_DIR, "temp_downloads")
    os.makedirs(dest_dir, exist_ok=True)
    
    scraped_products = []
    
    temp_items = []
    
    # 크롤러 결과 수집용 핸들러
    def on_result_received(item: dict):
        # 발견 시 바로 DB에 넣지 않고 임시 메모리 리스트에 수집된 정보를 순서대로 누적합니다.
        temp_items.append(item)
        logger.info(f"Buffered winwin crawled product for reverse importing: {item.get('title')}")

    # 윈윈크롤러3 앨범 스크레퍼 스레드 인스턴스화
    crawler_thread = WeishangCrawlingThread(
        vendor_url=vendor_url,
        vendor_name=os.path.basename(vendor_url)[:20],
        target_count=target_count,
        dest_dir=dest_dir,
        headless_mode=True,
        trans_options=trans_options
    )
    
    # 결과 수신 시그널 연결 (더미 시그널 호출)
    crawler_thread.result_signal.connect(on_result_received)
    
    # 크롤러 실행 (QThread의 run() 메서드를 직접 동기식 호출)
    logger.info("Starting WeishangCrawlingThread run loop...")
    crawler_thread.run()
    logger.info("WeishangCrawlingThread run loop complete.")
    
    # [수집 순서 보정] 위챗/웨이상 앨범은 최신 수집물이 리스트 전면에 오므로,
    # 수집 완료 후 과거 상품부터 역순(reversed)으로 DB에 저장해야 최신 등록 상품이 쇼핑몰 최상단에 뜨게 됩니다.
    for item in reversed(temp_items):
        try:
            title = item.get("title") or "미상 수집 상품"
            raw_desc = item.get("raw_description") or ""
            local_image_dir = item.get("local_image_dir") or ""
            image_files = item.get("image_files") or []
            
            # 가격 계산
            calculated_price = int(item.get("sale_price") or 0)
            if calculated_price <= 0:
                calculated_price = 30000 # 기본값
            
            # 본문에서 사이즈 정밀 감지
            parsed_sizes = extract_sizes_from_text(f"{title} {raw_desc}", category_name)
            
            # DB용 이미지 URL 목록 생성 (백엔드 static 경로에 맞춰 매핑)
            web_images = []
            for img_file in image_files:
                img_path = f"/static/crawler/{os.path.basename(local_image_dir)}/{img_file}"
                web_images.append(img_path)
            
            if not web_images:
                web_images = ["/placeholder.png"]
                
            # 브랜드 판별
            from backend.utils.brand_detector import detect_brand_id
            detected_brand_id = detect_brand_id(db, title, raw_desc)
            
            # 상품 DB 적재
            new_prod = HQProduct(
                category_id=category_id,
                brand_id=detected_brand_id,
                original_source_url=vendor_url,
                cn_name=title,
                kr_name=title[:50], # 앞 50자
                kr_description=raw_desc,
                base_price=calculated_price,
                images=web_images,
                status="PENDING"
            )
            
            if parsed_sizes:
                new_prod.size_stock_config = parsed_sizes
                new_prod.stock_quantity = sum(parsed_sizes.values())
            else:
                # 사이즈가 전혀 감지되지 않은 경우 기본 사이즈런 99개 지정
                default_sizes = {}
                if any(k in category_name for k in ["의류", "상의", "하의", "아우터"]):
                    default_sizes = { "S": 99, "M": 99, "L": 99, "XL": 99, "Free": 99 }
                elif any(k in category_name for k in ["가방", "백"]):
                    default_sizes = { "Mini": 99, "Medium": 99, "Large": 99, "Free": 99 }
                elif any(k in category_name for k in ["신발", "슈즈"]):
                    default_sizes = { "230": 99, "235": 99, "240": 99, "245": 99, "250": 99, "255": 99, "260": 99, "265": 99, "270": 99, "275": 99, "280": 99 }
                
                if default_sizes:
                    new_prod.size_stock_config = default_sizes
                    new_prod.stock_quantity = sum(default_sizes.values())
                else:
                    new_prod.stock_quantity = 0
            
            db.add(new_prod)
            db.commit()
            db.refresh(new_prod)
            
            scraped_products.append({
                "id": new_prod.id,
                "kr_name": new_prod.kr_name,
                "base_price": new_prod.base_price,
                "stock_quantity": new_prod.stock_quantity,
                "parsed_sizes": new_prod.size_stock_config,
                "images": new_prod.images,
                "brand_id": detected_brand_id
            })
            logger.info(f"Successfully integrated winwin crawled product (reverse sequence): {new_prod.kr_name}")
            
        except Exception as e:
            logger.error(f"Error while mapping winwin item to DB: {e}", exc_info=True)
            db.rollback()
            
    return scraped_products
