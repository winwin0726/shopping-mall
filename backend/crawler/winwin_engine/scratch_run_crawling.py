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
backend_dir = os.path.join(project_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.crawler_engine import CrawlerEngine
from backend.database import CrawlDB

def run_large_scale_crawl():
    print("[START] 100개 목표 대규모 진단 크롤링 재개 (누적 수집)")
    
    # DB 초기화 비활성화 (기존 62건 누적 수집)
    try:
        db = CrawlDB()
        current_cnt = db.count_all_products()
        print(f"📊 [DB 확인] 현재 DB에 저장된 상품 수: {current_cnt}개. 100개 돌파까지 이어서 수집합니다.")
    except Exception as dbe:
        print(f"DB 확인 실패: {dbe}")
        sys.exit(1)
        
    vendor_file = os.path.join(current_dir, "weishang_vendors.json")
    with open(vendor_file, "r", encoding="utf-8") as f:
        vendors = json.load(f)
        
    engine = CrawlerEngine()
    engine.crawled_products = []
    
    # 상위 10개 벤더는 완료했으므로 11번째 벤더부터 순차 크롤링 시작
    target_vendors = vendors[10:]
    print(f"총 {len(target_vendors)}개 업체 대상 순차 크롤링 시작...")
    
    for v_idx, vendor in enumerate(target_vendors):
        if engine.stop_flag:
            break
            
        # 매 루프 시작시 실시간 DB 적재량 검사
        try:
            db_check = CrawlDB()
            current_cnt = db_check.count_all_products()
            if current_cnt >= 100:
                print(f"🎯 [목표 달성] 현재 DB 상품 수: {current_cnt}개 (목표 100개 돌파). 크롤링을 종료합니다.")
                break
        except Exception as ce:
            print(f"DB 카운트 실시간 확인 실패: {ce}")
            
        print(f"\n========================================================")
        print(f"[{v_idx+1}/{len(target_vendors)}] 업체 크롤링 시작: {vendor.get('name')} ({vendor.get('id')})")
        
        settings = {
            "platform": "웨이상(Szwego)",
            "vendorUrl": vendor.get("url"),
            "apiKey": "AIzaSyDcyjVgYktiGvTKLioDM9WhQo3Et5S8dXI",
            "count": 15, # 업체당 최대 15개
            "append": True,
            "block_resources": True,
            "transOptions": {
                "enable": False, # API Key 유출 정지로 인한 딜레이/에러 방지를 위해 번역 비활성화
                "fx": 190.0,
                "category": "공통"
            }
        }
        
        try:
            engine.start_crawling(settings)
            
            # 스레드가 종료될 때까지 대기
            while engine.crawling_thread and engine.crawling_thread.is_alive():
                # 실시간 목표 도달 여부 스레드 내부에서도 체크
                try:
                    db_check = CrawlDB()
                    if db_check.count_all_products() >= 100:
                        engine.stop() # 크롤러 중단 명령 전달
                        print("🎯 [목표 달성] 수집 도중 100개 목표 돌파로 크롤러에 중단 명령을 전송했습니다.")
                        break
                except:
                    pass
                time.sleep(2)
                
            print(f"[{vendor.get('name')}] 크롤링 종료. 누적 수집된 상품: {len(engine.crawled_products)}개")
        except Exception as e:
            print(f"업체 크롤링 실패: {e}")
            traceback.print_exc()
            
    try:
        db_check = CrawlDB()
        final_cnt = db_check.count_all_products()
        print(f"\n[FINISH] 대규모 크롤링 수집 종료. DB 최종 저장 상품 수: {final_cnt}개")
    except:
        pass

if __name__ == "__main__":
    run_large_scale_crawl()
