"""
crawler_engine.py
─────────────────
FastAPI 백엔드 전용 크롤링/포스팅 오케스트레이터.
PyQt 의존성 100% 제거. 순수 Python + threading 기반.

기존 platform_base.py → KakaoCrawler / BandPoster / BandCrawlingThread 등을
조합하여 프론트엔드 API 요청에 따라 크롤링·포스팅 파이프라인을 실행한다.
"""

import os
import sys
import logging
import threading
import time
import datetime
import json
import re
try:
    from backend.database import get_db, get_system_settings
except ImportError:
    from database import get_db, get_system_settings
try:
    from backend.error_dumper import save_error_dump
except ImportError:
    try:
        from error_dumper import save_error_dump
    except:
        save_error_dump = lambda *args, **kwargs: None

# ── 프로젝트 루트 경로를 sys.path에 추가 (모듈 import 용) ──────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from backend.browser_sensors import apply_quiet_chrome_options
except ImportError:
    from browser_sensors import apply_quiet_chrome_options


class CrawlerEngine:
    """
    UI가 없는 파이썬 백엔드 엔진. (PyQt 의존성 100% 제거)
    프론트엔드 API 요청을 받아 실제 Selenium 크롤링/포스팅을 실행하는 오케스트레이터.
    """
    def __init__(self):
        self.logs = []              # 전체 로그 보관 (API에서 표시용/복사용으로 분리)
        self.max_logs = 10000       # 장시간 실행 시 메모리 폭주 방지용 상한
        self.progress = {"val": 0, "max": 0}
        self.stop_flag = False

        # DB 로딩 진행 상태 (프론트엔드 프로그레스바용)
        self.db_load_progress = {"current": 0, "total": 0, "percent": 0, "done": False}

        # 스레드 충돌 방지용 동기화 락 (중첩 호출 허용을 위해 RLock 사용)
        self.lock = threading.RLock()

        # 외부 통신(API -> WebSocket) 용 콜백
        self.on_state_change = None
        self._last_ws_notify_time = 0  # WebSocket 쿜링 쓰로틀링 (100ms)

        # 스레드 관리
        self.crawling_thread = None
        self.posting_thread = None
        self._posting_running = False

        from concurrent.futures import ThreadPoolExecutor
        self.translation_executor = ThreadPoolExecutor(max_workers=3)

        # Selenium 드라이버 (플랫폼별)
        self.source_driver = None   # 크롤링용 (카카오/밴드)
        self.target_driver = None   # 포스팅용

        # 크롤링 결과 저장소
        self.crawled_products = []
        self.products_loaded = False
        self.db_saved_product_count = 0

        # 크롤러/포스터 인스턴스
        self._source_crawler = None
        self._target_poster = None

        self.db = get_db()
        self._last_crawl_settings = None
        self._last_post_settings = None
        self._load_persisted_settings()
        self._init_product_load_policy()

    def _load_persisted_settings(self):
        """디스크(system_settings.json)로부터 이전 크롤링 및 포스팅 설정을 로드하여 동기화합니다."""
        try:
            settings = get_system_settings()
            self._last_crawl_settings = settings.get("last_crawl_settings")
            self._last_post_settings = settings.get("last_post_settings")
        except Exception as e:
            self.add_log(f"⚠️ 디스크 이전 설정 로드 중 오류: {e}", "WARNING", False)

    @property
    def last_crawl_settings(self):
        if self._last_crawl_settings is None:
            self._load_persisted_settings()
        return self._last_crawl_settings

    @last_crawl_settings.setter
    def last_crawl_settings(self, settings: dict):
        self._last_crawl_settings = settings
        try:
            try:
                from backend.database import save_system_settings
            except ImportError:
                from database import save_system_settings
            sys_settings = get_system_settings()
            sys_settings["last_crawl_settings"] = settings
            save_system_settings(sys_settings)
        except Exception as e:
            self.add_log(f"⚠️ 크롤링 설정 디스크 저장 중 오류: {e}", "WARNING", False)

    @property
    def last_post_settings(self):
        if self._last_post_settings is None:
            self._load_persisted_settings()
        return self._last_post_settings

    @last_post_settings.setter
    def last_post_settings(self, settings: dict):
        self._last_post_settings = settings
        try:
            try:
                from backend.database import save_system_settings
            except ImportError:
                from database import save_system_settings
            sys_settings = get_system_settings()
            sys_settings["last_post_settings"] = settings
            save_system_settings(sys_settings)
        except Exception as e:
            self.add_log(f"⚠️ 포스팅 설정 디스크 저장 중 오류: {e}", "WARNING", False)

    def _init_product_load_policy(self):
        """시작 시 DB 상품 원본을 자동 적재할지 결정한다."""
        total = self.db.count_all_products()
        self.db_saved_product_count = total
        settings = get_system_settings()
        if settings.get("auto_load_last_products_on_start", False):
            self._load_products_with_progress(force=True)
            return

        self.db_load_progress = {
            "current": 0,
            "total": total,
            "percent": 100,
            "done": True,
            "loaded": False,
            "skipped": total > 0,
        }
        if total > 0:
            self.add_log(
                f"📂 저장된 크롤링 데이터 {total}건이 있습니다. 시작 시 자동 불러오기는 생략했습니다.",
                "INFO",
                False,
            )
        self.notify_update()

    def _load_products_with_progress(self, force=False):
        """DB에서 상품을 배치 로딩하며 진행률을 실시간 업데이트한다."""
        with self.lock:
            if self.products_loaded and not force:
                return
            self.crawled_products = []

        total = self.db.count_all_products()
        self.db_saved_product_count = total
        if total == 0:
            self.db_load_progress = {"current": 0, "total": 0, "percent": 100, "done": True, "loaded": True, "skipped": False}
            self.products_loaded = True
            return

        self.db_load_progress = {"current": 0, "total": total, "percent": 0, "done": False, "loaded": False, "skipped": False}
        self.add_log(f"📂 백업된 DB에서 크롤링 데이터 ({total}건) 불러오기 시작...", "INFO", False)

        BATCH_SIZE = 200
        loaded = 0
        for offset in range(0, total, BATCH_SIZE):
            batch = self.db.get_products_batch(offset, BATCH_SIZE)
            try:
                from pricing_logic import clean_vendor_name
            except ImportError:
                from backend.pricing_logic import clean_vendor_name

            with self.lock:
                for item in batch:
                    if "vendor_name" in item:
                        item["vendor_name"] = clean_vendor_name(item["vendor_name"])
                self.crawled_products.extend(batch)
            loaded += len(batch)
            percent = min(int((loaded / total) * 100), 100)
            self.db_load_progress = {"current": loaded, "total": total, "percent": percent, "done": False, "loaded": False, "skipped": False}
            self.notify_update()

        self.products_loaded = True
        self.db_load_progress = {"current": total, "total": total, "percent": 100, "done": True, "loaded": True, "skipped": False}
        self.add_log(f"📂 백업된 DB에서 크롤링 데이터 ({total}건) 불러오기 완료", "INFO", False)
        self.notify_update()

    def ensure_products_loaded(self):
        """필요한 시점에만 DB 상품 원본을 메모리에 적재한다."""
        if not self.products_loaded:
            self._load_products_with_progress(force=True)

    def notify_update(self):
        """WebSocket 업데이트 푸시 (100ms 쓰로틀링 적용)"""
        now = time.time()
        if now - self._last_ws_notify_time < 0.1:  # 100ms 내 중복 호출 억제
            return
        self._last_ws_notify_time = now
        if self.on_state_change:
            self.on_state_change()

    def save_temp_data(self):
        """(Legacy) UI 호환성을 위해 유지하되 DB 전체 덮어쓰기로 기능 변경"""
        try:
            with self.lock:
                get_db().overwrite_all_products(self.crawled_products)
        except Exception as e:
            self.add_log(f"⚠️ DB 저장 실패: {e}", "WARNING", False)

    # ─── 로그 관리 ─────────────────────────────────────────────────────────
    def add_log(self, text, level="INFO", to_telegram=False, category=None):
        """직접 로그 리스트에 적재"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        if not category:
            thread_name = threading.current_thread().name
            if thread_name and thread_name != "MainThread":
                if "img_dl" in thread_name or "weishang" in thread_name:
                    category = "수집(weishang)"
                elif "kakao" in thread_name:
                    category = "수집(kakao)"
                elif "band" in thread_name:
                    category = "수집(band)"
                elif "포스팅" in thread_name:
                    category = "포스팅"
                elif "AI" in thread_name:
                    category = "AI번역"
                else:
                    category = "system"
            else:
                category = "system"

        log_entry = {"text": f"[{timestamp}] {text}", "level": level, "category": category}

        with self.lock:
            self.logs.append(log_entry)
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-self.max_logs:]

        self.notify_update()

        try:
            # Windows cp949 콘솔에서 이모지 깨짐 방지: 안전한 ASCII 폴백
            safe_text = text.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8', errors='replace')
            print(f"[{level}] {safe_text}")
        except Exception:
            pass  # 콘솔 출력 실패는 무시 (로그 리스트에는 이미 저장됨)

        # [텔레그램 연동 로직 추가 (스팸 방지 필터링 적용)]
        if getattr(self, 'telegram_token', None) and getattr(self, 'telegram_chat_id', None):
            send_allowed = False
            text_lower = text.lower()

            # 1. 명시적으로 to_telegram=True 인 경우
            if to_telegram:
                send_allowed = True
            else:
                # 2. 반드시 보고해야 하는 주요 마일스톤 키워드 (파이프라인 최적화)
                # 너무 잦은 알림을 막기 위해 시작, 종료, 에러, 요약 결과만 전송
                essential_keywords = ["크롤링 시작", "크롤링 완료", "포스팅 시작", "포스팅 완료", "모든 작업 완료", "에러", "실패", "정지"]
                if any(k in text_lower for k in essential_keywords):
                    send_allowed = True

                    # 단, 개별 게시물 업로드 완료 등은 제외하여 노이즈 감소
                    if "게시물" in text_lower and "완료" in text_lower and "모든" not in text_lower:
                        send_allowed = False

                # 3. 누적 진행 상황 알림 (진행 과정 중 특정 단위, 예: 50개, 100개)
                if "수집 누적" in text_lower or "포스팅 누적" in text_lower:
                    try:
                        import re
                        num_match = re.search(r'누적\s*(\d+)', text)
                        if num_match:
                            count = int(num_match.group(1))
                            # 50개 단위로만 전송하여 빈도 대폭 감소
                            if count > 0 and (count % 50 == 0):
                                send_allowed = True
                                text = f"🔄 <b>파이프라인 진행 중</b>\n현재 {count}개 처리 완료!"
                    except Exception:
                        pass

            if send_allowed:
                try:
                    # 봇 비서 인스턴스가 켜져 있다면, 봇 비서의 텔레그램 클라이언트를 활용 (HTML 포맷팅 및 에러/경고 기호 최적화)
                    from backend.telegram_assistant import get_telegram_assistant
                    assistant = get_telegram_assistant()
                    if assistant and assistant.running and assistant.bot:
                        emoji_prefix = "❌ " if level == "ERROR" else "⚠️ " if level == "WARNING" else "✅ "
                        assistant.send_push_notification(f"<b>Winwin Crawler 알림</b>\n\n{emoji_prefix}{text}")
                    else:
                        import requests
                        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                        emoji_prefix = "❌ " if level == "ERROR" else "⚠️ " if level == "WARNING" else "✅ "
                        payload = {
                            "chat_id": self.telegram_chat_id,
                            "text": f"<b>Winwin Crawler 알림</b>\n\n{emoji_prefix}{text}",
                            "parse_mode": "HTML"
                        }
                        requests.post(url, json=payload, timeout=5)
                except Exception:
                    pass

    def update_progress(self, val, maximum, current_item=""):
        with self.lock:
            self.progress["val"] = val
            self.progress["max"] = maximum
            if current_item:
                self.progress["current_item"] = current_item
        self.notify_update()

    # ─── chromedriver 파일 충돌 방지 ─────────────────────────────────────────
    def _fix_chromedriver_conflict(self):
        """undetected_chromedriver cache/profile cleanup without forcing a fresh network download."""
        import subprocess
        uc_dir = os.path.join(os.environ.get("APPDATA", ""), "undetected_chromedriver")
        target_exe = os.path.join(uc_dir, "undetected_chromedriver.exe")
        if os.path.exists(target_exe):
            try:
                size = os.path.getsize(target_exe)
                force_clean = os.environ.get("WINWIN_FORCE_CLEAN_CHROMEDRIVER", "").strip() == "1"
                if force_clean or size < 1024 * 1024:
                    os.remove(target_exe)
                    self.add_log("🧹 손상된 chromedriver 캐시 제거 완료")
                else:
                    self.add_log("✅ 기존 chromedriver 캐시 유지 (네트워크 재다운로드 방지)", "INFO")
            except Exception:
                pass  # 사용 중이면 무시

        # 현재 프로젝트(winwin크롤러2)의 user-data-dir를 점유하고 있는 좀비 chrome.exe 안전 종료
        try:
            import psutil
            killed = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == 'chrome.exe':
                        cmdline = proc.info['cmdline']
                        if cmdline:
                            cmdline_str = " ".join(cmdline)
                            if "winwin크롤러2" in cmdline_str:
                                proc.kill()
                                killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            if killed:
                self.add_log(f"🧹 충돌 방지를 위해 이전 크롤러 크롬 프로세스({killed}개) 종료 완료")
        except Exception:
            pass

    # ─── 로그인 상태 자동 감지 ─────────────────────────────────────────────
    def _kill_chrome_for_profile(self, target_profile_dir):
        """Close Chrome processes that are holding a specific automation profile."""
        # 0. 선제적인 드라이버 및 좀비 클린업
        try:
            import subprocess
            for proc_name in ["chromedriver.exe", "undetected_chromedriver.exe"]:
                subprocess.run(
                    f"taskkill /F /IM {proc_name}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception:
            pass

        try:
            import psutil
            target_abs = os.path.normcase(os.path.abspath(target_profile_dir))
            target_name = os.path.basename(target_abs)
            
            killed = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == 'chrome.exe':
                        cmdline = proc.info['cmdline']
                        if cmdline:
                            cmdline_str = " ".join(cmdline)
                            cmdline_norm = os.path.normcase(cmdline_str)
                            if target_abs in cmdline_norm or target_name in cmdline_norm:
                                proc.kill()
                                killed += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            if killed:
                self.add_log(f"Chrome processes closed for profile: {killed}", "INFO")
        except Exception as e:
            self.add_log(f"Chrome profile cleanup check failed: {str(e)[:80]}", "WARNING")

    def _is_dead_driver_error(self, error):
        msg = str(error).lower()
        return any(token in msg for token in (
            "connection aborted",
            "connectionreseterror",
            "10054",
            "invalid session",
            "no such window",
            "disconnected",
            "target window already closed",
            "cannot determine loading status",
            "chrome not reachable",
            "max retries exceeded",
            "urlopen error",
            "timed out",
            "connection timed out",
        ))

    def _safe_quit_driver(self, driver, label="드라이버"):
        if not driver:
            return
        try:
            driver.quit()
            self.add_log(f"🧹 기존 {label} 종료 완료", "INFO")
        except Exception:
            pass

    def _check_login_status(self, driver, platform: str) -> bool:
        """브라우저가 열린 후, 이미 로그인된 상태인지 확인한다."""
        import time
        time.sleep(3)  # 페이지 로딩 대기
        try:
            current_url = driver.current_url
            if platform in ("카카오스토리", "kakao"):
                # 카카오스토리 메인 페이지로 리다이렉트 되었으면 이미 로그인 상태
                if "story.kakao.com" in current_url and "accounts.kakao.com" not in current_url:
                    return True
            elif platform in ("네이버 밴드", "band"):
                current_url_lower = (current_url or "").lower()
                # home/about/intro/auth 는 글쓰기 가능한 로그인 완료 상태가 아닙니다.
                if (
                    "band.us/home" in current_url_lower
                    or "band.us/about" in current_url_lower
                    or "auth.band.us" in current_url_lower
                ):
                    return False
                if "band.us/band" in current_url_lower or "band.us/feed" in current_url_lower:
                    return True
        except Exception:
            pass
        return False

    def _get_band_target_url(self) -> str:
        """업로드용 기본 밴드 그룹 URL.

        환경변수 WINWIN_BAND_TARGET_URL 또는 WINWIN_BAND_NO로 덮어쓸 수 있습니다.
        현재 운영 밴드 번호는 사용자가 알려준 98026564를 기본값으로 사용합니다.
        """
        target_url = os.environ.get("WINWIN_BAND_TARGET_URL", "").strip()
        if target_url:
            return target_url
        band_no = os.environ.get("WINWIN_BAND_NO", "").strip() or "98026564"
        return f"https://www.band.us/band/{band_no}/post"

    @staticmethod
    def _is_blank_or_newtab_url(url: str) -> bool:
        url = (url or "").lower()
        return (
            not url
            or url.startswith("about:blank")
            or "chrome://new-tab-page" in url
            or "google.com/_/chrome/newtab" in url
        )

    @staticmethod
    def _is_band_public_landing_url(url: str) -> bool:
        url = (url or "").lower()
        return (
            "band.us/about" in url
            or "about.band.us" in url
            or url.rstrip("/") in ("https://band.us", "https://www.band.us")
            or "band.us/home" in url
        )

    @staticmethod
    def _is_band_group_url(url: str) -> bool:
        url = (url or "").lower()
        return "band.us/band/" in url or "band.us/feed" in url

    def _band_has_write_button(self, driver) -> bool:
        """현재 밴드 페이지에 글쓰기 버튼 후보가 보이는지 확인한다."""
        from selenium.webdriver.common.by import By
        selectors = [
            (By.XPATH, "//button[contains(normalize-space(.),'글쓰기')]"),
            (By.XPATH, "//span[contains(normalize-space(.),'글쓰기')]/ancestor::button[1]"),
            (By.XPATH, "//a[contains(normalize-space(.),'글쓰기')]"),
            (By.CSS_SELECTOR, "button.uButton._btnPostWrite"),
            (By.CSS_SELECTOR, "button[data-uiselector='btnPostWrite']"),
            (By.CSS_SELECTOR, "button[class*='_btnPostWrite'], button[class*='uWriteBtn']"),
            (By.CSS_SELECTOR, ".uButtonWrite button, .writeBtn button"),
        ]
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        for by, selector in selectors:
            try:
                for elem in driver.find_elements(by, selector):
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            return True
                    except Exception:
                        return True
            except Exception:
                pass
        return False

    def _ensure_band_group_page(self, driver, timeout: int = 18) -> bool:
        """밴드 업로드 전에 반드시 그룹 내부/글쓰기 가능 상태로 이동한다."""
        target_url = self._get_band_target_url()
        candidates = []
        try:
            current_url = driver.current_url or ""
            if current_url:
                candidates.append(current_url)
        except Exception:
            current_url = ""
        candidates.extend([target_url, target_url.replace("/post", ""), "https://www.band.us/feed"])

        seen = set()
        for url in candidates:
            if not url or url in seen:
                continue
            seen.add(url)
            try:
                if self._is_blank_or_newtab_url(url) or not self._is_band_group_url(url):
                    driver.get(url)
                elif url != current_url:
                    driver.get(url)
                end_at = time.time() + timeout
                while time.time() < end_at:
                    cur = driver.current_url or ""
                    if self._is_band_public_landing_url(cur) or "auth.band.us" in cur.lower():
                        break
                    if self._is_band_group_url(cur) and self._band_has_write_button(driver):
                        self.add_log(f"✅ 밴드 그룹 페이지 확인: {cur[:100]}", "INFO")
                        return True
                    time.sleep(0.4)
            except Exception as e:
                self.add_log(f"⚠️ 밴드 그룹 이동 실패: {str(e)[:100]}", "WARNING")

        try:
            last_url = driver.current_url
        except Exception:
            last_url = ""
        self.add_log(
            f"❌ 밴드 그룹 내부로 이동하지 못했습니다. 현재 URL: {last_url[:120]} / 목표: {target_url}",
            "ERROR",
        )
        return False

    # ─── 자동 로그인 (카카오스토리) ────────────────────────────────────────────
    def _auto_login_kakao(self, driver, credentials: dict):
        """카카오 로그인 페이지에서 ID/PW를 자동 입력하거나 간편 로그인 계정을 선택하여 로그인한다."""
        from selenium.webdriver.common.by import By
        import time

        self.add_log(f"🤖 카카오 자동 로그인 시도: {credentials['login_id']}")
        try:
            # 로그인 폼 또는 간편 로그인 계정 선택 화면이 로딩될 때까지 멀티 감시
            login_form_selector = "input[name='loginId'], #loginId--1"
            
            start_wait = time.time()
            found_mode = None
            while time.time() - start_wait < 15:
                if self.stop_flag:
                    break
                # A: 로그인 ID 필드가 나타났는지 확인
                ids = driver.find_elements(By.CSS_SELECTOR, login_form_selector)
                if ids and any(i.is_displayed() for i in ids):
                    found_mode = "form"
                    break
                # B: 간편로그인 계정 카드가 나타났는지 확인 (1순위: span.tit_profile 직접 매칭)
                accs = []
                try:
                    for candidate in driver.find_elements(By.CSS_SELECTOR, "span.tit_profile, .tit_profile"):
                        if candidate.is_displayed() and credentials['login_id'] in candidate.text:
                            accs = [candidate]
                            break
                except Exception:
                    pass

                if not accs:
                    # 2순위: XPath 2종 교차검증
                    accs = driver.find_elements(By.XPATH, f"//*[contains(text(), '{credentials['login_id']}')] | //*[contains(normalize-space(.), '{credentials['login_id']}')]")
                
                if not accs:
                    # C: fallback - 파이썬으로 텍스트 직접 매칭 검사
                    for candidate in driver.find_elements(By.CSS_SELECTOR, "span, div, p"):
                        try:
                            if candidate.is_displayed() and credentials['login_id'] in candidate.text:
                                accs = [candidate]
                                break
                        except Exception:
                            pass
                if accs and any(a.is_displayed() for a in accs):
                    found_mode = "shortcut"
                    break
                time.sleep(0.5)

            if not found_mode:
                raise Exception("로그인 폼 또는 간편 계정 요소를 찾지 못했습니다.")

            if found_mode == "shortcut":
                self.add_log(f"📱 간편 로그인 계정 선택 화면 감지. '{credentials['login_id']}' 계정을 자동 선택합니다.")
                # 요소 재조회 및 매칭 (1순위: span.tit_profile 적용)
                accs = []
                try:
                    for candidate in driver.find_elements(By.CSS_SELECTOR, "span.tit_profile, .tit_profile"):
                        if candidate.is_displayed() and credentials['login_id'] in candidate.text:
                            accs = [candidate]
                            break
                except Exception:
                    pass
                if not accs:
                    accs = driver.find_elements(By.XPATH, f"//*[contains(text(), '{credentials['login_id']}')] | //*[contains(normalize-space(.), '{credentials['login_id']}')]")
                if not accs:
                    accs = [c for c in driver.find_elements(By.CSS_SELECTOR, "span, div, p") if credentials['login_id'] in c.text and c.is_displayed()]
                
                clicked = False
                for acc in accs:
                    if acc.is_displayed():
                        # 상위 5단계 부모 노드 중 클릭 가능한 HTML 태그/속성을 색출해 기동
                        curr = acc
                        for _ in range(5):
                            try:
                                tag_name = curr.tag_name.lower()
                                if tag_name in ["button", "a", "li"] or curr.get_attribute("role") == "button":
                                    driver.execute_script("arguments[0].click();", curr)
                                    clicked = True
                                    break
                            except Exception:
                                pass
                            try:
                                curr = curr.find_element(By.XPATH, "..")
                            except Exception:
                                break
                        
                        if clicked:
                            break
                        
                        # 마지막 수단으로 요소 자체를 직접 클릭
                        try:
                            driver.execute_script("arguments[0].click();", acc)
                            clicked = True
                            break
                        except Exception:
                            pass
                if not clicked:
                    raise Exception("간편 로그인 계정 요소를 클릭하는 데 실패했습니다.")
                
            elif found_mode == "form":
                # ID 입력
                try:
                    id_field = driver.find_element(By.ID, "loginId--1")
                except Exception:
                    id_field = driver.find_element(By.CSS_SELECTOR, "input[name='loginId']")
                id_field.clear()
                id_field.send_keys(credentials['login_id'])
                time.sleep(0.5)

                # PW 입력
                try:
                    pw_field = driver.find_element(By.ID, "password--2")
                except Exception:
                    pw_field = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
                pw_field.clear()
                pw_field.send_keys(credentials['login_pw'])
                time.sleep(0.5)

                # 로그인 버튼 클릭
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, "button.btn_g.highlight.submit")
                    btn.click()
                except Exception:
                    btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                    btn.click()

            time.sleep(4)
            current_url = driver.current_url
            if "story.kakao.com" in current_url and "accounts" not in current_url:
                self.add_log("🎉 카카오 자동 로그인 성공!")
            else:
                self.add_log("⚠️ 자동 입력 완료. 2단계 인증 등이 필요할 수 있습니다.")
        except Exception as e:
            self.add_log(f"⚠️ 카카오 자동 로그인 실패 (수동으로 진행해주세요): {str(e)[:80]}")
            # ★ 100% 확실한 Heartbeat Probe 검사로 세션 생존 판정 오차 제로화
            is_dead = False
            try:
                _ = driver.title
            except Exception:
                is_dead = True

            if is_dead:
                self.add_log("⚠️ 드라이버 세션이 손상된 것으로 감지되어 즉시 드라이버 자원을 해제합니다.", "WARNING")
                try:
                    driver.quit()
                except Exception:
                    pass
                if getattr(self, "source_driver", None) == driver:
                    self.source_driver = None
                if getattr(self, "_source_crawler", None) and getattr(self._source_crawler, "driver", None) == driver:
                    self._source_crawler.driver = None

    # ─── 자동 로그인 (네이버 밴드) ─────────────────────────────────────────────
    def _auto_login_band(self, driver, credentials: dict):
        """밴드 로그인(이메일 계정)에서 ID/PW를 자동 입력한다."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time
        from selenium.webdriver.common.keys import Keys

        self.add_log(f"🤖 밴드(이메일) 자동 로그인 시도: {credentials['login_id']}")
        try:
            # 밴드 홈 대기
            time.sleep(2)
            current_url = driver.current_url

            def _is_blank_or_newtab(url):
                return self._is_blank_or_newtab_url(url)

            def _switch_best_window(prefer_inputs=None):
                """Use the Band/auth tab, not a stray blank Chrome new tab."""
                try:
                    handles = driver.window_handles
                    if not handles:
                        return False

                    scored = []
                    original = driver.current_window_handle
                    for order, handle in enumerate(handles):
                        try:
                            driver.switch_to.window(handle)
                            url = driver.current_url or ""
                            title = driver.title or ""
                            score = order
                            lowered = (url + " " + title).lower()
                            if "band.us" in lowered or "band.com" in lowered:
                                score += 100
                            if "login" in lowered or "auth" in lowered:
                                score += 30
                            if _is_blank_or_newtab(url):
                                score -= 80
                            if prefer_inputs:
                                for by, selector in prefer_inputs:
                                    try:
                                        if driver.find_elements(by, selector):
                                            score += 200
                                            break
                                    except Exception:
                                        pass
                            scored.append((score, handle, url))
                        except Exception:
                            pass

                    if scored:
                        scored.sort(key=lambda item: item[0], reverse=True)
                        driver.switch_to.window(scored[0][1])
                        return True
                    driver.switch_to.window(original)
                    return False
                except Exception:
                    return False

            def _switch_latest_window():
                return _switch_best_window()

            def _click_by_selectors(selectors, timeout=8):
                last_error = None
                end_at = time.time() + timeout
                while time.time() < end_at:
                    handles = []
                    try:
                        handles = list(driver.window_handles)
                    except Exception:
                        pass
                    if not handles:
                        handles = [None]

                    for handle in handles:
                        try:
                            if handle:
                                driver.switch_to.window(handle)
                            if _is_blank_or_newtab(driver.current_url):
                                continue
                        except Exception:
                            continue

                        for by, selector in selectors:
                            try:
                                elems = driver.find_elements(by, selector)
                                for elem in elems:
                                    try:
                                        if not elem.is_displayed():
                                            continue
                                    except Exception:
                                        pass
                                    try:
                                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
                                        time.sleep(0.15)
                                        elem.click()
                                    except Exception:
                                        try:
                                            driver.execute_script("arguments[0].click();", elem)
                                        except Exception as e:
                                            last_error = e
                                            continue
                                    time.sleep(0.8)
                                    _switch_best_window()
                                    return True
                            except Exception as e:
                                last_error = e
                    time.sleep(0.35)
                if last_error:
                    self.add_log(f"밴드 클릭 후보 실패: {str(last_error)[:80]}", "WARNING")
                return False

            def _find_input(selectors, timeout=12):
                end_at = time.time() + timeout
                while time.time() < end_at:
                    try:
                        handles = list(driver.window_handles)
                    except Exception:
                        handles = []
                    if not handles:
                        handles = [None]

                    for handle in handles:
                        try:
                            if handle:
                                driver.switch_to.window(handle)
                            if _is_blank_or_newtab(driver.current_url):
                                continue
                        except Exception:
                            continue

                        search_contexts = [None]
                        try:
                            driver.switch_to.default_content()
                            search_contexts.extend(driver.find_elements(By.CSS_SELECTOR, "iframe, frame"))
                        except Exception:
                            pass

                        for frame in search_contexts:
                            try:
                                if frame is None:
                                    driver.switch_to.default_content()
                                else:
                                    driver.switch_to.default_content()
                                    driver.switch_to.frame(frame)
                            except Exception:
                                continue

                            for by, selector in selectors:
                                try:
                                    elems = driver.find_elements(by, selector)
                                    for elem in elems:
                                        try:
                                            if elem.is_displayed() and elem.is_enabled():
                                                return elem
                                        except Exception:
                                            return elem
                                except Exception:
                                    pass
                    time.sleep(0.35)
                return None

            def _go_direct_band_login():
                """소개/빈 탭에 멈춘 경우 밴드 인증 페이지로 직접 이동한다."""
                for url in (
                    "https://auth.band.us/email_login",
                    "https://auth.band.us/",
                ):
                    try:
                        driver.get(url)
                        time.sleep(2.0)
                        _switch_best_window([
                            (By.ID, "input_email"),
                            (By.CSS_SELECTOR, "input[type='email']"),
                            (By.CSS_SELECTOR, "input[name*='email' i]"),
                            (By.CSS_SELECTOR, "a[href*='email_login']"),
                        ])
                        cur = driver.current_url or ""
                        if "auth.band.us" in cur.lower():
                            self.add_log(f"✅ 밴드 인증 페이지 직접 이동: {cur[:100]}")
                            return True
                    except Exception as e:
                        self.add_log(f"⚠️ 밴드 인증 URL 이동 실패: {str(e)[:80]}", "WARNING")
                return False

            # about/intro 또는 빈 탭은 로그인 링크가 안 잡히는 경우가 많아 인증 페이지를 먼저 보장한다.
            current_url = driver.current_url
            if _is_blank_or_newtab(current_url) or self._is_band_public_landing_url(current_url):
                _go_direct_band_login()

            # 1. 메인 '로그인' 버튼 클릭. 이미 auth 페이지면 생략한다.
            current_url = (driver.current_url or "").lower()
            if "auth.band.us" in current_url:
                login_clicked = True
            else:
                login_clicked = _click_by_selectors([
                    (By.CSS_SELECTOR, "a.login._loginLink"),
                    (By.CSS_SELECTOR, "a[href*='login']"),
                    (By.XPATH, "//a[contains(normalize-space(.), '로그인')]"),
                    (By.XPATH, "//button[contains(normalize-space(.), '로그인')]"),
                ], timeout=8)
            if login_clicked:
                self.add_log("✅ 밴드 로그인 버튼 클릭 완료")
                time.sleep(1.2)
            else:
                self.add_log("⚠️ '로그인' 링크를 찾지 못해 밴드 인증 페이지 직접 이동을 재시도합니다.")
                _go_direct_band_login()

            # 2. '이메일로 로그인' 버튼 클릭
            email_login_clicked = _click_by_selectors([
                (By.CSS_SELECTOR, "a#email_login_a"),
                (By.CSS_SELECTOR, "a[href*='email_login']"),
                (By.XPATH, "//span[contains(@class, 'buttonText') and contains(normalize-space(.), '이메일로 로그인')]/ancestor::*[self::button or self::a][1]"),
                (By.XPATH, "//span[contains(normalize-space(.), '이메일로 로그인')]/ancestor::*[self::button or self::a][1]"),
                (By.XPATH, "//*[contains(normalize-space(.), '이메일로 로그인') and (self::button or self::a)]"),
                (By.CSS_SELECTOR, "button[aria-label*='이메일'], a[aria-label*='이메일']"),
            ], timeout=10)
            if not email_login_clicked:
                # auth 루트의 구조가 바뀌어 버튼을 못 잡아도 email_login URL 자체는 안정적인 편이라 직접 이동한다.
                try:
                    driver.get("https://auth.band.us/email_login")
                    time.sleep(2.0)
                    email_login_clicked = True
                except Exception:
                    pass
            if email_login_clicked:
                self.add_log("✅ '이메일로 로그인' 버튼 클릭 완료")
                time.sleep(2.0)
                _switch_best_window([
                    (By.ID, "input_email"),
                    (By.CSS_SELECTOR, "input[type='email']"),
                    (By.CSS_SELECTOR, "input[name*='email' i]"),
                    (By.CSS_SELECTOR, "input[autocomplete='username']"),
                    (By.CSS_SELECTOR, "input[type='text']"),
                ])
            else:
                self.add_log("⚠️ '이메일로 로그인' 버튼을 찾지 못했습니다. 수동으로 진행해주세요.")
                return

            # 3. 이메일 입력 후 ENTER
            try:
                from selenium.webdriver.common.action_chains import ActionChains

                email_field = _find_input([
                    (By.ID, "input_email"),
                    (By.CSS_SELECTOR, "input[type='email']"),
                    (By.CSS_SELECTOR, "input[name='email']"),
                    (By.CSS_SELECTOR, "input[name*='email' i]"),
                    (By.CSS_SELECTOR, "input[id*='email' i]"),
                    (By.CSS_SELECTOR, "input[autocomplete='username']"),
                    (By.CSS_SELECTOR, "input[placeholder*='이메일']"),
                    (By.CSS_SELECTOR, "input[placeholder*='Email' i]"),
                    (By.CSS_SELECTOR, "input[type='text']"),
                ], timeout=15)
                if not email_field:
                    self.add_log(f"⚠️ 이메일 입력창 탐색 실패. 현재 URL: {driver.current_url[:120]}")
                    return
                # JS로 확실하게 필드 클리어 후 입력
                email_field.click()
                time.sleep(0.3)
                driver.execute_script("arguments[0].value = '';  arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", email_field)
                time.sleep(0.2)
                email_field.send_keys(credentials['login_id'])
                time.sleep(0.5)
                email_field.send_keys(Keys.ENTER)
                time.sleep(2.5)  # 비밀번호 페이지 전환 대기 충분히
            except Exception as e:
                self.add_log(f"⚠️ '이메일' 입력/전송 실패: {str(e)[:120]} / 현재 URL: {driver.current_url[:120]}")
                return

            # 4. 비밀번호 입력 후 ENTER (한 글자씩 타이핑 — SPA 글자 누락 방지)
            try:
                pw_field = _find_input([
                    (By.ID, "pw"),
                    (By.ID, "input_password"),
                    (By.CSS_SELECTOR, "input[type='password']"),
                    (By.CSS_SELECTOR, "input[name='password']"),
                    (By.CSS_SELECTOR, "input[name*='pw' i]"),
                    (By.CSS_SELECTOR, "input[id*='pw' i]"),
                    (By.CSS_SELECTOR, "input[autocomplete='current-password']"),
                ], timeout=15)
                if not pw_field:
                    self.add_log(f"⚠️ 비밀번호 입력창 탐색 실패. 현재 URL: {driver.current_url[:120]}")
                    return

                # JS로 확실하게 필드 클리어
                pw_field.click()
                time.sleep(0.3)
                driver.execute_script("arguments[0].value = '';  arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", pw_field)
                time.sleep(0.2)

                # ActionChains로 한 글자씩 입력 (SPA 이벤트 핸들러 확실 반응)
                password = credentials['login_pw']
                actions = ActionChains(driver)
                actions.click(pw_field)
                for char in password:
                    actions.send_keys(char)
                    actions.pause(0.05)
                actions.perform()
                time.sleep(0.5)

                # 입력값 검증 (비밀번호 길이 비교)
                try:
                    entered_len = driver.execute_script("return arguments[0].value.length;", pw_field)
                    if entered_len != len(password):
                        self.add_log(f"⚠️ 비밀번호 길이 불일치 (입력:{entered_len} vs 원본:{len(password)}), 재입력...")
                        driver.execute_script("arguments[0].value = '';  arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", pw_field)
                        time.sleep(0.2)
                        pw_field.click()
                        time.sleep(0.1)
                        for char in password:
                            pw_field.send_keys(char)
                            time.sleep(0.08)
                        time.sleep(0.3)
                except Exception:
                    pass  # 검증 실패해도 진행

                pw_field.send_keys(Keys.ENTER)
            except Exception as e:
                self.add_log(f"⚠️ '비밀번호' 입력 실패: {str(e)[:100]}. 수동으로 진행해주세요.")
                return

            time.sleep(3)
            current_url = driver.current_url
            if self._check_login_status(driver, "band") or self._ensure_band_group_page(driver, timeout=12):
                self.add_log("🎉 밴드(이메일) 자동 로그인 성공!")
            else:
                self.add_log(f"⚠️ 자동 입력 완료. 추가 인증 또는 밴드 그룹 권한 확인이 필요합니다. 현재 URL: {current_url[:120]}")
        except Exception as e:
            self.add_log(f"⚠️ 밴드 자동 로그인 실패 (수동으로 진행해주세요): {str(e)[:80]}")

    # ─── 브라우저 열기 (로그인) ─────────────────────────────────────────────
    def open_browser(self, platform: str, credentials: dict = None, ghost_mode: bool = False):
        if not hasattr(self, 'browser_open_lock'):
            self.browser_open_lock = threading.Lock()
        self.add_log(f"⏳ [{platform}] 브라우저 오픈 대기 중... (동시 실행 충돌 방지)")
        with self.browser_open_lock:
            self._locked_open_browser(platform, credentials, ghost_mode)

    def _locked_open_browser(self, platform: str, credentials: dict = None, ghost_mode: bool = False):
        """
        플랫폼별 브라우저를 열고 로그인 페이지로 이동한다.
        credentials가 제공되면 자동 로그인을 수행한다.
        프로필 폴더에 쿠키/세션을 저장하여, 두 번째부터는 자동 로그인된다.
        ghost_mode=True면 브라우저를 화면 밖(-32000, -32000)으로 이동시켜 사용자에게 보이지 않게 한다.
        """
        self.add_log(f"🔌 [{platform}] 브라우저 열기 시작...")

        # chromedriver 파일 충돌 방지 (WinError 183 예방)
        self._fix_chromedriver_conflict()

        try:
            if platform in ("카카오스토리", "kakao"):
                try:
                    from platforms.kakao.crawler import KakaoCrawler
                except ImportError:
                    from backend.platforms.kakao.crawler import KakaoCrawler
                crawler = KakaoCrawler()
                crawler.set_log_func(self.add_log)

                # ★ 프로필 폴더 지정 → 프로필별 독립 세션
                if credentials:
                    safe_name = credentials['name'].replace(' ', '_')
                    profile_dir = os.path.join(_PROJECT_ROOT, f"kakao_profile_{safe_name}")
                    self.kakao_profile_name = credentials['name']
                else:
                    profile_dir = os.path.join(_PROJECT_ROOT, "kakao_profile_optimized")
                    self.kakao_profile_name = "카카오계정(기본)"
                os.makedirs(profile_dir, exist_ok=True)

                # ── 이전 카카오 드라이버 정리 (메모리 및 세션 락 해제) ──
                if getattr(self, "source_driver", None):
                    self._safe_quit_driver(self.source_driver, "카카오 소스 드라이버")
                self.source_driver = None
                self._source_crawler = None
                time.sleep(0.8)

                # ── 예외 상황에서의 자원 안전 회수를 위한 대형 try-except 가드 ──
                try:
                    def _kill_chrome_for_profile(target_profile_dir):
                        # 0. 선제적인 드라이버 및 좀비 클린업
                        try:
                            import subprocess
                            for proc_name in ["chromedriver.exe", "undetected_chromedriver.exe"]:
                                subprocess.run(
                                    f"taskkill /F /IM {proc_name}",
                                    shell=True,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL
                                )
                        except Exception:
                            pass

                        # 1. SingletonLock 및 lock 파일 수동 강제 삭제
                        if target_profile_dir and os.path.isdir(target_profile_dir):
                            lock_file = os.path.join(target_profile_dir, "SingletonLock")
                            lock_file2 = os.path.join(target_profile_dir, "lock")
                            lock_file3 = os.path.join(target_profile_dir, "Default", "SingletonLock")
                            lock_file4 = os.path.join(target_profile_dir, "Default", "lock")
                            for lf in [lock_file, lock_file2, lock_file3, lock_file4]:
                                try:
                                    if os.path.exists(lf) or os.path.islink(lf):
                                        os.remove(lf)
                                        self.add_log(f"🧹 프로필 락 파일 제거 완료: {os.path.basename(lf)}")
                                except Exception:
                                    pass

                        # 2. 한글 인코딩 대응 크롬 좀비 정리 (psutil 사용)
                        try:
                            import psutil
                            target_abs = os.path.normcase(os.path.abspath(target_profile_dir))
                            target_name = os.path.basename(target_abs)
                            
                            killed = 0
                            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                                try:
                                    if proc.info['name'] and proc.info['name'].lower() == 'chrome.exe':
                                        cmdline = proc.info['cmdline']
                                        if cmdline:
                                            cmdline_str = " ".join(cmdline)
                                            cmdline_norm = os.path.normcase(cmdline_str)
                                            if target_abs in cmdline_norm or target_name in cmdline_norm:
                                                proc.kill()
                                                killed += 1
                                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                    continue
                            if killed:
                                self.add_log(f"카카오 프로필 Chrome 프로세스 정리: {killed}개", "INFO")
                        except Exception as e:
                            self.add_log(f"카카오 프로필 Chrome 정리 확인 실패: {str(e)[:80]}", "WARNING")
                    self.add_log(f"📁 카카오 프로필 저장 경로: {profile_dir}")

                    kakao_url = "https://accounts.kakao.com/login?continue=https://story.kakao.com/"

                    _kill_chrome_for_profile(profile_dir)
                    time.sleep(1.0)
                    options = crawler._build_chrome_options(profile_dir=profile_dir)
                    # Chrome 새 탭/복원 탭이 URL 이동을 먹는 경우가 있어 시작 URL도 함께 주입한다.
                    try:
                        options.add_argument(kakao_url)
                    except Exception:
                        pass
                    crawler.driver = crawler._create_driver(options, profile_dir=profile_dir)

                    # ★ 크롬 초기화 완료 대기 (프로필 복원 포함)
                    time.sleep(3)

                    # ★ 창 크기 및 위치 보정
                    if ghost_mode:
                        try:
                            crawler.driver.set_window_position(-32000, -32000)
                            crawler.driver.set_window_size(1500, 900)
                        except Exception:
                            pass
                    else:
                        try:
                            crawler.driver.set_window_position(0, 0)
                            crawler.driver.set_window_size(800, 700)
                        except Exception:
                            pass

                    def _is_kakao_url(url):
                        url = (url or "").lower()
                        return "accounts.kakao.com" in url or "story.kakao.com" in url

                    def _is_dead_session_error(error):
                        msg = str(error).lower()
                        return any(token in msg for token in [
                            "invalid session",
                            "no such window",
                            "target window already closed",
                            "browser has closed",
                            "session deleted",
                            "not connected to devtools",
                            "disconnected",
                        ])

                    def _open_kakao_login_page(driver, retries=3):
                        """죽은/복원 탭을 피해서 카카오 로그인 URL을 살아있는 탭에 연다."""
                        from selenium.webdriver.common.keys import Keys
                        from selenium.webdriver.common.action_chains import ActionChains

                        last_url = ""

                        def _wait_for_kakao_url(timeout=4):
                            nonlocal last_url
                            end_at = time.time() + timeout
                            while time.time() < end_at:
                                try:
                                    last_url = driver.current_url
                                    if _is_kakao_url(last_url):
                                        return True
                                except Exception as e:
                                    if _is_dead_session_error(e):
                                        raise
                                time.sleep(0.2)
                            return False

                        def _navigate_current_tab():
                            """일반 get, CDP, 주소창 입력 순서로 현재 탭 이동을 시도한다."""
                            nonlocal last_url
                            nav_errors = []

                            for method_name, nav_fn in [
                                ("driver.get", lambda: driver.get(kakao_url)),
                                ("cdp.navigate", lambda: driver.execute_cdp_cmd("Page.navigate", {"url": kakao_url})),
                                ("address-bar", lambda: ActionChains(driver)
                                    .key_down(Keys.CONTROL).send_keys("l").key_up(Keys.CONTROL)
                                    .send_keys(kakao_url).send_keys(Keys.ENTER).perform()),
                            ]:
                                try:
                                    nav_fn()
                                    if _wait_for_kakao_url(timeout=4):
                                        return True
                                except Exception as e:
                                    nav_errors.append(f"{method_name}: {str(e)[:50]}")
                                    if _is_dead_session_error(e):
                                        raise

                            try:
                                last_url = driver.current_url
                            except Exception:
                                pass
                            if nav_errors:
                                self.add_log(f"⚠️ 카카오 URL 이동 방식 실패: {' / '.join(nav_errors[:2])}", "WARNING")
                            return False

                        for attempt in range(1, retries + 1):
                            try:
                                handles = list(driver.window_handles)
                                self.add_log(f"🔍 크롬 탭 {len(handles)}개 감지")
                                if not handles:
                                    raise RuntimeError("no chrome window handles")

                                active_handle = None
                                for handle in handles:
                                    try:
                                        driver.switch_to.window(handle)
                                        last_url = driver.current_url
                                        active_handle = handle
                                        break
                                    except Exception:
                                        pass
                                if not active_handle:
                                    raise RuntimeError("no alive chrome tab")

                                try:
                                    if ghost_mode:
                                        driver.set_window_position(-32000, -32000)
                                        driver.set_window_size(1500, 900)
                                    else:
                                        driver.set_window_position(40, 40)
                                        driver.set_window_size(1500, 900)
                                except Exception:
                                    pass

                                try:
                                    driver.execute_script("window.stop();")
                                except Exception:
                                    pass

                                # 1차: 현재 살아있는 탭을 직접 이동
                                if _navigate_current_tab():
                                    self.add_log(f"✅ 카카오 로그인 페이지 접속 성공: {last_url[:100]}")
                                    return True

                                # 2차: 새 탭 생성 후 이동. 기존 탭을 닫지는 않는다.
                                try:
                                    try:
                                        driver.switch_to.new_window("tab")
                                    except Exception:
                                        driver.execute_script("window.open('about:blank', '_blank');")
                                        time.sleep(0.3)
                                        driver.switch_to.window(list(driver.window_handles)[-1])
                                except Exception:
                                    driver.switch_to.window(active_handle)

                                if _navigate_current_tab():
                                    self.add_log(f"✅ 카카오 로그인 페이지 접속 성공: {last_url[:100]}")
                                    return True

                                for handle in list(driver.window_handles):
                                    try:
                                        driver.switch_to.window(handle)
                                        last_url = driver.current_url
                                        if _is_kakao_url(last_url):
                                            self.add_log(f"✅ 카카오 로그인 페이지 접속 성공: {last_url[:100]}")
                                            return True
                                    except Exception:
                                        pass

                                self.add_log(f"⚠️ 카카오 이동 재시도 {attempt}/{retries} (현재: {last_url[:80]})", "WARNING")
                            except Exception as nav_error:
                                self.add_log(f"⚠️ 카카오 탭 이동 오류 {attempt}/{retries}: {str(nav_error)[:80]}", "WARNING")
                                if _is_dead_session_error(nav_error):
                                    raise
                            time.sleep(1)
                        self.add_log(f"❌ 카카오 로그인 페이지로 이동하지 못했습니다. 마지막 URL: {last_url[:120]}", "ERROR")
                        return False

                    session_alive = True
                    try:
                        if not _open_kakao_login_page(crawler.driver):
                            session_alive = False
                            self.add_log("⚠️ 카카오 로그인 페이지 이동 실패 → 드라이버 재생성을 시도합니다.", "WARNING")
                    except Exception as e:
                        err_msg = str(e).lower()
                        if _is_dead_session_error(e):
                            session_alive = False
                            self.add_log(f"⚠️ 세션 무효화 감지: {str(e)[:80]}")
                        else:
                            self.add_log(f"⚠️ 탭 정리 중 오류: {str(e)[:80]}")
                            session_alive = False

                    # ★ 세션이 죽은 경우 → 드라이버 재생성 (안전 fallback)
                    if not session_alive:
                        self.add_log("🔄 세션 손실 → 드라이버를 다시 생성합니다...")
                        try:
                            crawler.driver.quit()
                        except Exception:
                            pass
                        time.sleep(1)
                        options = crawler._build_chrome_options(profile_dir=profile_dir)
                        try:
                            options.add_argument(kakao_url)
                        except Exception:
                            pass
                        crawler.driver = crawler._create_driver(options, profile_dir=profile_dir)
                        time.sleep(3)
                        try:
                            # 새 드라이버에서 카카오 URL로 직접 이동
                            if not _open_kakao_login_page(crawler.driver):
                                self._safe_quit_driver(crawler.driver, "실패한 카카오 드라이버")
                                return False
                            self.add_log(f"✅ 드라이버 재생성 후 카카오 페이지 접속 성공")
                        except Exception as e2:
                            self.add_log(f"❌ 드라이버 재생성 후에도 실패: {e2}")
                            self._safe_quit_driver(crawler.driver, "실패한 카카오 드라이버")
                            return False

                    self.source_driver = crawler.driver
                    self._source_crawler = crawler

                    # ★ 로그인 상태 자동 감지
                    if self._check_login_status(crawler.driver, platform):
                        self.add_log("🎉 저장된 세션으로 자동 로그인 성공! (수동 로그인 불필요)")
                    elif credentials:
                        self._auto_login_kakao(crawler.driver, credentials)
                    else:
                        self.add_log("✅ 카카오스토리 로그인 페이지가 열렸습니다. 직접 로그인해주세요.")
                        self.add_log("💡 로그인하시면 다음부터는 자동으로 로그인됩니다.")
                except Exception as e:
                    self.add_log(f"❌ 카카오 브라우저 기동 및 로그인 시도 중 치명적 오류 발생: {e}", "ERROR")
                    if hasattr(crawler, 'driver') and crawler.driver:
                        self._safe_quit_driver(crawler.driver, "오류가 발생한 카카오 드라이버")
                    try:
                        _kill_chrome_for_profile(profile_dir)
                    except Exception:
                        pass
                    return False

            elif platform in ("네이버 밴드", "band"):
                try:
                    from platforms.band.poster import BandPoster
                except ImportError:
                    from backend.platforms.band.poster import BandPoster
                poster = BandPoster()
                poster.set_log_func(self.add_log)

                import undetected_chromedriver as uc
                import re as _re

                # ★ 프로필 폴더 지정 → 프로필별 독립 세션
                if credentials:
                    safe_name = credentials['name'].replace(' ', '_')
                    profile_dir = os.path.join(_PROJECT_ROOT, f"band_profile_{safe_name}")
                    self.band_profile_name = credentials['name']
                else:
                    profile_dir = os.path.join(_PROJECT_ROOT, "band_profile_optimized")
                    self.band_profile_name = "밴드계정(기본)"
                os.makedirs(profile_dir, exist_ok=True)
                self.add_log(f"📁 밴드 프로필 저장 경로: {profile_dir}")

                # 이전 크롬 프로세스를 강제 종료하기 전에 Python 쪽의 낡은 driver 참조도 정리합니다.
                # 죽은 driver 객체가 남아 있으면 다음 로그인 요청에서 ConnectionResetError(10054)가 납니다.
                if getattr(self, "_target_poster", None) and getattr(self._target_poster, "band_driver", None):
                    self._safe_quit_driver(self._target_poster.band_driver, "밴드 드라이버")
                if getattr(self, "target_driver", None):
                    self._safe_quit_driver(self.target_driver, "타겟 드라이버")
                self.target_driver = None
                self._target_poster = None
                time.sleep(0.8)

                # ★ 이전 세션 파일 삭제 → 탭 복원 방지 (근본 해결)
                self._kill_chrome_for_profile(profile_dir)
                time.sleep(1.0)
                detected_version = None
                try:
                    import shutil
                    for s_dir in ["Sessions", "Session Storage"]:
                        p = os.path.join(profile_dir, "Default", s_dir)
                        if os.path.exists(p):
                            shutil.rmtree(p, ignore_errors=True)
                except Exception:
                    pass

                def _build_band_options():
                    opts = uc.ChromeOptions()
                    opts.add_argument("--disable-blink-features=AutomationControlled")
                    if ghost_mode:
                        opts.add_argument("--window-position=-32000,-32000")
                        opts.add_argument("--window-size=1500,900")
                    else:
                        opts.add_argument("--start-maximized")
                    opts.add_argument(f"--user-data-dir={profile_dir}")
                    opts.add_argument("--no-first-run")
                    opts.add_argument("--no-default-browser-check")
                    opts.add_argument("--disable-session-crashed-bubble")
                    opts.add_argument("--hide-crash-restore-bubble")
                    opts.add_argument("--disable-quic")
                    apply_quiet_chrome_options(opts)
                    try:
                        opts.add_argument(self._get_band_target_url())
                    except Exception:
                        pass
                    proxy = os.environ.get("WINWIN_CHROME_PROXY", "").strip()
                    if proxy:
                        opts.add_argument(f"--proxy-server={proxy}")
                        os.environ.setdefault("HTTP_PROXY", proxy)
                        os.environ.setdefault("HTTPS_PROXY", proxy)
                        self.add_log(f"Chrome proxy enabled: {proxy}", "INFO")
                        self.add_log("Python driver-download proxy enabled from WINWIN_CHROME_PROXY", "INFO")
                    elif os.environ.get("WINWIN_CHROME_NO_PROXY", "").strip() == "1":
                        opts.add_argument("--no-proxy-server")
                        self.add_log("Chrome proxy disabled by WINWIN_CHROME_NO_PROXY", "INFO")
                    return opts

                def _get_local_chromedriver_path():
                    candidates = []
                    env_path = os.environ.get("WINWIN_CHROMEDRIVER_PATH", "").strip()
                    if env_path:
                        candidates.append(env_path)
                    candidates.append(os.path.join(os.environ.get("APPDATA", ""), "undetected_chromedriver", "undetected_chromedriver.exe"))

                    for path in candidates:
                        try:
                            if path and os.path.exists(path) and os.path.getsize(path) > 1024 * 1024:
                                return path
                        except Exception:
                            pass
                    return ""

                def _launch_band_driver(opts, version=None, retries=2):
                    last_error = None
                    for attempt in range(retries + 1):
                        kwargs = {"options": opts, "user_data_dir": profile_dir}
                        local_driver = _get_local_chromedriver_path()
                        if local_driver:
                            kwargs["driver_executable_path"] = local_driver
                            self.add_log(f"✅ 로컬 chromedriver 사용: {local_driver}", "INFO")
                        if version:
                            kwargs["version_main"] = version
                        try:
                            try:
                                return uc.Chrome(**kwargs)
                            except TypeError:
                                kwargs.pop("user_data_dir", None)
                                return uc.Chrome(**kwargs)
                        except Exception as e:
                            last_error = e
                            if not self._is_dead_driver_error(e) or attempt >= retries:
                                if not _get_local_chromedriver_path():
                                    self.add_log(
                                        "❌ 로컬 chromedriver 캐시가 없고, 드라이버 자동 다운로드 네트워크가 끊겼습니다. "
                                        "VPN/프록시를 켠 뒤 다시 시도하거나 WINWIN_CHROMEDRIVER_PATH를 지정해주세요.",
                                        "ERROR"
                                    )
                                raise
                            self.add_log(f"⚠️ 밴드 드라이버 생성 연결 끊김 감지 → 재시도 {attempt + 1}/{retries}", "WARNING")
                            try:
                                self._kill_chrome_for_profile(profile_dir)
                            except Exception:
                                pass
                            time.sleep(2.0 + attempt)
                            opts = _build_band_options()
                    raise last_error

                def _preflight_band_network():
                    try:
                        import urllib.request
                        with urllib.request.urlopen("https://www.band.us/home", timeout=15) as resp:
                            self.add_log(f"Band network preflight OK ({resp.status})", "INFO")
                            return True
                    except Exception as e:
                        self.add_log(f"Band network preflight failed: {str(e)[:120]}", "WARNING")
                        return False

                def _open_band_home(driver):
                    try:
                        driver.set_page_load_timeout(60)
                    except Exception:
                        pass
                    last_error = None
                    target_url = self._get_band_target_url()
                    login_url = "https://auth.band.us/"
                    for url in (target_url, "https://www.band.us/feed", login_url, "https://www.band.us/home", "https://band.us/home"):
                        try:
                            self.add_log(f"Trying Band URL: {url}", "INFO")
                            driver.get(url)
                            time.sleep(3)
                            cur_url = driver.current_url
                            cur_lower = (cur_url or "").lower()
                            if self._is_band_public_landing_url(cur_url):
                                self.add_log(f"⚠️ 밴드 공개 소개/랜딩으로 이동됨: {cur_url[:100]}", "WARNING")
                                continue
                            if "auth.band.us" in cur_lower or self._is_band_group_url(cur_url):
                                self.add_log(f"Band page loaded: {cur_url[:80]}", "INFO")
                                return True
                            self.add_log(f"Unexpected Band URL after load: {cur_url[:80]}", "WARNING")
                        except Exception as e:
                            last_error = e
                            err_msg = str(e)
                            lower_msg = err_msg.lower()
                            if "invalid session" in lower_msg or "no such window" in lower_msg:
                                raise
                            if "err_connection_timed_out" in lower_msg or "timed out" in lower_msg:
                                self.add_log(f"Band URL timed out: {url}", "WARNING")
                            else:
                                self.add_log(f"Band URL failed: {url} / {err_msg[:120]}", "WARNING")
                    if last_error:
                        self.add_log(f"Band page final failure: {str(last_error)[:160]}", "ERROR")
                    return False

                _preflight_band_network()
                options = _build_band_options()

                try:
                    if detected_version:
                        poster.band_driver = _launch_band_driver(options, detected_version)
                    else:
                        poster.band_driver = _launch_band_driver(options)
                except Exception as e:
                    m = _re.search(r"Current browser version is\s+(\d+)\.", str(e))
                    if m:
                        version = int(m.group(1))
                        self.add_log(f"💡 크롬 버전 불일치 → 자동 재시도 (v{version})")

                        bad_driver = _get_local_chromedriver_path()
                        if bad_driver and os.path.exists(bad_driver):
                            try:
                                import subprocess
                                subprocess.run("taskkill /F /IM undetected_chromedriver.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                subprocess.run("taskkill /F /IM chromedriver.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                time.sleep(0.5)
                                os.remove(bad_driver)
                                self.add_log(f"🔄 구버전 드라이버 캐시 삭제 완료 (재다운로드 유도)")
                            except Exception as del_err:
                                self.add_log(f"⚠️ 구버전 드라이버 삭제 실패: {del_err}", "WARNING")

                        options2 = _build_band_options()
                        poster.band_driver = _launch_band_driver(options2, version)
                    else:
                        raise

                # ★ 크롬 초기화 완료 대기
                time.sleep(3)

                # ★ 유령 창 모드: 밴드 크롬 초기화 후 위치 보정
                if ghost_mode:
                    try:
                        poster.band_driver.set_window_position(-32000, -32000)
                        poster.band_driver.set_window_size(1500, 900)
                    except Exception:
                        pass

                # ★ 핵심 전략: 복원된 불필요한 탭을 모두 닫고, 남은 탭에서 직접 이동
                band_url = self._get_band_target_url()
                session_alive = True
                try:
                    handles = poster.band_driver.window_handles
                    self.add_log(f"🔍 크롬 탭 {len(handles)}개 감지")

                    if len(handles) > 0:
                        try:
                            poster.band_driver.switch_to.window(handles[0])
                        except Exception:
                            pass

                    if session_alive:
                        session_alive = _open_band_home(poster.band_driver)
                except Exception as e:
                    err_msg = str(e).lower()
                    if "invalid session" in err_msg or "no such window" in err_msg:
                        session_alive = False
                        self.add_log(f"⚠️ 세션 무효화 감지: {str(e)[:80]}")
                    else:
                        self.add_log(f"⚠️ 탭 정리 중 오류: {str(e)[:80]}")
                        session_alive = False

                # ★ 세션이 죽은 경우 → 드라이버 재생성 (안전 fallback)
                if not session_alive:
                    self.add_log("🔄 밴드 접속 실패 → 세션 정리 후 드라이버를 다시 생성합니다...")
                    try:
                        poster.band_driver.quit()
                    except Exception:
                        pass
                    time.sleep(1)

                    KakaoCrawler._clean_session_files(profile_dir)
                    options_new = _build_band_options()

                    try:
                        poster.band_driver = _launch_band_driver(options_new, detected_version)
                    except Exception as ver_err:
                        m = _re.search(r"Current browser version is\s+(\d+)\.", str(ver_err))
                        if m:
                            bad_driver = _get_local_chromedriver_path()
                            if bad_driver and os.path.exists(bad_driver):
                                try:
                                    import subprocess
                                    subprocess.run("taskkill /F /IM undetected_chromedriver.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                    subprocess.run("taskkill /F /IM chromedriver.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                    time.sleep(0.5)
                                    os.remove(bad_driver)
                                except:
                                    pass
                            options_retry = _build_band_options()
                            poster.band_driver = _launch_band_driver(options_retry, int(m.group(1)))
                        else:
                            raise
                    time.sleep(3)
                    try:
                        if not _open_band_home(poster.band_driver):
                            self.add_log("⚠️ 기존 밴드 프로필로 재접속 실패 → 깨끗한 임시 프로필로 재시도합니다.", "WARNING")
                            try:
                                poster.band_driver.quit()
                            except Exception:
                                pass
                            profile_dir = f"{profile_dir}_clean_test"
                            os.makedirs(profile_dir, exist_ok=True)
                            KakaoCrawler._clean_session_files(profile_dir)
                            options_clean = _build_band_options()
                            poster.band_driver = _launch_band_driver(options_clean, detected_version)
                            time.sleep(3)
                            if not _open_band_home(poster.band_driver):
                                self.add_log("❌ 깨끗한 임시 프로필에서도 밴드 페이지 접속 실패", "ERROR")
                                return False
                    except Exception as e2:
                        self.add_log(f"❌ 드라이버 재생성 후에도 실패: {e2}")
                        return False

                self.target_driver = poster.band_driver
                self._target_poster = poster

                # ★ 로그인 상태 자동 감지
                if self._check_login_status(poster.band_driver, platform):
                    self.add_log("🎉 저장된 세션으로 자동 로그인 성공! (수동 로그인 불필요)")
                elif credentials:
                    self._auto_login_band(poster.band_driver, credentials)
                else:
                    self.add_log("✅ 네이버 밴드 로그인 페이지가 열렸습니다. 직접 로그인해주세요.")
                    self.add_log("💡 로그인하시면 다음부터는 자동으로 로그인됩니다.")

            else:
                self.add_log(f"⚠️ 지원하지 않는 플랫폼: {platform}", "WARNING")

        except Exception as e:
            self.add_log(f"❌ 브라우저 열기 오류: {e}", "ERROR")
            if self._is_dead_driver_error(e):
                self._safe_quit_driver(getattr(self, "target_driver", None), "끊어진 타겟 드라이버")
                self.target_driver = None
                if getattr(self, "_target_poster", None):
                    self._safe_quit_driver(getattr(self._target_poster, "band_driver", None), "끊어진 밴드 드라이버")
                self._target_poster = None
                self.add_log("🔄 끊어진 드라이버 참조를 정리했습니다. 다시 로그인 버튼을 눌러 새 세션을 생성하세요.", "WARNING")
            import traceback
            self.add_log(traceback.format_exc(), "ERROR")

    def diagnose_band_page(self, use_ai: bool = False) -> dict:
        """Capture a manual Band DOM diagnostic report for selector/page-change checks."""
        driver = self.target_driver or self.source_driver
        if not driver:
            return {"status": "error", "message": "열려있는 밴드 브라우저가 없습니다. 먼저 밴드 로그인을 실행해주세요."}

        try:
            current_url = driver.current_url
        except Exception:
            current_url = ""
        if "band.us" not in current_url:
            return {"status": "error", "message": f"현재 브라우저가 밴드 페이지가 아닙니다: {current_url[:120]}"}

        try:
            import pathlib
            import traceback
            now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = pathlib.Path(_PROJECT_ROOT) / "diagnostics" / "band" / now
            report_dir.mkdir(parents=True, exist_ok=True)

            selector_groups = {
                "posts": ["article._postMainWrap", "div.cCard > article.cContentsCard._postMainWrap", "div.cCard article", "li.cCard", "article"],
                "post_text": ["div.postText._postText", "div.postText", "p.listBody", "div.postBody", "button._btnMore"],
                "post_images": ["img._image", "ul.uCollage img", "div.photoGrid img", "img[src*='pstatic.net']", "img[src*='campmobile']", "button._imageButton", "button.uMoreImage", "li.more button"],
                "popup_layers": ["div[data-viewname='DPostView']", "div[data-viewname='DPostPhotoView']", "div[role='dialog']", "div[aria-modal='true']", "div.layerWrap", "div.viewer_layer", "div[class*='modal' i]", "div[class*='dialog' i]", "div[class*='popup' i]", "div[class*='layer' i]"],
                "login": ["a.login._loginLink", "span.buttonText", "input[type='email']", "#input_email", "input[type='password']", "#pw"],
            }

            selector_counts, visible_counts, samples = {}, {}, {}
            for group, selectors in selector_groups.items():
                selector_counts[group], visible_counts[group], samples[group] = {}, {}, {}
                for selector in selectors:
                    try:
                        elems = driver.find_elements("css selector", selector)
                        selector_counts[group][selector] = len(elems)
                        visible, sample_texts = 0, []
                        for elem in elems[:5]:
                            try:
                                if elem.is_displayed():
                                    visible += 1
                            except Exception:
                                pass
                            try:
                                text = (elem.text or "").strip()
                                if text:
                                    sample_texts.append(re.sub(r"\s+", " ", text)[:160])
                            except Exception:
                                pass
                        visible_counts[group][selector] = visible
                        samples[group][selector] = sample_texts
                    except Exception as e:
                        selector_counts[group][selector] = f"ERROR: {str(e)[:80]}"
                        visible_counts[group][selector] = 0
                        samples[group][selector] = []

            try:
                overlay_candidates = driver.execute_script("""
                    const vw = window.innerWidth || document.documentElement.clientWidth;
                    const vh = window.innerHeight || document.documentElement.clientHeight;
                    const nodes = Array.from(document.querySelectorAll('div, section, article, main'));
                    const out = [];
                    for (const el of nodes) {
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);
                        if (!r || r.width < 220 || r.height < 140) continue;
                        if (r.bottom < 0 || r.right < 0 || r.top > vh || r.left > vw) continue;
                        if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity || 1) < 0.2) continue;
                        const z = parseInt(s.zIndex, 10);
                        const text = (el.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 220);
                        const imgs = el.querySelectorAll("img[src*='pstatic.net'], img[src*='campmobile'], [style*='pstatic.net'], [style*='campmobile']").length;
                        const buttons = el.querySelectorAll('button, a').length;
                        const likely = s.position === 'fixed' || s.position === 'absolute' || (Number.isFinite(z) && z >= 10);
                        if (!likely && imgs === 0 && text.length < 20) continue;
                        out.push({
                            tag: el.tagName, id: el.id || '', className: String(el.className || '').slice(0, 180),
                            position: s.position, zIndex: Number.isFinite(z) ? z : null,
                            rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
                            imageCount: imgs, buttonCount: buttons, textSample: text
                        });
                    }
                    out.sort((a, b) => (b.imageCount * 100000 + b.rect.w * b.rect.h) - (a.imageCount * 100000 + a.rect.w * a.rect.h));
                    return out.slice(0, 20);
                """)
            except Exception:
                overlay_candidates = []

            screenshot_path = report_dir / "screenshot.png"
            html_path = report_dir / "page.html"
            report_path = report_dir / "report.json"

            try:
                driver.save_screenshot(str(screenshot_path))
            except Exception:
                screenshot_path = None
            try:
                html_path.write_text(driver.page_source or "", encoding="utf-8")
            except Exception:
                html_path = None

            report = {
                "status": "success",
                "created_at": now,
                "url": current_url,
                "title": getattr(driver, "title", ""),
                "selector_counts": selector_counts,
                "visible_counts": visible_counts,
                "samples": samples,
                "overlay_candidates": overlay_candidates,
                "files": {
                    "report": str(report_path),
                    "screenshot": str(screenshot_path) if screenshot_path else "",
                    "html": str(html_path) if html_path else "",
                },
                "ai_summary": "",
            }

            if use_ai:
                report["ai_summary"] = self._summarize_band_diagnostic_with_ai(report)

            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.add_log(f"🧪 밴드 페이지 진단 리포트 저장 완료: {report_path}", "INFO", False)
            if report.get("ai_summary"):
                self.add_log(f"🤖 밴드 진단 AI 요약: {report['ai_summary'][:180]}", "INFO", False)
            return report
        except Exception as e:
            return {"status": "error", "message": str(e), "traceback": traceback.format_exc() if "traceback" in locals() else ""}

    def _summarize_band_diagnostic_with_ai(self, report: dict) -> str:
        """Optional Gemini summary. Fails closed so diagnostics still work without AI."""
        try:
            from backend.secret_store import get_secret
        except ImportError:
            try:
                from secret_store import get_secret
            except ImportError:
                get_secret = lambda *_args, **_kwargs: ""

        api_key = get_secret("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            env_path = os.path.join(_PROJECT_ROOT, ".env")
            try:
                if os.path.exists(env_path):
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("GEMINI_API_KEY="):
                                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                                break
            except Exception:
                pass
        if not api_key:
            return "AI 요약 생략: GEMINI_API_KEY가 설정되어 있지 않습니다."

        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            compact = {
                "url": report.get("url"),
                "selector_counts": report.get("selector_counts"),
                "visible_counts": report.get("visible_counts"),
                "overlay_candidates": report.get("overlay_candidates", [])[:8],
                "samples": report.get("samples"),
            }
            prompt = (
                "너는 Selenium 크롤러 DOM 진단 도우미다. 아래 네이버 밴드 페이지 진단 JSON을 보고 "
                "1) 현재 살아있는 게시물/팝업/이미지 셀렉터, 2) 실패 가능성이 큰 셀렉터, "
                "3) 코드에서 우선 보강할 클릭/수집 전략을 한국어로 6줄 이내로 요약해줘.\n\n"
                + json.dumps(compact, ensure_ascii=False)[:12000]
            )
            res = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)
            return (getattr(res, "text", "") or "").strip()[:2000]
        except Exception as e:
            return f"AI 요약 실패: {str(e)[:160]}"

    # ─── 크롤링 시작 ───────────────────────────────────────────────────────
    def start_crawling(self, settings: dict):
        """
        백그라운드 스레드에서 크롤링을 시작한다.
        settings: {platform, count, startDate, endDate, category, append, ...}
        """
        if self.crawling_thread and self.crawling_thread.is_alive():
            self.add_log("크롤링이 이미 실행 중입니다.", "WARNING")
            return

        self.stop_flag = False

        self.append_mode = settings.get("append", False)
        if not self.append_mode:
            # 신규 크롤링 시작 전 기존 DB 데이터가 있다면 안전하게 백업을 먼저 수행합니다.
            try:
                db_count = self.db.count_all_products()
                if db_count > 0 or len(self.crawled_products) > 0:
                    backup_name = f"신규 크롤링 전 자동 백업 ({max(db_count, len(self.crawled_products))}건)"
                    self.db.backup_current_products(custom_name=backup_name)
                    self.add_log(f"💾 신규 크롤링 전 안전 조치: 기존 상품 {max(db_count, len(self.crawled_products))}건 백업 완료", "INFO", False)
            except Exception as e:
                self.add_log(f"⚠️ 신규 크롤링 전 자동 백업 실패: {e}", "WARNING", False)

            self.crawled_products = []
            self.products_loaded = True
            try:
                self.db.truncate_all()
                self.add_log("🧹 기존 DB 상품 목록을 비웠습니다.", "INFO", False)
            except Exception as e:
                self.add_log(f"⚠️ DB 초기화 실패: {e}", "WARNING", False)
            self.add_log("🧹 기존 목록을 지우고 처음부터 새로 크롤링합니다.", "INFO", False)
        else:
            if not self.products_loaded:
                self.ensure_products_loaded()
            self.add_log(f"➕ 자동 이어가기: 기존 목록({len(self.crawled_products)}건) 아래에 이어서 수집합니다.", "INFO", False)

        platform = settings.get("platform", "카카오스토리")
        count = settings.get("count", 10)

        def _crawl_worker():
            try:
                if platform in ("카카오스토리", "kakao"):
                    self._crawl_kakao(settings)
                elif platform in ("네이버 밴드", "band"):
                    self._crawl_band(settings)
                elif platform in ("웨이상(Szwego)", "weishang"):
                    self._crawl_weishang(settings)
                else:
                    self.add_log(f"⚠️ 지원하지 않는 소스 플랫폼: {platform}", "WARNING")
            except Exception as e:
                self.add_log(f"❌ 크롤링 중 오류: {e}", "ERROR")
                import traceback
                self.add_log(traceback.format_exc(), "ERROR")
            finally:
                # 수집이 종료되면(성공/중단 불문) 사용한 크롤러 브라우저 창을 자동으로 닫습니다.
                try:
                    self.cleanup()
                except Exception as cleanup_err:
                    self.add_log(f"⚠️ 크롤링 종료 후 브라우저 정리 오류: {cleanup_err}", "WARNING")

                if not self.stop_flag:
                    trans_opts = settings.get("transOptions")
                    if trans_opts and trans_opts.get("enable") and trans_opts.get("api_key"):
                        self.add_log("🚀 [자동 분석/번역 기동] 크롤링이 완료되어 AI 일괄 분석 및 번역을 자동 가동합니다.", "INFO")
                        try:
                            self.start_batch_retranslate(
                                api_key=trans_opts.get("api_key"),
                                category=trans_opts.get("category", "여성의류"),
                                naver_fx=float(trans_opts.get("naver_fx", 195.0)),
                                custom_prompt=trans_opts.get("rules_text", ""),
                                use_critic=settings.get("use_critic", False),
                                critic_prompt=""
                            )
                        except Exception as tr_err:
                            self.add_log(f"⚠️ 자동 분석/번역 트리거 실패: {tr_err}", "WARNING")
                    else:
                        self.add_log("🚀 크롤링이 완료되었습니다. (자동 AI 분석 비활성화 상태)", "INFO")

                if len(self.crawled_products) > 0:
                    try:
                        from backend.analysis_history import save_analysis_history
                        summary_msg = f"{platform} 수집 자동 백업 ({len(self.crawled_products)}건)"
                        save_analysis_history(len(self.crawled_products), "", summary_msg, {"bundled_products": self.crawled_products})
                        self.add_log(f"💾 크롤링 실행건 백업 완료 (분석자료 관리 화면에서 확인 가능)", "SUCCESS")
                    except Exception as backup_err:
                        self.add_log(f"⚠️ 자동 백업 실패: {backup_err}", "WARNING")

                # 텔레그램 최종 완료 리포트 및 이미지 브리핑 전송
                try:
                    from backend.telegram_assistant import get_telegram_assistant
                    assistant = get_telegram_assistant()
                    if assistant and assistant.running:
                        status_str = "🛑 사용자 중단" if self.stop_flag else "✅ 정상 완료"
                        registered_count = len(self.crawled_products)
                        
                        report_msg = (
                            f"📊 <b>[수집 완료 보고서]</b>\n\n"
                            f"• <b>수집 결과</b>: <code>{status_str}</code>\n"
                            f"• <b>플랫폼</b>: <code>{platform}</code>\n"
                            f"• 🎯 <b>목표 수량</b>: <code>{count}개</code>\n"
                            f"• 📦 <b>최종 등록 성공</b>: <b>{registered_count}개</b>\n\n"
                            f"<i>최근 수집된 신상품 이미지를 아래에 함께 전송합니다.</i>"
                        )
                        
                        # 최근 상품 이미지 3장 경로 수집
                        photo_paths = []
                        if self.crawled_products:
                            latest_prod = self.crawled_products[-1]
                            local_imgs = latest_prod.get("local_image_paths", [])
                            for p in local_imgs:
                                if len(photo_paths) >= 3:
                                    break
                                if os.path.exists(p):
                                    photo_paths.append(p)
                                    
                        assistant.send_push_notification(report_msg, photo_paths=photo_paths)
                except Exception as tele_report_err:
                    self.add_log(f"⚠️ 텔레그램 완료 보고 전송 실패: {tele_report_err}", "WARNING")

        plat_name = "weishang" if "웨이상" in platform else "kakao" if "카카오" in platform else "band" if "밴드" in platform else platform
        self.crawling_thread = threading.Thread(target=_crawl_worker, daemon=True, name=f"수집({plat_name})")
        self.crawling_thread.start()
        self.add_log(f"📥 [{platform}] 크롤링 스레드 시작 (최대 {count}개)")

        # 텔레그램 수집 시작 알림 전송
        try:
            from backend.telegram_assistant import get_telegram_assistant
            assistant = get_telegram_assistant()
            if assistant and assistant.running:
                start_msg = (
                    f"🚀 <b>[수집 기동 알림]</b>\n\n"
                    f"• <b>플랫폼</b>: <code>{platform}</code>\n"
                    f"• 🎯 <b>목표 수량</b>: <code>{count}개</code>\n"
                    f"• ⚙️ <b>모드</b>: <code>{'이어쓰기' if settings.get('append') else '처음부터'}</code>\n\n"
                    f"<i>원격 제어 봇이 실시간 수집 프로세스를 안전하게 감시합니다.</i>"
                )
                assistant.send_push_notification(start_msg)
        except Exception:
            pass

    def _crawl_kakao(self, settings: dict):
        """카카오스토리 실제 크롤링 실행"""
        try:
            from platforms.kakao.crawler import KakaoCrawler
        except ImportError:
            from backend.platforms.kakao.crawler import KakaoCrawler
        from datetime import datetime as dt

        count = settings.get("count", 10)
        start_date_str = settings.get("startDate", "")
        end_date_str = settings.get("endDate", "")
        category = settings.get("category", "여성의류")

        # 날짜 파싱
        try:
            start_date = dt.strptime(start_date_str, "%Y-%m-%d") if start_date_str else dt.now().replace(day=1)
            end_date = dt.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59) if end_date_str else dt.now()
        except ValueError:
            start_date = dt.now().replace(day=1)
            end_date = dt.now()

        # 크롤러가 이미 있으면 재사용, 없으면 새로 생성
        if self._source_crawler and isinstance(self._source_crawler, KakaoCrawler):
            crawler = self._source_crawler
        else:
            crawler = KakaoCrawler()
            crawler.set_log_func(self.add_log)
            self._source_crawler = crawler

        # 드라이버가 없으면 안내
        if not crawler.driver and not self.source_driver:
            self.add_log("⚠️ 카카오스토리 브라우저가 열려있지 않습니다. '로그인 버튼'을 먼저 클릭하세요.", "WARNING")
            return

        if not crawler.driver and self.source_driver:
            crawler.driver = self.source_driver

        # 이미지 저장 폴더
        target_folder = os.path.join(_PROJECT_ROOT, "TEMP_CRAWLED", "kakao")
        os.makedirs(target_folder, exist_ok=True)

        self.add_log(f"🔁 카카오스토리 크롤링 시작 ({start_date_str} ~ {end_date_str}, 최대 {count}개)")
        self.update_progress(0, count)

        def on_progress(c):
            self.update_progress(c, count)

        def on_result(item):
            try:
                from pricing_logic import clean_vendor_name
            except ImportError:
                from backend.pricing_logic import clean_vendor_name
            if "vendor_name" in item:
                item["vendor_name"] = clean_vendor_name(item["vendor_name"])

            row_id = get_db().add_product(item)
            item["db_id"] = row_id
            with self.lock:
                self.crawled_products.append(item)
            self.add_log(f"📦 수집 누적 {len(self.crawled_products)}: {item.get('title', '제목없음')[:30]}...")
            self.notify_update()

            # --- 실시간 비동기 번역 트리거 차단 (사용자 요청) ---
            # trans_opts = settings.get("transOptions")
            # if trans_opts and trans_opts.get("enable") and trans_opts.get("api_key") and not self.stop_flag:
            #     self.translation_executor.submit(
            #         self.translate_single_item,
            #         idx=item_idx,
            #         api_key=trans_opts.get("api_key"),
            #         category=trans_opts.get("category", "여성의류"),
            #         naver_fx=trans_opts.get("naver_fx", 195.0),
            #         custom_prompt=trans_opts.get("rules_text", ""),
            #         use_critic=settings.get("use_critic", False),
            #         critic_prompt=""
            #     )

        results = crawler.crawl(
            start_date=start_date,
            end_date=end_date,
            max_count=count,
            selected_cat_text=category,
            target_folder=target_folder,
            progress_callback=on_progress,
            result_callback=on_result,
        )

        self.add_log(f"🎉 카카오스토리 크롤링(추가) 완료! 이번 회차 신규 {len(results)}건 수집됨")
        self.update_progress(count, count)

    def _crawl_band(self, settings: dict):
        """네이버 밴드 실제 크롤링 실행"""
        from datetime import datetime as dt

        count = settings.get("count", 10)
        start_date_str = settings.get("startDate", "")
        end_date_str = settings.get("endDate", "")
        category = settings.get("category", "여성의류")

        try:
            start_date = dt.strptime(start_date_str, "%Y-%m-%d") if start_date_str else dt.now().replace(day=1)
            end_date = dt.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59) if end_date_str else dt.now()
        except ValueError:
            start_date = dt.now().replace(day=1)
            end_date = dt.now()

        # 드라이버 확인
        driver = self.source_driver or self.target_driver
        if not driver:
            self.add_log("⚠️ 밴드 브라우저가 열려있지 않습니다. '로그인 버튼'을 먼저 클릭하세요.", "WARNING")
            return

        target_folder = os.path.join(_PROJECT_ROOT, "TEMP_CRAWLED", "band")
        os.makedirs(target_folder, exist_ok=True)

        self.add_log(f"🔁 밴드 크롤링 시작 ({start_date_str} ~ {end_date_str}, 최대 {count}개)")
        self.update_progress(0, count)

        try:
            # BandCrawlingThread를 직접 인스턴스로 사용 (QThread.run()를 직접 호출)
            from band_crawling_thread import BandCrawlingThread

            band_crawler = BandCrawlingThread(
                driver=driver,
                start_date=start_date,
                end_date=end_date,
                max_count=count,
                selected_cat_text=category,
                target_folder=target_folder,
            )
            self._source_crawler = band_crawler

            # QThread의 시그널 대신 engine의 add_log 주입
            band_crawler.log = lambda msg: self.add_log(msg)

            # pyqtSignal의 emit을 오버라이드할 수는 없으므로, result 수집용 래퍼
            collected = self.crawled_products

            class SignalProxy:
                """pyqtSignal.emit()을 일반 콜백으로 변환"""
                def __init__(self, callback):
                    self._cb = callback
                def emit(self, *args):
                    self._cb(*args)
                def connect(self, *args): pass
                def disconnect(self, *args): pass

            band_crawler.log_signal = SignalProxy(lambda msg: self.add_log(msg))
            band_crawler.progress_signal = SignalProxy(lambda c: self.update_progress(c, count))

            def _on_result(item):
                row_id = get_db().add_product(item)
                item["db_id"] = row_id
                with self.lock:
                    collected.append(item)
                self.notify_update()
            band_crawler.result_signal = SignalProxy(_on_result)

            band_crawler.finished_signal = SignalProxy(lambda c: self.add_log(f"🎉 밴드 크롤링 완료! 총 {c}개"))

            # run()을 직접 호출 (QThread.start() 대신, 이미 백그라운드 스레드 안이므로)
            band_crawler.run()

            self.crawled_products = collected
            self.add_log(f"📋 밴드 크롤링 결과: {len(collected)}개 수집됨")

        except ImportError:
            self.add_log("❌ band_crawling_thread.py를 찾을 수 없습니다.", "ERROR")
        except Exception as e:
            self.add_log(f"❌ 밴드 크롤링 오류: {e}", "ERROR")
            import traceback
            self.add_log(traceback.format_exc(), "ERROR")
            try:
                if 'band_crawler' in locals() and hasattr(band_crawler, 'driver') and band_crawler.driver:
                    dump_path = save_error_dump(band_crawler.driver, "band_crawl_fatal")
                    if dump_path: self.add_log(f"📸 에러 캡처: {dump_path}", "INFO")
            except: pass

    def _crawl_weishang(self, settings: dict):
        """웨이상(Szwego) 크롤링 실행"""
        try:
            try:
                from platforms.weishang.crawler import WeishangCrawler
            except ImportError:
                from backend.platforms.weishang.crawler import WeishangCrawler
        except ImportError:
            self.add_log("❌ weishang_crawler.py를 찾을 수 없습니다.", "ERROR")
            return

        def _qr_callback(b64):
            self.weishang_qr_base64 = b64

        def _add_product(item):
            item.setdefault("platform", "웨이상(Szwego)")
            try:
                from pricing_logic import clean_vendor_name
            except ImportError:
                from backend.pricing_logic import clean_vendor_name
            if "vendor_name" in item:
                item["vendor_name"] = clean_vendor_name(item["vendor_name"])

            row_id = get_db().add_product(item)
            item["db_id"] = row_id
            with self.lock:
                self.crawled_products.append(item)
            self.notify_update()

        def _update_product(item):
            db_id = item.get("db_id")
            if db_id is None:
                return
            try:
                from pricing_logic import clean_vendor_name
            except ImportError:
                from backend.pricing_logic import clean_vendor_name
            if "vendor_name" in item:
                item["vendor_name"] = clean_vendor_name(item["vendor_name"])

            get_db().update_product_by_id(db_id, item)
            with self.lock:
                for idx, prod in enumerate(self.crawled_products):
                    if prod.get("db_id") == db_id:
                        self.crawled_products[idx] = item
                        break
            self.notify_update()

        def _record_weishang_event(event):
            get_db().record_crawl_event(
                platform="weishang",
                event_type=event.get("event_type", ""),
                vendor_id=event.get("vendor_id", ""),
                vendor_name=event.get("vendor_name", ""),
                reason=event.get("reason", ""),
                raw_text=event.get("raw_text", ""),
                metadata=event.get("metadata", {}),
            )

        crawler = WeishangCrawler(
            log_func=self.add_log,
            add_product_func=_add_product,
            update_product_func=_update_product,
            qr_callback=_qr_callback,
            telemetry_func=_record_weishang_event,
        )

        crawler.run(settings)

        # 자동 재번역은 _crawl_worker()의 공통 완료 처리에서 한 번만 실행한다.
    def sync_vendors(self):
        """웨이상 업체 목록 동기화"""
        try:
            try:
                from platforms.weishang.crawler import WeishangCrawler
            except ImportError:
                from backend.platforms.weishang.crawler import WeishangCrawler
        except ImportError:
            self.add_log("❌ weishang_crawler.py를 찾을 수 없습니다.", "ERROR")
            return []

        def _qr_callback(b64):
            self.weishang_qr_base64 = b64

        crawler = WeishangCrawler(
            log_func=self.add_log,
            add_product_func=lambda x: None,
            qr_callback=_qr_callback
        )
        return crawler.sync_vendors()

    def _recover_band_poster(self, settings: dict):
        """밴드 포스터 세션 유실/충돌 시 자동 복구 및 브라우저 재기동"""
        self.add_log("⚙️ [자가 복구] 밴드 포스터 세션 오류를 극복하기 위한 복구 솔루션을 작동합니다.", "WARNING")
        if self.target_driver:
            try:
                self._safe_quit_driver(self.target_driver, "밴드 복구용 강제종료")
            except:
                pass
            self.target_driver = None
        if self._target_poster:
            self._target_poster.band_driver = None

        # 락 파일 해제
        try:
            profile_name = getattr(self, "band_profile_name", "밴드업데이트계정1")
            profile_dir = os.path.join(_PROJECT_ROOT, f"band_profile_{profile_name}")
            for lf in ["SingletonLock", "lock", "Default/SingletonLock", "Default/lock"]:
                lock_path = os.path.join(profile_dir, lf)
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            self.add_log(f"🧹 [자가 복구] 밴드 프로필 '{profile_name}' 락 파일을 처치했습니다.", "INFO")
        except Exception as e:
            self.add_log(f"⚠️ [자가 복구] 락 해제 실패 (계속 진행): {e}", "WARNING")

        # 좀비 크롬 소멸
        self._fix_chromedriver_conflict()

        # 재기동
        try:
            self.add_log("⏳ [자가 복구] 밴드 브라우저 및 세션 재설정 구동 중...", "INFO")
            self.open_browser("네이버 밴드", {}, settings.get("ghost_mode", False))
            if self.target_driver:
                self._prepare_band_poster(settings)
                self.add_log("✅ [자가 복구] 밴드 포스터가 안전하게 재기동 완료되어 이어서 진행합니다.", "SUCCESS")
        except Exception as e:
            self.add_log(f"❌ [자가 복구] 밴드 재기동 실패: {e}", "ERROR")

    def _recover_kakao_driver(self, settings: dict):
        """카카오스토리 포스터 세션 유실/충돌 시 자동 복구 및 브라우저 재기동"""
        self.add_log("⚙️ [자가 복구] 카카오스토리 세션 오류를 극복하기 위한 복구 솔루션을 작동합니다.", "WARNING")
        if self.source_driver:
            try:
                self._safe_quit_driver(self.source_driver, "카카오 복구용 강제종료")
            except:
                pass
            self.source_driver = None

        # 락 파일 해제
        try:
            profile_name = getattr(self, "kakao_profile_name", "메인카스2")
            profile_dir = os.path.join(_PROJECT_ROOT, f"kakao_profile_{profile_name}")
            for lf in ["SingletonLock", "lock", "Default/SingletonLock", "Default/lock"]:
                lock_path = os.path.join(profile_dir, lf)
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            self.add_log(f"🧹 [자가 복구] 카카오 프로필 '{profile_name}' 락 파일을 처치했습니다.", "INFO")
        except Exception as e:
            self.add_log(f"⚠️ [자가 복구] 락 해제 실패 (계속 진행): {e}", "WARNING")

        # 좀비 크롬 소멸
        self._fix_chromedriver_conflict()

        # 재기동
        try:
            self.add_log("⏳ [자가 복구] 카카오 브라우저 및 세션 재설정 구동 중...", "INFO")
            self.open_browser("카카오스토리", {}, settings.get("ghost_mode", False))
            if self.source_driver:
                self.add_log("✅ [자가 복구] 카카오 업로더가 안전하게 재기동 완료되어 이어서 진행합니다.", "SUCCESS")
        except Exception as e:
            self.add_log(f"❌ [자가 복구] 카카오 재기동 실패: {e}", "ERROR")

    # ─── 포스팅 시작 ───────────────────────────────────────────────────────
    def is_posting_running(self) -> bool:
        """포스팅 작업이 이미 실행 중인지 API/큐에서 확인할 때 사용한다."""
        with self.lock:
            thread_alive = bool(self.posting_thread and self.posting_thread.is_alive())
            return bool(self._posting_running or thread_alive)

    def start_posting(self, settings: dict):
        """
        하위 호환성을 위한 메서드. 실제로는 run_posting_job을 스레드로 실행합니다.
        (보통 QueueManager가 run_posting_job을 직접 동기 호출하므로 직접 쓸 일은 줄어듭니다)
        """
        if self.posting_thread and self.posting_thread.is_alive():
            self.add_log("포스팅이 이미 실행 중입니다.", "WARNING")
            return

        self.posting_thread = threading.Thread(target=self.run_posting_job, args=(settings,), daemon=True, name="포스팅")
        self.posting_thread.start()

    def run_posting_job(self, settings: dict):
        with self.lock:
            if self._posting_running:
                self.add_log("⚠️ 포스팅 작업이 이미 실행 중이라 중복 시작 요청을 무시합니다.", "WARNING")
                return False
            self._posting_running = True
        try:
            return self._run_posting_job_locked(settings)
        finally:
            with self.lock:
                self._posting_running = False
            self.notify_update()

    def _build_post_content_signature(self, item: dict) -> str:
        """게시 본문과 이미지 순서를 기준으로 정확 중복 판정용 해시를 만든다."""
        import hashlib
        import json
        import os
        import re

        text = item.get("raw_description") or item.get("description") or item.get("title") or ""
        normalized_text = re.sub(r"\s+", " ", str(text)).strip()
        image_refs = item.get("local_image_paths") or item.get("image_urls") or item.get("image_files") or []
        image_signatures = []

        for ref in image_refs:
            ref_text = str(ref or "").strip()
            if not ref_text:
                continue
            if os.path.exists(ref_text) and os.path.isfile(ref_text):
                try:
                    h = hashlib.sha256()
                    with open(ref_text, "rb") as f:
                        for chunk in iter(lambda: f.read(1024 * 1024), b""):
                            h.update(chunk)
                    image_signatures.append(f"file:{h.hexdigest()}")
                    continue
                except Exception:
                    pass
            image_signatures.append(f"ref:{ref_text}")

        payload = {"text": normalized_text, "images": image_signatures}
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def _run_posting_job_locked(self, settings: dict):
        """
        실제 포스팅 동기 루프 메서드.
        QueueManager의 POST 워커 스레드 위에서 동기적으로 실행됩니다.
        """
        import random
        import time
        if not self.crawled_products:
            self.add_log("⚠️ 포스팅할 데이터가 없습니다. 먼저 크롤링을 실행하세요.", "WARNING")
            return

        self.stop_flag = False
        platforms = settings.get("platforms", ["네이버 밴드"])

        if not platforms:
            self.add_log("⚠️ 포스팅할 플랫폼이 선택되지 않았습니다.", "WARNING")
            return

        # 드라이버 사전 검증
        use_band = "네이버 밴드" in platforms
        use_kakao = "카카오스토리" in platforms

        if use_band and not self._prepare_band_poster(settings):
            return
        if use_kakao and not self._prepare_kakao_driver():
            return

        selected_indices_raw = settings.get("selected_indices") or []
        selected_indices = []
        if selected_indices_raw:
            seen_indices = set()
            for raw_idx in selected_indices_raw:
                try:
                    idx_val = int(raw_idx)
                except Exception:
                    continue
                if 0 <= idx_val < len(self.crawled_products) and idx_val not in seen_indices:
                    selected_indices.append(idx_val)
                    seen_indices.add(idx_val)

        if selected_indices:
            posting_targets = [(idx, self.crawled_products[idx]) for idx in selected_indices]
            self.add_log(f"🎯 선택된 상품 {len(posting_targets)}개만 포스팅합니다.", "INFO")
        elif selected_indices_raw:
            self.add_log("⚠️ 선택된 상품 인덱스가 현재 목록과 맞지 않아 포스팅을 중단합니다.", "WARNING")
            return
        else:
            posting_targets = list(enumerate(self.crawled_products))

        platform_names = " + ".join(platforms)
        self.add_log(f"📤 [{platform_names}] 포스팅 작업 시작 ({len(posting_targets)}개 대기)")

        total = len(posting_targets)
        self.update_progress(0, total)

        band_ok, band_fail = 0, 0
        kakao_ok, kakao_fail = 0, 0
        delay_min = settings.get("delayMin", 3)
        delay_max = settings.get("delayMax", 10)

        dry_run = settings.get("dry_run", False)
        skip_duplicate_posts = bool(settings.get("skip_duplicate_posts", True))
        if dry_run:
            self.add_log("🧪 [Dry-Run] 테스트 모드로 실행됩니다. 실제 게시는 이루어지지 않습니다.", "INFO")
        if not skip_duplicate_posts:
            self.add_log("🔁 중복 게시 방지 필터 OFF: 기존 게시 이력이 있어도 포스팅합니다.", "WARNING")

        for seq, (original_index, item) in enumerate(posting_targets, 1):
            if self.stop_flag:
                self.add_log("⚠️ 사용자에 의해 포스팅이 중단되었습니다.", "WARNING")
                break

            product_code = item.get('product_code', '')
            title = item.get('title', '제목없음')[:30]
            item_had_post_attempt = False
            item_label = f"{seq}/{total}" if original_index + 1 == seq and total == len(self.crawled_products) else f"{seq}/{total} | #{original_index + 1}"
            content_signature = self._build_post_content_signature(item)

            # ── 밴드 포스팅 (자가 복구 적용) ──
            if use_band:
                band_profile = getattr(self, "band_profile_name", "밴드계정")
                if skip_duplicate_posts and self.db.is_already_posted(product_code, "네이버 밴드", content_signature) and not dry_run:
                    self.add_log(f"⏭️ [중복 방지] 본문+이미지가 같은 밴드 게시 이력이 있습니다: {title}", "WARNING")
                    item['post_status_band'] = 'skip'
                    item['post_error_band'] = '본문+이미지 중복 게시 방지'
                else:
                    recovery_attempts = 0
                    sys_settings = get_system_settings()
                    enable_recovery = sys_settings.get("enable_auto_recovery", True)
                    recovery_limit = sys_settings.get("auto_recovery_retry_limit", 3)
                    
                    while True:
                        if self.stop_flag:
                            break
                        item_had_post_attempt = True
                        
                        # 하트비트 모니터링: 브라우저가 정상 응답하는지 pre-check
                        if sys_settings.get("session_heartbeat_check", True) and self.target_driver:
                            try:
                                _ = self.target_driver.title
                            except Exception as e:
                                self.add_log(f"⚠️ [하트비트] 밴드 브라우저 비정상 감지 (오류: {e}). 자동 복구를 진행합니다.", "WARNING")
                                if enable_recovery and recovery_attempts < recovery_limit:
                                    recovery_attempts += 1
                                    self.add_log(f"⏳ [자가 복구] 밴드 세션 재연결 시도 ({recovery_attempts}/{recovery_limit})...", "INFO")
                                    self._recover_band_poster(settings)
                                    continue
                                else:
                                    self.add_log("❌ [자가 복구] 최대 복구 시도 횟수를 초과했거나 복구가 비활성화되어 있습니다.", "ERROR")
                        
                        self.add_log(f"📝 [{item_label}] 🟠 밴드 포스팅: {title}...")
                        try:
                            band_result = self._post_single_to_band(item, dry_run=dry_run)
                            
                            # 포스팅 실패 시 브라우저 사망 여부 검사 및 복구
                            if not band_result and self.target_driver:
                                is_dead = False
                                try:
                                    _ = self.target_driver.title
                                except Exception:
                                    is_dead = True
                                
                                if is_dead and enable_recovery and recovery_attempts < recovery_limit:
                                    recovery_attempts += 1
                                    self.add_log(f"⏳ [자가 복구] 포스팅 오류 감지 - 밴드 브라우저 재기동 시도 ({recovery_attempts}/{recovery_limit})...", "WARNING")
                                    self._recover_band_poster(settings)
                                    continue
                        except Exception as e:
                            band_result = False
                            if enable_recovery and recovery_attempts < recovery_limit:
                                recovery_attempts += 1
                                self.add_log(f"❌ [에러 복구] 밴드 포스팅 예외 발생: {e}. 재시도합니다 ({recovery_attempts}/{recovery_limit}).", "WARNING")
                                self._recover_band_poster(settings)
                                continue
                            else:
                                item['post_error_band'] = f"예외 발생: {str(e)}"
                        
                        if band_result:
                            band_ok += 1
                            item['post_status_band'] = 'dry_run' if dry_run else 'success'
                            item['post_error_band'] = ''
                            status_val = "DRY_RUN" if dry_run else "SUCCESS"
                            self.db.add_post_history(product_code, "네이버 밴드", band_profile, status_val, content_signature=content_signature)
                            self.save_temp_data()
                        else:
                            band_fail += 1
                            item['post_status_band'] = 'fail'
                            item['post_error_band'] = item.get('post_error_band', '알 수 없는 오류')
                            self.db.add_post_history(product_code, "네이버 밴드", band_profile, "FAIL", item.get('post_error_band', '알 수 없는 오류'), content_signature=content_signature)
                            self.save_temp_data()
                        break
                self.notify_update()

                # 두 플랫폼 모두 사용 시 중간 딜레이
                if use_kakao:
                    mid_delay = random.uniform(2, 4)
                    time.sleep(mid_delay)

            # ── 카카오 포스팅 (자가 복구 적용) ──
            if use_kakao:
                kakao_profile = getattr(self, "kakao_profile_name", "카카오계정")
                if skip_duplicate_posts and self.db.is_already_posted(product_code, "카카오스토리", content_signature) and not dry_run:
                    self.add_log(f"⏭️ [중복 방지] 본문+이미지가 같은 카카오 게시 이력이 있습니다: {title}", "WARNING")
                    item['post_status_kakao'] = 'skip'
                    item['post_error_kakao'] = '본문+이미지 중복 게시 방지'
                else:
                    recovery_attempts = 0
                    sys_settings = get_system_settings()
                    enable_recovery = sys_settings.get("enable_auto_recovery", True)
                    recovery_limit = sys_settings.get("auto_recovery_retry_limit", 3)
                    
                    while True:
                        if self.stop_flag:
                            break
                        item_had_post_attempt = True
                        
                        # 하트비트 모니터링: 브라우저가 정상 응답하는지 pre-check
                        if sys_settings.get("session_heartbeat_check", True) and self.source_driver:
                            try:
                                _ = self.source_driver.title
                            except Exception as e:
                                self.add_log(f"⚠️ [하트비트] 카카오 브라우저 비정상 감지 (오류: {e}). 자동 복구를 진행합니다.", "WARNING")
                                if enable_recovery and recovery_attempts < recovery_limit:
                                    recovery_attempts += 1
                                    self.add_log(f"⏳ [자가 복구] 카카오 세션 재연결 시도 ({recovery_attempts}/{recovery_limit})...", "INFO")
                                    self._recover_kakao_driver(settings)
                                    continue
                                else:
                                    self.add_log("❌ [자가 복구] 최대 복구 시도 횟수를 초과했거나 복구가 비활성화되어 있습니다.", "ERROR")

                        self.add_log(f"📝 [{item_label}] 🟡 카카오 포스팅: {title}...")
                        try:
                            kakao_result = self._post_single_to_kakao(item, dry_run=dry_run)
                            
                            # 포스팅 실패 시 브라우저 사망 여부 검사 및 복구
                            if not kakao_result and self.source_driver:
                                is_dead = False
                                try:
                                    _ = self.source_driver.title
                                except Exception:
                                    is_dead = True
                                
                                if is_dead and enable_recovery and recovery_attempts < recovery_limit:
                                    recovery_attempts += 1
                                    self.add_log(f"⏳ [자가 복구] 포스팅 오류 감지 - 카카오 브라우저 재기동 시도 ({recovery_attempts}/{recovery_limit})...", "WARNING")
                                    self._recover_kakao_driver(settings)
                                    continue
                        except Exception as e:
                            kakao_result = False
                            if enable_recovery and recovery_attempts < recovery_limit:
                                recovery_attempts += 1
                                self.add_log(f"❌ [에러 복구] 카카오 포스팅 예외 발생: {e}. 재시도합니다 ({recovery_attempts}/{recovery_limit}).", "WARNING")
                                self._recover_kakao_driver(settings)
                                continue
                            else:
                                item['post_error_kakao'] = f"예외 발생: {str(e)}"
                        
                        if kakao_result:
                            kakao_ok += 1
                            item['post_status_kakao'] = 'dry_run' if dry_run else 'success'
                            item['post_error_kakao'] = ''
                            status_val = "DRY_RUN" if dry_run else "SUCCESS"
                            self.db.add_post_history(product_code, "카카오스토리", kakao_profile, status_val, content_signature=content_signature)
                            self.save_temp_data()
                        else:
                            kakao_fail += 1
                            item['post_status_kakao'] = 'fail'
                            item['post_error_kakao'] = item.get('post_error_kakao', '알 수 없는 오류')
                            self.db.add_post_history(product_code, "카카오스토리", kakao_profile, "FAIL", item.get('post_error_kakao', '알 수 없는 오류'), content_signature=content_signature)
                            self.save_temp_data()
                        break
                self.notify_update()

            self.progress["success"] = band_ok + kakao_ok
            self.progress["fail"] = band_fail + kakao_fail
            self.update_progress(seq, total)

            # 다음 상품까지 딜레이
            if seq < total and not self.stop_flag and item_had_post_attempt:
                delay = random.uniform(min(delay_min, delay_max), max(delay_min, delay_max))
                self.add_log(f"⏱ {delay:.1f}초 대기...")
                time.sleep(delay)

        # 결과 요약
        results = []
        if use_band:
            results.append(f"밴드(성공:{band_ok}/실패:{band_fail})")
        if use_kakao:
            results.append(f"카카오(성공:{kakao_ok}/실패:{kakao_fail})")
        self.add_log(f"🎉 포스팅 완료! {' | '.join(results)}")
        
        # 포스팅 작업 완료 후 브라우저를 자동으로 닫지 않고 유지합니다. (보관 및 수동 정리)
        # try:
        #     self.cleanup()
        # except Exception as cleanup_err:
        #     self.add_log(f"⚠️ 포스팅 종료 후 브라우저 정리 오류: {cleanup_err}", "WARNING")
        self.add_log("ℹ️ 포스팅 작업이 모두 완료되었습니다. 브라우저 창은 수동 정리를 위해 열려있는 상태로 유지됩니다.", "INFO")

    # ─── 밴드 드라이버 사전 준비 ──────────────────────────────────────────
    def _prepare_band_poster(self, settings: dict) -> bool:
        """밴드 BandPoster 인스턴스를 준비하고 드라이버를 확인한다. 성공 시 True."""
        try:
            from platforms.band.poster import BandPoster
        except ImportError:
            from backend.platforms.band.poster import BandPoster

        delay_min = settings.get("delayMin", 3)
        delay_max = settings.get("delayMax", 10)

        if self._target_poster and isinstance(self._target_poster, BandPoster):
            poster = self._target_poster
        else:
            poster = BandPoster(
                post_list=self.crawled_products,
                delay_min=delay_min,
                delay_max=delay_max,
            )
            poster.set_log_func(self.add_log)

        if not poster.band_driver:
            if self.target_driver:
                poster.band_driver = self.target_driver
            else:
                self.add_log("⚠️ 밴드 브라우저가 열려있지 않습니다. '밴드 로그인'을 먼저 클릭하세요.", "WARNING")
                return False

        if not self._ensure_band_group_page(poster.band_driver, timeout=18):
            self.add_log(
                "⚠️ 밴드 업로드 준비 실패: 현재 브라우저가 밴드 그룹 내부가 아니거나 글쓰기 버튼을 찾을 수 없습니다.",
                "WARNING",
            )
            return False

        self._target_poster = poster
        return True

    # ─── 카카오 드라이버 사전 준비 ────────────────────────────────────────
    def _prepare_kakao_driver(self) -> bool:
        """카카오스토리 드라이버가 열려있는지 확인한다. 성공 시 True."""
        if not self.source_driver:
            self.add_log("⚠️ 카카오스토리 브라우저가 열려있지 않습니다. '카카오 로그인'을 먼저 클릭하세요.", "WARNING")
            return False
        return True

    # ─── 밴드 단건 포스팅 ─────────────────────────────────────────────────
    def _post_single_to_band(self, item: dict, dry_run: bool = False) -> bool:
        """밴드에 상품 1건을 포스팅한다. 성공 시 True."""
        try:
            from platforms.band.poster import BandPoster
        except ImportError:
            from backend.platforms.band.poster import BandPoster

        if dry_run:
            self.add_log(f"  🧪 [Dry-Run] 밴드 포스팅 시뮬레이션 (상품: {item.get('title', '제목없음')[:20]})", "INFO")
            return True

        try:
            poster = self._target_poster
            if not poster or not isinstance(poster, BandPoster):
                item['post_error_band'] = '밴드 포스터 미초기화'
                self.add_log("⚠️ 밴드 포스터가 초기화되지 않았습니다.", "WARNING")
                return False
            ok = poster.post(item)
            if ok:
                self.add_log("  ✅ 밴드 게시 성공")
            else:
                item['post_error_band'] = '글쓰기/게시 버튼 실패'
                self.add_log("  ❌ 밴드 게시 실패", "WARNING")
            return ok
        except Exception as e:
            item['post_error_band'] = str(e)[:100]
            self.add_log(f"  ❌ 밴드 포스팅 오류: {e}", "ERROR")
            try:
                if self.target_driver:
                    dump_path = save_error_dump(self.target_driver, "band_post_fatal")
                    if dump_path: self.add_log(f"📸 에러 캡처: {dump_path}", "INFO")
            except: pass
            return False

    # ─── 카카오 단건 포스팅 ───────────────────────────────────────────────
    def _post_single_to_kakao(self, item: dict, dry_run: bool = False) -> bool:
        """카카오스토리에 상품 1건을 포스팅한다. (platforms/kakao/poster.py 로직 위임)"""
        try:
            from platforms.kakao.poster import KakaoPoster
        except ImportError:
            from backend.platforms.kakao.poster import KakaoPoster

        poster = KakaoPoster(self.source_driver, self.add_log, getattr(self, "final_target_folder", ""))
        poster.stop_flag = self.stop_flag
        return poster.post(item, dry_run=dry_run)

    # ─── 일괄 재번역 로직 (api_server_py에서 이식) ──────────────────────
    def translate_single_item(self, idx, api_key, category, naver_fx, custom_prompt="", use_critic=False, critic_prompt="", seq=0, total=1):
        import json, time, re, os
        import pricing_logic


        if getattr(self, '_retranslate_stop', False):
            return False

        product = self.crawled_products[idx]
        raw_text = product.get('original_chinese', '')
        if not raw_text:
            return False

        title_preview = product.get('title', '제목없음')[:20]
        self.add_log(f"🔄 [{seq+1}/{total}] 번역 시작: {title_preview}...", "INFO", False)

        try:
            from google import genai
            from google.genai import types
        except Exception as e:
            self.add_log(f"❌ Gemini 모듈 오류: {e}", "ERROR", False)
            return False

        client = genai.Client(api_key=api_key.strip())
        base_fx = naver_fx

        # --- 스마트 카테고리 감지 (Phase 5: Vision API 교차검증 포함) ---
        try:
            import backend.database as database
        except ImportError:
            import database
        try:
            from backend.ai_services import detect_category_with_vision
        except ImportError:
            from ai_services import detect_category_with_vision

        item_cat = product.get("vendor_category", "")
        final_cat = item_cat

        # 1. 텍스트 감지 (기본)
        if not final_cat:
            _det_title = product.get('title', '')
            _, _det_specific = pricing_logic.determine_item_category(category, _det_title, raw_text)
            _CAT_MAP = {
                '가방': '가방', '지갑': '지갑', '부츠': '신발', '일반신발': '신발',
                '시계': '시계', '악세사리': '악세사리',
                '바지': category, '아우터': category,
                '무거운의류': category, '일반의류': category,
            }
            final_cat = _CAT_MAP.get(_det_specific, category)

        # 시스템 설정 로드 (Vision AI 사용 차단 여부 등)
        sys_settings = database.get_system_settings()
        ai_budget_mode = sys_settings.get("ai_budget_mode", "economy")
        ai_use_vision = sys_settings.get("ai_use_vision_during_crawl", False)

        # 2. Vision API 보정 (캐시가 없을 때만, 그리고 예산 모드가 economy/minimum이 아니고 Vision AI 옵션이 활성화되었을 때만)
        use_translation_cache = not bool(str(custom_prompt or "").strip())
        
        # 캐시 충돌 방지를 위해 첫 번째 이미지의 파일명을 image_key로 활용
        first_img_file = ""
        local_paths = product.get("local_image_paths", [])
        if local_paths and len(local_paths) > 0:
            first_img_file = os.path.basename(local_paths[0])
        elif product.get("image_urls") and len(product.get("image_urls")) > 0:
            first_img_file = os.path.basename(product.get("image_urls")[0].split('?')[0])

        cached_result = database.get_cached_translation(raw_text, final_cat, first_img_file) if use_translation_cache else None

        # economy 또는 minimum 모드이거나 비전 미사용 설정 시 Vision AI 스킵
        skip_vision_api = (ai_budget_mode in ["economy", "minimum"]) or (not ai_use_vision)

        if not cached_result and not skip_vision_api:
            # 첫 번째 로컬 이미지를 활용해 판별
            first_img_path = ""
            if local_paths and len(local_paths) > 0:
                first_img_path = local_paths[0]
            elif product.get("image_urls") and len(product.get("image_urls")) > 0:
                # fallback to URL if local image is somehow missing but URL exists
                first_img_path = product.get("image_urls")[0]

            if first_img_path:
                try:
                    vision_cat = detect_category_with_vision(api_key.strip(), first_img_path, raw_text)
                    if vision_cat and vision_cat != final_cat:
                        final_cat = vision_cat
                        self.add_log(f"  🤖 [Vision AI] 텍스트 분류를 '{vision_cat}'(으)로 교차 검증 및 보정 완료", "INFO", False)
                        # 카테고리가 변경되었으므로 변경된 카테고리로 캐시 재확인
                        cached_result = database.get_cached_translation(raw_text, final_cat, first_img_file)
                except Exception as ve:
                    self.add_log(f"  ⚠️ [Vision AI] 분류 보정 오류 (스킵): {ve}", "WARNING", False)

        if final_cat != category:
                self.add_log(f"  🏷️ 자동 감지 카테고리: {final_cat} (원문/제목 분석)", "INFO", False)

        # --- 카테고리별 사이즈 규칙 동적 할당 ---
        cat_lower = final_cat.lower()
        if any(k in cat_lower for k in ["신발", "슬리퍼", "샌들", "스니커즈", "부츠", "로퍼", "뮬"]):
            size_rule_text = "4. 📏 신발류는 원문의 사이즈 범위(예: 38-45)를 번역하고, 사이즈 mm 매핑을 가로가 아닌 무조건 '세로로 한 줄씩 일렬 정렬'하여 기재할 것.\n(예시: \n38 ▶ 245mm\n39 ▶ 250mm\n40 ▶ 255mm). S/M/L 등 의류 사이즈 사용 절대 금지!"
            size_template_text = "✔ 사이즈 : 38 ~ 45\n  38 ▶ 245mm\n  39 ▶ 250mm\n  40 ▶ 255mm\n  41 ▶ 260mm\n  42 ▶ 265mm\n  43 ▶ 275mm\n  44 ▶ 280mm\n  45 ▶ 285mm\n  (원문의 사이즈 범위에 맞춰 기재하고, 반드시 위처럼 세로로 줄바꿈하여 정렬할 것)"
        elif any(k in cat_lower for k in ["바지", "데님", "팬츠", "하의"]):
            size_rule_text = "4. 📏 바지/팬츠류는 원문 기준(숫자 사이즈 혹은 S/M/L)을 우선하고 임의 변환하지 말 것. 실측표가 있으면 실측표 형태로 작성할 것."
            size_template_text = "✔ 사이즈 : (원문 기준 허리사이즈 또는 S/M/L 등 표기, 정보가 없으면 삭제)"
        elif any(k in cat_lower for k in ["가방", "지갑"]):
            size_rule_text = "4. 📏 가방/지갑류는 원문에 기재된 실제 크기/치수(예: 30x26x14cm 등)를 번역할 것. 의류 사이즈표(S/M/L) 절대 금지."
            size_template_text = "✔ 사이즈 : (원문의 실제 치수 번역, 정보가 없으면 삭제)"
        elif "시계" in cat_lower:
            size_rule_text = "4. 📏 시계류는 케이스 지름(예: 40mm) 등 기재된 치수를 번역할 것. 의류 사이즈표 절대 금지."
            size_template_text = "✔ 사이즈 : (원문의 케이스 지름 치수 등 번역, 정보가 없으면 삭제)"
        elif any(k in cat_lower for k in ["악세사리", "선글라스", "acc", "기타"]):
            size_rule_text = "4. 📏 액세서리류는 원문에 기재된 치수를 번역할 것. S/M/L 의류 사이즈표 절대 금지."
            size_template_text = "✔ 사이즈 : (원문의 실제 치수 번역, 정보가 없으면 삭제)"
        else: # 기본 의류 (남성의류, 여성의류, 패딩, 자켓 등)
            size_rule_text = "4. 📏 의류 사이즈는 '✔ 사이즈 : S / M / L' 형태로 적고, 각 사이즈별 한국 사이즈 매칭(▶ 기호 사용)을 포함할 것. (예: S ▶ 95, M ▶ 100)"
            size_template_text = "✔ 사이즈 : S / M / L / XL\n  S ▶ 95\n  M ▶ 100\n  L ▶ 105\n  XL ▶ 110"

        vendor_name = product.get('vendor_name', 'Unknown')
        profile_rule_text = ""
        try:
            product_vendor_id = str(product.get("vendor_id") or "").strip()
            product_vendor_url = str(product.get("vendor_url") or "").strip()
            product_vendor_key = str(product.get("vendor_profile_key") or "").strip()

            def _extract_vendor_id_for_match(value: str) -> str:
                value = str(value or "")
                m = re.search(r"/shop_detail/([^/?#\s]+)", value)
                if m:
                    return m.group(1)
                if value.startswith("_"):
                    return value.split("?")[0].strip("/")
                return ""

            def _normalize_vendor_key(value: str) -> str:
                vid = _extract_vendor_id_for_match(value)
                if vid:
                    return f"shop_detail/{vid}"
                return str(value or "").split("?")[0].rstrip("/")

            vendor_file = os.path.join(_PROJECT_ROOT, "weishang_vendors.json")
            if os.path.exists(vendor_file):
                with open(vendor_file, "r", encoding="utf-8") as f:
                    vlist = json.load(f)
                    matched_vendor = None
                    for v in vlist:
                        vendor_id = str(v.get("id") or _extract_vendor_id_for_match(v.get("url", ""))).strip()
                        vendor_key = _normalize_vendor_key(v.get("url", ""))
                        if product_vendor_id and vendor_id and product_vendor_id == vendor_id:
                            matched_vendor = v
                            break
                        if product_vendor_key and vendor_key and product_vendor_key == vendor_key:
                            matched_vendor = v
                            break
                        if product_vendor_url and vendor_key and _normalize_vendor_key(product_vendor_url) == vendor_key:
                            matched_vendor = v
                            break
                        if v.get("name") == vendor_name:
                            matched_vendor = v
                            break
                    if matched_vendor:
                        # [업체명 교정 로직 추가] DB/크롤링에서 업체명이 없거나 Unknown/UnknownVendor/相册详情/微商相册 등으로 넘어온 경우 프로파일 정보로 교정
                        current_vname = product.get('vendor_name', '')
                        if not current_vname or current_vname.lower() in ('unknown', 'unknownvendor') or current_vname in ('相册详情', '微商相册', '详情', '相册'):
                            try:
                                from pricing_logic import clean_vendor_name
                            except ImportError:
                                from backend.pricing_logic import clean_vendor_name
                            product['vendor_name'] = clean_vendor_name(matched_vendor.get('name', 'Unknown'))
                            vendor_name = product['vendor_name']

                        profile_parts = []
                        for label, key in [
                            ("업체 번역/문체 규칙", "profile_rules"),
                            ("상품 글 구성", "post_structure"),
                            ("묶음/분할 규칙", "grouping_rules"),
                            ("동일상품 매칭 규칙", "matching_rules"),
                            ("가격 표기/계산 패턴", "pricing_pattern"),
                            ("추천 판매 문체", "recommended_style"),
                            ("업체코드 (상품코드 앞자리 지정용)", "vendor_code"),
                            ("단가 보정값 (상품코드 계산 지정용)", "price_margin"),
                        ]:
                            value = matched_vendor.get(key)
                            if value:
                                profile_parts.append(f"- {label}: {value}")
                        if profile_parts:
                            profile_rule_text = "\n\n🚨 [해당 업체 특화 AI 번역/상품화 규칙 - 최우선 참고]\n" + "\n".join(profile_parts) + "\n"
        except Exception:
            pass

        try:
            from backend.style_context import build_style_instruction
        except ImportError:
            from style_context import build_style_instruction
        style_rule_text = build_style_instruction(final_cat or category, include_band=True)

        try:
            from backend.category_templates import get_template_for_category
        except ImportError:
            try:
                from category_templates import get_template_for_category
            except ImportError:
                def get_template_for_category(c): return ""
        category_template_text = f"\n\n🚨 [해당 카테고리 특화 번역 지침]\n{get_template_for_category(final_cat or category)}\n" if get_template_for_category(final_cat or category) else ""

        custom_prompt_text = f"\n\n🚨 [사용자 추가 번역 규칙]\n{custom_prompt}\n" if custom_prompt else ""
        prompt = f"""아래 [포스팅 템플릿]과 [번역 규칙]을 엄격하게 준수하여 중국어 상품 정보를 한국어 프리미엄 쇼핑몰용으로 번역해줘.
이번에는 카카오스토리용(kakao_text), 네이버 밴드용(band_text), 인스타그램용(insta_text) 3가지 버전으로 각각 작성해야 해.
{profile_rule_text}{category_template_text}{style_rule_text}{custom_prompt_text}
[파라미터]
상품 카테고리: {final_cat}

🚨 [다중 페르소나 템플릿 규칙]
0. [최고 엄격 규칙] 출력 결과물에 중국어(한자)가 단 한 글자라도 포함되어서는 절대 안 되며, '미인점 없는' 같이 패션 상품과 어울리지 않는 어색한 기계적 직역은 금지합니다. 무조건 100% 자연스러운 의류/잡화 전문 쇼핑몰 용어로 의역하세요. (예: 简约圆领 -> 심플한 라운드넥, 无暇 -> 깔끔한 마감/완벽한 퀄리티)
0-1. [길이 제한] 본문 설명글을 너무 길고 장황하게 쓰지 마세요. 불필요한 미사여구를 빼고 상품의 핵심 특징만 간결하게 2~3가지 항목으로 축약하여 작성하세요.
0-2. [단어 교정] '러닝화'라는 단어는 절대 쓰지 마세요. 무조건 '런닝화' 혹은 '스니커즈'라는 단어로 대체하여 작성하세요.
0-3. [단어 치환] '이탈리아'라는 단어는 절대 쓰지 말고 무조건 '이태리'로 작성하세요. '정품'이라는 단어는 절대 쓰지 말고 무조건 '정규품싱크'로 작성하세요.
0-4. [군더더기 배제 및 인간화] 제품 특징/소재를 설명할 때 이미 단어 자체에 포함되어 있는 뻔한 설명이나 상업적 수식어(예: "~소재의 고급스러운 질감", "~공법의 디테일", "~자랑하는", "~를 사용하여 튼튼함" 등)는 완전히 빼세요. 불필요한 부연설명이나 미사여구를 모두 제거하고, 제품의 명확한 실물 사양/디테일만 딱부러지게 표현하세요.
    - 나쁜 예시: "이탈리아 수입 소가죽 소재의 고급스러운 질감", "정품 동일 공법의 로고 그래픽 디테일", "뛰어난 착화감을 자랑하는 특수 성형 밑창"
    - 좋은 예시: "이태리 수입 소가죽", "정규품싱크의 로고디테일", "뛰어난 착화감의 특수성형밑창"
1. [공통] 제목에 '[ 브랜드명 ]' 등 대괄호 태그는 절대 금지! 자연스럽게 첫 줄에 브랜드+상품명을 적을 것. 원문의 단가/금액/숫자 표시는 제목 생성 시 무조건 제외.
2. [공통] 컬러는 반드시 '✔ 컬러 : 블랙 / 화이트' 형태로 슬래시 구분 1줄. 사이즈는 아래 규칙 준수:
{size_rule_text}
3. [공통] 배송은 무조건 하단 양식처럼 '✔ 2박특송 : 입고 후 2 ~ 3일'과 '(개인통관부호 필수)'를 2줄로 추가할 것. 맨 마지막 줄에 코드나 ㄷㄱ를 임의로 생성하지 말 것.
4. [카카오스토리 버전 - kakao_text]
   '✔ 특징' 같은 라벨은 절대 쓰지 말고, 각 항목 앞에 '✔ ' 기호를 붙여서 바로 나열할 것. 항목들 위아래와 구분선(ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ) 사이에는 반드시 빈 줄(엔터 1~2번)을 넣어 칼각 정렬할 것. 장황한 설명 금지.
5. [네이버 밴드 버전 - band_text]
   친근한 소매상/단골 대상 어투 사용 ("언니들~ 이번에 들어온 신상...", "사장님들 퀄리티 미쳤어요 강추합니다!"). 카카오버전의 내용(컬러/사이즈/배송)은 하단에 동일하게 포함.
6. [인스타그램 버전 - insta_text]
   감성적이고 트렌디한 설명. 개조식(✔)보다는 자연스러운 줄글 형태로 작성하고, 해시태그를 본문 맨 아래 자연스럽게 배치. 컬러/사이즈/배송 정보는 심플하게 포함.
7. [소재 및 디테일 시각 추출 - core_material]
   텍스트 원문에 기재되지 않았더라도, 첨부된 사진들을 시각적으로 분석하여 질감(가죽, 니트, 트위드 등), 주요 디테일(금장 로고, 체인 스트랩, 퀄팅 패턴 등), 그리고 카테고리(원피스, 토트백 등)를 직접 찾아내어 번역본 본문에 자연스럽게 반영할 것. 그 중 가장 핵심적인 프리미엄 소재 1~2단어만 추출하여 이 필드에 담을 것. (예: "최고급 램스킨", "캐시미어 혼방").
8. [해시태그 - hashtags]
   인스타그램 등에 쓸 최적의 한글 해시태그 5개를 배열로 생성.
9. [브랜드 추론 - detected_brand]
   원문에 은어나 알파벳 약어로 표기된 명품 브랜드명(예: sch/Schiapa -> Schiaparelli, lv -> Louis Vuitton, cc/C사 -> Chanel, h/H사 -> Hermes, d/D사 -> Dior, p/P사 -> Prada, b/B사 -> Balenciaga, g/G사 -> Gucci 등)이 있다면 이를 정식 명칭으로 풀어내어 번역본 제목 및 detected_brand에 정확히 반영할 것. 약어가 없거나 모를 경우 원문 그대로 사용.
10. [시각적 특징 추출 - visual_features]
사진에서 눈에 띄는 핵심 디자인 포인트 2~3가지를 짧은 문장 배열로 추출할 것. (예: ["클래식한 퀼팅 패턴", "전면 골드 메탈 로고 장식"])
11. [단가 추출 초고도화 - ai_extracted_price]
원문 텍스트에 기재된 도매가(예: P150, 💰150, ¥150, 批150) 또는 첨부된 이미지의 워터마크, 배경의 가격표 등을 시각적으로 꼼꼼히 분석하여 최종 도매가(위안화)를 숫자로만 추출하세요. 단, 搜索码/搜素码/货号/款号/编号/SKU 뒤의 숫자는 상품 식별번호이지 단가가 아니므로 가격으로 쓰지 마세요. 단가를 찾을 수 없으면 0입니다.
12. [복수 상품 혼합 주의]
원문에 여러 상품(구찌, 루이비통 등)의 설명이 섞여서 기재되어 있을 경우, 제공된 첨부 사진들에 해당하는 상품의 설명만 골라서 번역할 것. 다른 상품들의 설명은 과감히 버릴 것.
13. [사진 순서 - ordered_images]
ordered_images는 최대 20개 파일명만 반환하세요.
특히 색상이 3개 이상인 상품(특히 신발류)의 경우:
- 대표 색상(블랙이나 화이트가 있다면 우선 선정, 없으면 가장 대표적인 색상) 1개를 선정하여 해당 색상의 모든 뷰(앞/뒤 대표컷 및 상세 디테일 컷)를 우선 정렬하세요.
- 나머지 보조 색상들은 상세 디테일 컷을 완전히 배제하고 오직 각 색상당 정면 대표컷 '딱 1장씩'만 선정하여 대표 색상 디테일 컷 뒤에 일렬로 배치하세요.
- 사이즈표가 있으면 반드시 가장 마지막에 둡니다.
- 예시 순서: [대표색상 앞/뒤 대표컷] -> [대표색상 디테일컷] -> [보조색상1 정면 1장] -> [보조색상2 정면 1장] -> [사이즈표]
- 같은 제품의 색상/디테일/사이즈표를 서로 다른 상품처럼 분리하지 마세요.

[중국어 원문]:
{raw_text}"""

        contents_payload = []
        img_paths = product.get('local_image_paths', [])
        file_name_map = {}
        if img_paths:
            for img_path in img_paths[:9]:
                if os.path.exists(img_path):
                    try:
                        with open(img_path, 'rb') as f:
                            img_bytes = f.read()
                        basename = os.path.basename(img_path)
                        file_name_map[basename] = img_path
                        contents_payload.append(f"[사진 파일명: {basename}]")
                        contents_payload.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
                    except Exception:
                        pass
        contents_payload.append(prompt)

        out_data = {}
        if cached_result:
            try:
                out_data = json.loads(cached_result)
                self.add_log(f"  ⚡ [Cache Hit] 번역 캐시를 활용하여 API 호출을 생략했습니다.", "INFO", False)
            except Exception:
                out_data = {}

        if not out_data:
            model_chain = ['gemini-3.1-flash-lite', 'gemini-2.5-flash', 'gemini-1.5-flash-latest']

            for current_model in model_chain:
                is_success = False
                for attempt in range(1, 3):
                    try:
                        res = client.models.generate_content(
                            model=current_model,
                            contents=contents_payload,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=types.Schema(
                                    type="OBJECT",
                                    properties={
                                        "raw_korean_translation": {"type": "STRING", "description": "[필수 사고과정] 원문을 100% 한글로 직역한 결과. 어떠한 중국어(한자)도 포함되어서는 안 됨. 이 필드를 가장 먼저 작성하세요."},
                                        "detected_brand": {"type": "STRING", "description": "로고나 디자인 기반 한글 브랜드명. 없으면 빈 문자열."},
                                        "kakao_text": {"type": "STRING", "description": "카카오스토리용 정형화된 개조식 템플릿 번역본."},
                                        "band_text": {"type": "STRING", "description": "네이버 밴드용 친근한 어투의 번역본."},
                                        "insta_text": {"type": "STRING", "description": "인스타그램용 감성적인 줄글 형태 번역본."},
                                        "core_material": {"type": "STRING", "description": "사진과 텍스트에서 추출한 핵심 프리미엄 소재 1~2단어 (예: '최고급 송아지 가죽'). 없으면 빈 문자열."},
                                        "visual_features": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "사진에서 포착된 디자인 포인트 2~3개 (예: '골드 체인 스트랩')"},
                                        "hashtags": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "최적의 한글 해시태그 5개 배열"},
                                        "ai_extracted_price": {"type": "INTEGER", "description": "텍스트 및 사진에서 찾아낸 최종 도매가 숫자. 없으면 0"},
                                        "ordered_images": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "최대 20개. 색상별 앞/뒤 대표컷 → 대표색상 디테일 → 사이즈표 마지막 순서의 파일명 배열"}
                                    },
                                    required=["raw_korean_translation", "detected_brand", "kakao_text", "band_text", "insta_text", "core_material", "visual_features", "hashtags", "ordered_images", "ai_extracted_price"]
                                )
                            )
                        )

                        if res and res.text:
                            try:
                                out_data = json.loads(res.text)

                                # CRITIC Loop
                                if use_critic and critic_prompt and out_data:
                                    critic_payload = [
                                        critic_prompt,
                                        f"== [1차 번역본 결과] ==\n{json.dumps(out_data, ensure_ascii=False, indent=2)}\n\n위 결과를 평가하고 최종 JSON을 출력하세요."
                                    ]
                                    try:
                                        critic_res = client.models.generate_content(
                                            model=current_model,
                                            contents=critic_payload,
                                            config=types.GenerateContentConfig(
                                                response_mime_type="application/json",
                                                response_schema=types.Schema(
                                                    type="OBJECT",
                                                    properties={
                                                        "status": {"type": "STRING", "description": "PASS 또는 FAIL"},
                                                        "feedback": {"type": "STRING", "description": "FAIL일 경우 구체적 개선 이유, PASS면 빈 문자열"},
                                                        "corrected_data": {"type": "OBJECT", "description": "PASS면 1차 결과 유지, FAIL이면 개선된 전체 필드를 포함하는 객체"}
                                                    },
                                                    required=["status", "feedback", "corrected_data"]
                                                )
                                            )
                                        )
                                        if critic_res and critic_res.text:
                                            critic_data = json.loads(critic_res.text)
                                            if critic_data.get("status") == "FAIL":
                                                self.add_log(f"  🤖 [Critic 개입] 품질 미달(FAIL) → 재번역 실시. 사유: {critic_data.get('feedback')}", "WARNING")
                                                out_data = critic_data.get("corrected_data", out_data)
                                            else:
                                                self.add_log(f"  ✅ [Critic 통과] 번역 품질 우수(PASS).", "SUCCESS")
                                    except Exception as critic_e:
                                        self.add_log(f"  ⚠️ [Critic 실패] 평가 중 오류 발생, 1차 결과 유지: {critic_e}", "WARNING")

                                if use_translation_cache:
                                    database.set_cached_translation(raw_text, json.dumps(out_data, ensure_ascii=False), final_cat, first_img_file)
                            except Exception:
                                out_data = {}
                            is_success = True
                            break # 성공했으므로 재시도 루프 탈출
                    except Exception as e:
                        err_str = str(e).lower()
                        is_not_found = '404' in err_str or 'not found' in err_str
                        is_overload = '429' in err_str or '503' in err_str or 'rate' in err_str or 'quota' in err_str or 'unavailable' in err_str

                        if is_not_found:
                            self.add_log(f"  ⚠️ [AI 폴백] '{current_model}' 미지원. 다음 모델로 우회합니다.", "WARNING")
                            break # 즉시 다음 모델로 넘어감

                        if is_overload and attempt < 2:
                            self.add_log(f"  ⚠️ [AI 과부하] {current_model} 에러 발생. 5초 후 재시도... ({attempt}/2)", "WARNING")
                            time.sleep(5)
                            continue
                        else:
                            self.add_log(f"  ⚠️ [AI 실패] {current_model} 에러: {e}. 다음 모델로 우회합니다.", "WARNING")
                            break # 다음 모델로 넘어감

                if is_success:
                    break # 성공했으므로 모델 루프 탈출

        kakao_text = out_data.get("kakao_text", "")
        band_text = out_data.get("band_text", "")
        insta_text = out_data.get("insta_text", "")
        core_material = out_data.get("core_material", "").strip()
        hashtags = out_data.get("hashtags", [])
        d_brand = pricing_logic.extract_brand_from_text(raw_text, out_data.get("detected_brand", "").strip())
        ordered_images_list = out_data.get("ordered_images", [])

        # --- 사후 한글 보정 및 인간화 필터 적용 ---
        def apply_humanized_translation_rules(text: str) -> str:
            if not text:
                return text
            # 1. 단어 단순 치환
            text = text.replace("이탈리아", "이태리")
            
            # 2. 군더더기 및 상업적 미사여구 배제 (인간화)
            # 가죽 계열의 고급스러운/부드러운 질감 제거
            text = re.sub(
                r"이태리\s*수입\s*(소가죽|양가죽|가죽)\s*(소재)?\s*(의)?\s*(고급스러운|부드러운|뛰어난)?\s*질감",
                r"이태리 수입 \1",
                text
            )
            text = text.replace("이태리 수입 소가죽 소재의 고급스러운 질감", "이태리 수입 소가죽")
            text = text.replace("이태리 수입 소가죽의 고급스러운 질감", "이태리 수입 소가죽")
            text = text.replace("이태리 수입 소가죽 고급스러운 질감", "이태리 수입 소가죽")
            text = text.replace("이태리 수입 소가죽 소재의 부드러운 질감", "이태리 수입 소가죽")
            text = text.replace("이태리 수입 소가죽의 부드러운 질감", "이태리 수입 소가죽")

            # 정품 동일 공법의 로고 디테일 제거 및 치환
            text = re.sub(
                r"정품\s*(동일\s*공법|동일공법)\s*(의)?\s*로고\s*(그래픽)?\s*디테일",
                "정규품싱크의 로고디테일",
                text
            )
            text = text.replace("정품 동일 공법의 로고 그래픽 디테일", "정규품싱크의 로고디테일")
            text = text.replace("정품 동일 공법의 로고 디테일", "정규품싱크의 로고디테일")
            text = text.replace("정품 동일공법의 로고 디테일", "정규품싱크의 로고디테일")
            text = text.replace("정품동일공법의 로고 디테일", "정규품싱크의 로고디테일")

            # 뛰어난 착화감 자랑 및 특수 성형 밑창 교정
            text = re.sub(
                r"뛰어난\s*착화감(을)?\s*자랑하는\s*특수\s*성형\s*밑창",
                "뛰어난 착화감의 특수성형밑창",
                text
            )
            text = text.replace("뛰어난 착화감을 자랑하는 특수 성형 밑창", "뛰어난 착화감의 특수성형밑창")
            text = text.replace("뛰어난 착화감을 자랑하는 특수성형밑창", "뛰어난 착화감의 특수성형밑창")
            text = text.replace("뛰어난 착화감 자랑하는 특수 성형 밑창", "뛰어난 착화감의 특수성형밑창")
            text = text.replace("뛰어난 착화감의 특수 성형 밑창", "뛰어난 착화감의 특수성형밑창")

            # 정품 동일 -> 정규품싱크
            text = re.sub(r"정품\s*동일", "정규품싱크", text)
            text = text.replace("정품", "정규품싱크")

            return text

        # 각 플랫폼용 텍스트 및 해시태그에 보정 필터 일괄 적용
        kakao_text = apply_humanized_translation_rules(kakao_text)
        band_text = apply_humanized_translation_rules(band_text)
        insta_text = apply_humanized_translation_rules(insta_text)

        # 기본 UI 표시용으로는 kakao_text를 기준(기존 호환성)으로 합니다.
        f_text = kakao_text

        if f_text:
            final_text, final_title, _, _ = pricing_logic.parse_gemini_translation_common(f_text, "AUTO", d_brand, vendor_name)

            # 소재 부각 하이라이트 강제 주입 로직 제거 (사용자가 설정한 프론트엔드 스타일만 따르도록 수정)
            # if core_material:
            #     material_highlight = f"\n✨ 소재 포인트: {core_material}\nㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n"
            #     if "ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ" in final_text:
            #         final_text = final_text.replace("ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ", f"ㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ{material_highlight}", 1)
            #     else:
            #         final_text = f"{final_title}\n{material_highlight}{final_text}"

            price_input = product.get('price_input', '0')

            ai_price = out_data.get("ai_extracted_price", 0)
            # 기존 수집 단가가 없거나 유효하지 않은 경우 판별
            is_existing_price_invalid = str(price_input).strip() in ("", "0", "-", "단가미상")
            
            # economy 또는 minimum 예산 모드일지라도 기존 가격이 없거나 유효하지 않은 경우에는 AI 초고도화 단가를 폴백 적용함
            if isinstance(ai_price, int) and ai_price > 0:
                if is_existing_price_invalid or ai_budget_mode not in ["economy", "minimum"]:
                    self.add_log(f"  🔍 [AI 초고도화 단가 적용] 기존 단가({price_input}) 대신 AI(Vision+Text)가 추출한 단가({ai_price})를 최종 적용합니다.", "INFO", False)
                    price_input = str(ai_price)
                else:
                    self.add_log(f"  🔍 [AI 초고도화 단가 미적용] AI 단가({ai_price})가 추출되었으나 예산 모드({ai_budget_mode}) 정책에 의해 기존 수집 단가({price_input})를 유지합니다.", "INFO", False)

            vendor_name = product.get('vendor_name', 'Unknown')

            item_code_preview, cat_preview = pricing_logic.determine_item_category(category, final_title, raw_text)

            generated_code, computed_sale_price, dg_display_str, calc_log = pricing_logic.generate_product_code_and_price(
                vendor_name, price_input, final_cat or category, final_title, raw_text, base_fx
            )
            price_detected = bool(str(price_input).strip() not in ("", "0", "-", "단가미상"))
            if not price_detected:
                try:
                    get_db().record_crawl_event(
                        platform="weishang",
                        event_type="price_parse_failed",
                        vendor_id=product.get("vendor_id", ""),
                        vendor_name=vendor_name,
                        reason="translation_price_missing",
                        raw_text=raw_text,
                        metadata={"final_cat": final_cat or category, "title": final_title},
                    )
                except Exception:
                    pass

            final_text = re.sub(r'^.*?(?:[A-Za-z0-9_-]{10,}|AUTO)\s*$', '', final_text, flags=re.MULTILINE)
            final_text = re.sub(r'^(?:ㄷㄱ|단가|판매가|가격)\s*[:：]?\s*.*$', '', final_text, flags=re.MULTILINE)
            final_text = final_text.strip()
            final_text = final_text + f"\n\n{generated_code}\nㄷㄱ {dg_display_str}"

            # --- AI 사진 순서 교정 반영 ---
            new_image_files = []
            new_local_image_paths = []
            if ordered_images_list and isinstance(ordered_images_list, list) and len(ordered_images_list) > 0:
                for base in ordered_images_list:
                    if base in product.get('image_files', []):
                        new_image_files.append(base)
                        if base in file_name_map:
                            new_local_image_paths.append(file_name_map[base])
                
                # 신발류(Footwear)인 경우 누락된 보조 이미지를 강제로 뒤에 덧붙이지 않고 완전히 배제
                cat_lower = (final_cat or category or "").lower()
                is_footwear = any(k in cat_lower for k in ["신발", "슬리퍼", "샌들", "스니커즈", "부츠", "로퍼", "뮬", "구두", "운동화"])
                
                if not is_footwear:
                    # 신발류가 아닐 때만 누락된 나머지 사진들을 뒤에 안전장치로 추가
                    for item_img in product.get('image_files', []):
                        if item_img not in new_image_files:
                            new_image_files.append(item_img)
                            if item_img in file_name_map:
                                new_local_image_paths.append(file_name_map[item_img])

            with self.lock:
                self.crawled_products[idx]['title'] = final_title
                self.crawled_products[idx]['raw_description'] = final_text
                self.crawled_products[idx]['band_text'] = band_text
                self.crawled_products[idx]['insta_text'] = insta_text
                self.crawled_products[idx]['hashtags'] = hashtags
                self.crawled_products[idx]['product_code'] = generated_code
                self.crawled_products[idx]['sale_price'] = str(computed_sale_price)
                self.crawled_products[idx]['price_input'] = str(price_input)
                self.crawled_products[idx]['price_detected'] = price_detected
                self.crawled_products[idx]['calc_log'] = calc_log
                if new_image_files:
                    self.crawled_products[idx]['image_files'] = new_image_files
                    self.crawled_products[idx]['local_image_paths'] = new_local_image_paths
                if hasattr(self, 'retranslate_progress') and self.retranslate_progress.get('running', False):
                    self.retranslate_progress["current"] += 1

            get_db().update_product_by_index(idx, self.crawled_products[idx])
            self.notify_update()
            brand_info = f" | 브랜드:{d_brand}" if d_brand else ""
            self.add_log(
                f"  ✅ [{seq+1}] 완료 ▸ 제목:{final_title[:25]} | 코드:{generated_code} | ㄷㄱ:{dg_display_str} ({computed_sale_price:,}원){brand_info}",
                "SUCCESS", False
            )
            return True
        else:
            self.add_log(f"⚠️ [{seq+1}] 빈 응답 및 번역 실패", "WARNING", False)
            return False


    def start_batch_retranslate(self, api_key: str, category: str, naver_fx: float, target_indices: list = None, custom_prompt: str = "", use_critic: bool = False, critic_prompt: str = ""):
        """이미 수집된 상품(중국어 원문 보유)에 대해 병렬 번역을 백그라운드에서 수행"""
        if not hasattr(self, 'retranslate_progress'):
            self.retranslate_progress = {"current": 0, "total": 0, "running": False, "failed": 0}

        if getattr(self, '_retranslate_running', False):
            self.add_log("⚠️ 이미 재번역 프로세스가 실행 중입니다.", "WARNING")
            return

        if not api_key:
            self.add_log("⚠️ Gemini API 키가 없어 재번역을 수행할 수 없습니다.", "WARNING")
            return

        if not self.crawled_products:
            self.add_log("⚠️ 재번역할 상품 데이터가 없습니다.", "WARNING")
            return

        indices = target_indices if target_indices is not None else list(range(len(self.crawled_products)))
        valid_indices = [i for i in indices if 0 <= i < len(self.crawled_products) and self.crawled_products[i].get('original_chinese')]

        if not valid_indices:
            self.add_log("⚠️ 중국어 원문을 보관중인 재번역 대상이 없습니다.", "WARNING")
            return

        self.retranslate_progress = {"current": 0, "total": len(valid_indices), "running": True, "failed": 0}
        self._retranslate_running = True
        self._retranslate_stop = False

        PARALLEL_WORKERS = 5

        def _worker_thread():
            import time
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def _translate_one(task, use_critic=False, critic_prompt=""):
                seq, idx = task
                return self.translate_single_item(
                    idx, api_key, category, naver_fx,
                    custom_prompt=custom_prompt,
                    use_critic=use_critic,
                    critic_prompt=critic_prompt,
                    seq=seq,
                    total=len(valid_indices)
                )

            failed_count = 0
            tasks = [(seq, idx) for seq, idx in enumerate(valid_indices)]
            self.add_log(f"🚀 {PARALLEL_WORKERS}개 병렬 재번역 자동 시작 (총 {len(tasks)}개)", "INFO")

            with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
                futures = {executor.submit(_translate_one, t, use_critic=use_critic, critic_prompt=critic_prompt): t for t in tasks}
                for future in as_completed(futures):
                    if getattr(self, '_retranslate_stop', False):
                        self.add_log("🛑 재번역 중단 요청됨.", "WARNING")
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    try:
                        result = future.result()
                        if not result: failed_count += 1
                    except Exception as e:
                        failed_count += 1
                        self.add_log(f"❌ 스레드 오류: {str(e)[:60]}", "ERROR")

            # self.save_temp_data() deprecated in Phase 3
            self.retranslate_progress["running"] = False
            self.retranslate_progress["failed"] = failed_count
            self._retranslate_running = False
            completed = self.retranslate_progress["current"]
            self.add_log(f"✅ 병렬 재번역 완료! (성공: {completed}, 실패: {failed_count})", "INFO")

        import threading
        t = threading.Thread(target=_worker_thread, daemon=True, name="AI번역")
        t.start()
    # ─── 정지 ──────────────────────────────────────────────────────────────
    def stop_all(self):
        """모든 크롤링/포스팅 스레드를 중지한다."""
        self.stop_flag = True

        # 크롤러/포스터 내부 stop_flag도 설정
        if self._source_crawler and hasattr(self._source_crawler, 'stop_flag'):
            self._source_crawler.stop_flag = True
        if self._target_poster and hasattr(self._target_poster, 'stop_flag'):
            self._target_poster.stop_flag = True

        self.add_log("🛑 모든 작업 정지 신호 전송됨...")

    # ─── 드라이버 정리 ─────────────────────────────────────────────────────
    def cleanup(self):
        """열린 모든 드라이버를 종료한다."""
        for name, driver in [("소스", self.source_driver), ("타겟", self.target_driver)]:
            if driver:
                try:
                    driver.quit()
                    self.add_log(f"✅ {name} 드라이버 종료")
                except Exception as e:
                    self.add_log(f"⚠️ {name} 드라이버 종료 오류: {e}")
        self.source_driver = None
        self.target_driver = None
        if self._source_crawler:
            if hasattr(self._source_crawler, 'close_browser'):
                try:
                    self._source_crawler.close_browser()
                except Exception as e:
                    self.add_log(f"⚠️ 소스 크롤러 close_browser 오류: {e}")
            self._source_crawler = None
        if self._target_poster:
            self._target_poster = None


