import sys
import os
import json
import time

sys.path.append('backend')
from crawler_engine import CrawlerEngine

def main():
    if not os.path.exists('weishang_vendors.json'):
        print("No weishang_vendors.json found.")
        return

    with open('weishang_vendors.json', 'r', encoding='utf-8') as f:
        vendors_data = json.load(f)

    urls = []
    if isinstance(vendors_data, list):
        urls = [v.get('url', '') for v in vendors_data if isinstance(v, dict)]
    elif isinstance(vendors_data, dict):
        urls = list(vendors_data.keys())
    
    urls = [u for u in urls if u and "szwego.com" in u]
    print(f"Loaded {len(urls)} vendors from weishang_vendors.json")

    # 1000개를 수집하기 위해 대략 25개 업체를 추출
    target_urls = urls[:25]
    if not target_urls:
        print("No szwego urls found.")
        return

    vendor_url_raw = "\n".join(target_urls)
    
    settings = {
        "platform": "웨이상(Szwego)",
        "count": 50, # 업체당 50개 (총 1250개 예상)
        "vendorUrl": vendor_url_raw,
        "append": False,
        "max_scrolls": 10,
    }

    engine = CrawlerEngine()
    print("Starting massive crawl for 1000+ items...")
    engine.start_crawling(settings)

    last_count = 0
    try:
        while engine.crawling_thread and engine.crawling_thread.is_alive():
            time.sleep(5)
            curr = len(engine.crawled_products)
            if curr != last_count:
                print(f"Crawled products so far: {curr}")
                last_count = curr
    except KeyboardInterrupt:
        print("Interrupted by user. Stopping...")
        engine.stop_crawling()
        
    print("Massive Crawl completed.")
    print(f"Total collected: {len(engine.crawled_products)}")

if __name__ == '__main__':
    main()
