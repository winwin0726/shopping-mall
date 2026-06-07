import logging
import asyncio
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.database import SessionLocal
from backend.models import HQProduct
from backend.crawler.engine import CrawlerEngine
from backend.crawler.ai_translator import AITranslatorPipeline

logger = logging.getLogger(__name__)

async def run_crawler_pipeline():
    """ 실제 크롤링-번역-저장 파이프라인 (비동기) """
    logger.info("🤖 [크롤링 파이프라인 시작] 원스톱 해외 상품 소싱 진행 중...")
    
    # 1. 크롤러 & 번역기 초기화
    crawler = CrawlerEngine(headless=True)
    translator = AITranslatorPipeline()
    db = SessionLocal()
    
    try:
        # Example Target : 추후 DB의 Target Source List에서 불러오도록 확장 가능
        target_url = "https://example-weishang-album.com/new-arrivals"
        
        # 2. 크롤링 수행 (Raw Item 획득)
        raw_items = await crawler.scrape_album(target_url)
        
        # 수집 결과가 없으면 더미 데이터를 주입하지 않고 종료 (DB 오염 방지)
        if not raw_items:
            logger.info("크롤링 결과가 없어 이번 회차는 건너뜁니다.")
            return

        for item in raw_items:
            # 3. AI 상세 번역
            translated_data = await translator.translate_product_info(
                item.get("cn_name", "Unknown"), 
                item.get("cn_desc", "")
            )
            
            kr_name = translated_data.get("kr_name", "[자동변환] " + item.get("cn_name", "상품"))
            kr_desc = translated_data.get("kr_description", "")
            
            # 4. 환율 및 마진율 30% 적용 동적 계산
            # 예시: 1 CNY = 190 KRW 가정
            cny_price = item.get("source_price_cny", 50)
            base_krw = cny_price * 190
            margin_rate = 0.30
            # 백원 단위 절사 로직 적용
            sell_price = int(base_krw + (base_krw * margin_rate))
            sell_price = (sell_price // 100) * 100 

            # 5. DB 적재 (PENDING)
            new_product = HQProduct(
                category_id=1, # Default 카테고리 (가정)
                kr_name=kr_name,
                kr_description=kr_desc,
                base_price=sell_price,
                stock_quantity=99,
                status="PENDING",
                original_source_url=target_url,
                cn_name=item.get("cn_name", "")
            )
            db.add(new_product)
            
        db.commit()
        logger.info(f"✅ 성공적으로 {len(raw_items)}개의 상품이 PENDING 상태로 입고 대기열에 추가되었습니다.")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 크롤링 파이프라인 에러: {str(e)}")
    finally:
        crawler.close_session()
        db.close()

def automated_daily_crawling_job():
    # 백그라운드 스레드에서 Async Loop를 돌리기 위함
    asyncio.run(run_crawler_pipeline())

# Global Scheduler Instance
scheduler = BackgroundScheduler()

def start_scheduler():
    # C3: 기본 비활성. 과거엔 example-weishang-album.com 더미 URL 대상으로 매일 02:00 무조건 실패했음.
    #     실제 소싱 대상이 준비된 경우에만 ENABLE_DAILY_CRAWLER=1 로 활성화한다.
    if os.getenv("ENABLE_DAILY_CRAWLER") == "1":
        scheduler.add_job(
            automated_daily_crawling_job,
            trigger=CronTrigger(hour=2, minute=0),
            id="daily_crawler_job",
            replace_existing=True
        )
        logger.info("⏰ 일일 자동 크롤 잡 등록됨 (ENABLE_DAILY_CRAWLER=1).")
    else:
        logger.info("⏰ 일일 자동 크롤 잡 비활성(기본). 활성화하려면 ENABLE_DAILY_CRAWLER=1 + 실제 소스 설정.")
    scheduler.start()
    logger.info("⏰ Background APScheduler 가동 완료.")

def stop_scheduler():
    scheduler.shutdown()
    logger.info("⏰ Background APScheduler가 종료되었습니다.")
