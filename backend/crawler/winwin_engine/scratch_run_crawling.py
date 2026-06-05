import os
import sys
import json
import traceback
import time

# Windows 환경 호환성을 위해 stdout UTF-8 강제
sys.stdout.reconfigure(encoding='utf-8')

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = current_dir # 현재 위치가 프로젝트 루트임
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from backend.crawler_engine import CrawlerEngine
from backend.database import get_db

def run_large_scale_crawl():
    print("[START] 대규모 진단 크롤링 시작 (업체별 최대 50개, 1000개 목표)")
    
    vendor_file = os.path.join(current_dir, "weishang_vendors.json")
    with open(vendor_file, "r", encoding="utf-8") as f:
        vendors = json.load(f)
        
    engine = CrawlerEngine()
    db = get_db()
    db.overwrite_all_products([])
    engine.crawled_products = []
    
    target_vendors = vendors[:5]
    print(f"총 {len(target_vendors)}개 업체 대상 크롤링 설정 준비...")
    
    for v_idx, vendor in enumerate(target_vendors):
        if engine.stop_flag:
            break
            
        print(f"\n========================================================")
        print(f"[{v_idx+1}/{len(target_vendors)}] 업체 크롤링 시작: {vendor.get('name')} ({vendor.get('id')})")
        
        settings = {
            "platform": "웨이상(Szwego)",
            "vendorUrl": vendor.get("url"),
            "count": 50,
            "append": True,
            "block_resources": True,
            "transOptions": {
                "enable": False
            }
        }
        
        try:
            engine.start_crawling(settings)
            
            # 스레드가 종료될 때까지 대기
            while engine.crawling_thread and engine.crawling_thread.is_alive():
                time.sleep(2)
                
            print(f"[{vendor.get('name')}] 크롤링 종료. 누적 수집된 상품: {len(engine.crawled_products)}개")
        except Exception as e:
            print(f"업체 크롤링 실패: {e}")
            traceback.print_exc()
            
    print(f"\n[FINISH] 모든 벤더 크롤링 종료. 총 수집된 상품: {len(engine.crawled_products)}개")

if __name__ == "__main__":
    run_large_scale_crawl()
