import asyncio
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

logger = logging.getLogger(__name__)

class CrawlerEngine:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None

    def start_session(self):
        """Initializes the Selenium WebDriver."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        
        # User-agent spoofing if needed for WeChat albums
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
        
        try:
            self.driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()), 
                options=chrome_options
            )
            logger.info("CrawlerEngine session started.")
        except Exception as e:
            logger.error(f"Failed to start crawler session: {e}")
            raise

    def close_session(self):
        if self.driver:
            self.driver.quit()
            logger.info("CrawlerEngine session closed.")

    async def scrape_album(self, url: str):
        """
        Scrape target album page for images and metadata.
        Implemented heavily with lazy-load scrolling and Fallback CSS parsers.
        """
        if not self.driver:
            self.start_session()
            
        logger.info(f"Targeting URL: {url}")
        
        try:
            self.driver.get(url)
            await asyncio.sleep(2) # Initial load wait
            
            # 1. 스크롤 렌더링 (Lazy Loading 완벽 대응)
            logger.info("Executing slow scroll to defeat lazy-loading...")
            scroll_pause_time = 1.5
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            for _ in range(4): # 최대 4회 하강 (데모 안전 방어)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                await asyncio.sleep(scroll_pause_time)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
                
            logger.info("Scroll complete. Extracting loaded DOM.")
            
            # 2. 데이터 추출 (DOM 파싱)
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            raw_items = []
            
            # 범용 CSS 컨테이너 탐색 (주요 쇼핑몰 클래스명 유추)
            product_containers = soup.find_all(['li', 'div', 'a'], class_=lambda c: c and any(kw in c.lower() for kw in ['item', 'product', 'goods', 'box', 'card']))
            
            if not product_containers:
                 logger.warning("Standard containers not found -> using aggressive fallback img scanner")
                 for idx, img in enumerate(soup.find_all('img')):
                     src = img.get('src') or img.get('data-original') or img.get('data-src') or img.get('srcset')
                     if src and ('http' in src or src.startswith('//')):
                         title = img.get('alt') or img.get('title') or f"오토수집_상품_{idx+1}"
                         if src.startswith('//'): src = 'https:' + src
                         # 크기가 작거나 아이콘 류 배제 로직 임시 (일단 모두 수집)
                         if len(src) > 10:
                             raw_items.append({
                                 "id": idx + 1,
                                 "title": title[:30] + "..." if len(title) > 30 else title,
                                 "desc": "이미지 기반 폴백 스캐닝 결과물",
                                 "image_url": src,
                             })
            else:
                 for idx, container in enumerate(product_containers):
                     img_tag = container.find('img')
                     if not img_tag: continue
                     
                     src = img_tag.get('src') or img_tag.get('data-original') or img_tag.get('data-src')
                     if not src: continue
                     if src.startswith('//'): src = 'https:' + src
                     elif not src.startswith('http'): src = self.driver.current_url + src
                     
                     title_tag = container.find(['h1', 'h2', 'h3', 'p', 'span', 'strong'], class_=lambda c: c and any(kw in c.lower() for kw in ['title', 'name', 'txt']))
                     title_text = title_tag.get_text(strip=True) if title_tag else (img_tag.get('alt') or f"앨범 수집상품_{idx+1}")
                     
                     raw_items.append({
                         "id": idx + 1,
                         "title": title_text[:30] + "..." if len(title_text) > 30 else title_text,
                         "desc": "오토 파서 기반 앨범 항목 분석",
                         "image_url": src
                     })

            # 중복 URL 제거 및 최대 10개 슬라이싱 탑재
            unique_items = list({v['image_url']:v for v in raw_items}.values())[:10]
            
            logger.info(f"Successfully scraped {len(unique_items)} items from {url}")
            return unique_items
            
        except Exception as e:
            logger.error(f"Crawling failed for URL {url}: {str(e)}")
            return []