# ─── 싱글톤 인스턴스 ────────────────────────────────────────────────────────
engine_instance = None

def get_engine():
    global engine_instance
    if engine_instance is None:
        # 파이썬의 중복 임포트(Double Import)로 인해 서로 다른 네임스페이스로 로드되었더라도
        # 동일한 메모리 인스턴스를 리턴하여 싱글톤을 철저히 보장합니다.
        import sys
        other_engine = None
        for mod_name in ('backend.crawler_engine', 'crawler_engine'):
            if mod_name in sys.modules:
                mod = sys.modules[mod_name]
                if hasattr(mod, 'engine_instance') and mod.engine_instance is not None:
                    other_engine = mod.engine_instance
                    break
        
        # 파일 경로 기준 역추적 보완 가드 (임포트 네임스페이스가 위 두 개와 다른 변종인 경우 대비)
        if other_engine is None:
            for mod in list(sys.modules.values()):
                if mod is not None:
                    file_path = getattr(mod, '__file__', None)
                    if file_path and ('crawler_engine.py' in file_path or 'crawler_engine.pyc' in file_path):
                        if hasattr(mod, 'engine_instance') and mod.engine_instance is not None:
                            other_engine = mod.engine_instance
                            break

        if other_engine is not None:
            engine_instance = other_engine
        else:
            engine_instance = CrawlerEngine()
    return engine_instance
