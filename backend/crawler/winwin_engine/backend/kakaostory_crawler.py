import asyncio
import json
import os
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("KakaoStoryCrawler")

class KakaoStoryCrawler:
    def __init__(self, target_url, category="공통"):
        self.target_url = target_url
        self.category = category
        self.output_file = f"user_post_history_{category}.json"
        
    async def extract_posts(self):
        """카카오스토리 페이지 접속 및 스크롤을 통한 과거 포스팅 수집"""
        logger.info(f"🚀 카카오스토리 크롤러 엔진 부팅 중... 대상: {self.target_url}")
        
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(
                    headless=False,
                    args=["--window-size=800,700", "--window-position=0,0"]
                )
                context = await browser.new_context(
                    viewport={'width': 800, 'height': 700},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = await context.new_page()
                # ─── STEP 1: 크롬 브라우저로 대상 페이지 접속 ───
                logger.info("  🌐 페이지 접속 중...")
                await page.goto(self.target_url, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)  # 페이지가 충분히 렌더링될 때까지 대기
                
                # ─── STEP 2: 로그인 대기 팝업 (OK 누를 때까지 크롤링 절대 시작 안 함) ───
                logger.info("⏳ [대기 모드] 크롬 브라우저가 열렸습니다. 로그인 완료 후 알림창의 [확인]을 눌러주세요.")
                logger.warning("⚠️ 크롤링은 [확인] 버튼을 누르기 전까지 시작되지 않습니다.")
                
                import ctypes
                import asyncio
                
                def show_login_popup():
                    """윈도우 시스템 팝업으로 로그인 대기 → OK 누를 때까지 블로킹"""
                    user32 = ctypes.windll.user32
                    # 비프음으로 주의 환기 (MB_ICONWARNING 비프)
                    ctypes.windll.kernel32.Beep(800, 300)
                    # MB_OK=0 | MB_TOPMOST=0x40000 | MB_ICONWARNING=0x30 | MB_SETFOREGROUND=0x10000
                    flags = 0x00000000 | 0x00040000 | 0x00000030 | 0x00010000
                    user32.MessageBoxW(
                        0,
                        "🔐 크롬 브라우저에서 카카오스토리 로그인을 완료해주세요.\n\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        "① 열려 있는 크롬 창에서 카카오 로그인을 진행하세요.\n"
                        "② 로그인이 완료되어 게시물이 보이면\n"
                        "③ 이 창의 [확인] 버튼을 누르세요.\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        "※ [확인]을 누르면 AI 스타일 추출(크롤링)이 시작됩니다.",
                        "🤖 윈윈 크롤러 — AI 추출 대기",
                        flags
                    )
                
                # 팝업이 닫힐 때까지 여기서 대기 (사용자가 OK를 눌러야만 다음으로 진행)
                await asyncio.to_thread(show_login_popup)
                
                logger.info("  ✅ 사용자 확인 완료! AI 크롤링 분석을 시작합니다.")
                
                # ─── STEP 3: 로그인 후 대상 URL 재접속 (리다이렉트 방어) ───
                await page.goto(self.target_url, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                
                logger.info("  ⬇️ 과거 데이터 로딩을 위한 딥 스크롤 가동 (목표: 대량 수집)")
                # 스크롤 로직 (끝까지 여러 번 내리기)
                try:
                    last_height = await page.evaluate("document.body.scrollHeight")
                    scroll_attempts = 0
                    max_scrolls = 100  # 대량 포스팅 수집을 위한 스크롤 횟수
                    
                    while scroll_attempts < max_scrolls:
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                        await page.wait_for_timeout(2000) # 데이터 로딩 대기
                        
                        new_height = await page.evaluate("document.body.scrollHeight")
                        if new_height == last_height:
                            logger.info("  ✅ 더 이상 로딩할 과거 포스팅이 없습니다.")
                            break
                        last_height = new_height
                        scroll_attempts += 1
                        logger.info(f"  ... 스크롤 {scroll_attempts}/{max_scrolls} 완료")
                except Exception as e:
                    logger.warning(f"  ⚠️ 스크롤 중 화면 전환 감지(리다이렉트). 현재 상태까지만 수집합니다: {e}")
                
                # DOM 파싱
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                # 포스팅 아이템 추출 (카카오스토리 DOM 구조 분석)
                # 카스는 보통 <div class="_post">, <div class="post">, <div data-kant-id> 등의 구조를 가짐
                # 최근 구조는 _18vM 등의 난독화 클래스를 사용하므로, 텍스트가 있는 컨테이너를 넓게 잡습니다.
                posts = []
                
                # 텍스트 본문 추출 (보통 클래스명에 'text'나 'content', 'desc'가 포함되거나 p 태그 사용)
                # 포스트 영역 전체를 잡아서 텍스트와 해시태그를 뽑습니다.
                post_elements = soup.find_all('div', attrs={"data-section": "Section_Feed"})
                if not post_elements:
                     # 카카오스토리의 일반적인 본문 텍스트 클래스들
                    post_elements = soup.find_all(['p', 'div', 'span'], class_=lambda c: c and any(kw in c.lower() for kw in ['text', 'content', 'desc', 'txt', 'article']))
                
                # 그래도 없으면 페이지 안의 길이가 긴 <p> 태그들을 강제로 모두 가져옴
                if not post_elements:
                    all_p = soup.find_all('p')
                    post_elements = [p for p in all_p if len(p.get_text(strip=True)) > 20]

                logger.info(f"  🔍 {len(post_elements)}개의 포스팅 엘리먼트 감지됨. 텍스트 추출 시작...")
                
                for el in post_elements:
                    # <br> 태그를 실제 줄바꿈 기호로 변환하여 사장님의 '엔터 치는 습관'을 그대로 보존
                    for br in el.find_all("br"):
                        br.replace_with("\n")
                    
                    raw_text = el.get_text(separator=' ', strip=True)
                    # 줄바꿈 복구 (연속 공백을 살림)
                    clean_text = el.get_text(separator='\n').strip()
                    
                    # 너무 짧은 글은 상품 포스팅이 아닐 확률이 높으므로 제외
                    if len(clean_text) < 20:
                        continue
                        
                    # 해시태그 추출
                    tags = re.findall(r'#(\w+)', clean_text)
                    
                    post_data = {
                        "content": clean_text,
                        "tags": tags,
                        "length": len(clean_text)
                    }
                    if post_data not in posts: # 중복 방지
                        posts.append(post_data)
                
                # JSON 저장
                if posts:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    save_path = os.path.join(base_dir, self.output_file)
                    with open(save_path, 'w', encoding='utf-8') as f:
                        json.dump(posts, f, ensure_ascii=False, indent=2)
                    logger.info(f"  🎉 총 {len(posts)}개의 과거 포스팅 텍스트를 성공적으로 추출하여 저장했습니다. [{save_path}]")
                else:
                    logger.error("  ❌ 포스팅 텍스트를 찾지 못했습니다. 카카오스토리 DOM 구조 변경이나 비공개 설정일 수 있습니다.")
                    
            except Exception as e:
                logger.error(f"  ❌ 크롤링 중 오류 발생: {e}")
                try:
                    import traceback
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    dump_dir = os.path.join(base_dir, 'error_dumps')
                    os.makedirs(dump_dir, exist_ok=True)
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    prefix = os.path.join(dump_dir, f"{ts}_kakao_fatal")
                    if 'page' in locals() and page:
                        await page.screenshot(path=f"{prefix}.png", full_page=True)
                        content = await page.content()
                        with open(f"{prefix}.html", "w", encoding="utf-8") as f:
                            f.write(content)
                        with open(f"{prefix}_info.txt", "w", encoding="utf-8") as f:
                            f.write(f"URL: {page.url}\n")
                            f.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"Traceback:\n{traceback.format_exc()}\n")
                        logger.info(f"📸 에러 캡처 완료: {prefix}")
                except Exception as dmp_err:
                    logger.warning(f"⚠️ 에러 캡처 실패: {dmp_err}")
            finally:
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass

if __name__ == "__main__":
    import sys
    # 테스트 실행용
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        crawler = KakaoStoryCrawler(test_url)
        asyncio.run(crawler.extract_posts())
    else:
        print("사용법: python kakaostory_crawler.py [카카오스토리 URL]")
