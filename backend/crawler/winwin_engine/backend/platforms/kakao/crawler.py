"""
kakao_crawler.py
────────────────
SourceCrawler 의 카카오스토리 구현체.

기존 winwin58.py 의 CrawlingThread + start_login() 로직을 이 클래스로 통합.
winwin58.py 의 CrawlingThread 는 이 클래스에 위임(delegation)하여 하위호환을 유지한다.
"""

import os
import re
import time
import json
import concurrent.futures
import requests
from datetime import datetime, timedelta

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

import undetected_chromedriver as uc
from core.driver_manager import create_uc_driver

from backend.browser_sensors import apply_quiet_chrome_options
from platform_base import SourceCrawler


# ── 공통 유틸: winwin58.py 에 있는 함수들을 여기서 직접 import ──────────────
# (winwin58.py 가 이미 실행 중인 환경에서는 같은 네임스페이스를 공유하지만,
#  독립 실행 시에도 동작하도록 try/except 로 감싼다.)
def _import_utils():
    """winwin58 유틸 함수를 런타임에 import."""
    try:
        from category_data import get_final_code, generate_product_code
        from text_constants import replace_emoji_to_basic
    except ImportError:
        get_final_code = generate_product_code = replace_emoji_to_basic = None

    try:
        # winwin58 모듈이 로드된 환경
        import winwin58 as _w
        transform_fn  = getattr(_w, "transform_kakao_story_text_alt", None)
        parse_ddg     = getattr(_w, "parse_ddg_value", None)
        compute_price = getattr(_w, "compute_sale_price", None)
        create_driver = getattr(_w, "_create_uc_driver", None)
    except ImportError:
        transform_fn = parse_ddg = compute_price = create_driver = None

    return {
        "get_final_code":                get_final_code,
        "generate_product_code":         generate_product_code,
        "transform_kakao_story_text_alt": transform_fn,
        "parse_ddg_value":               parse_ddg,
        "compute_sale_price":            compute_price,
        "_create_uc_driver":             create_driver,
    }


class KakaoCrawler(SourceCrawler):
    """
    카카오스토리 크롤러.

    사용법:
        crawler = KakaoCrawler()
        crawler.set_log_func(self.log)          # UI 로그 주입 (선택)
        crawler.login(user_id, user_pw)
        items = crawler.crawl(start, end, 50, "여성의류", "./images")
        crawler.quit()
    """

    def __init__(self, driver=None, profile_manager=None):
        """
        Args:
            driver:          기존 uc.Chrome 드라이버 인스턴스 (재사용 시)
            profile_manager: ProfileManager 인스턴스 (프로필 적용 시)
        """
        super().__init__()
        self.driver          = driver
        self.profile_manager = profile_manager
        self._utils          = _import_utils()

    # ── 내부 헬퍼 ──────────────────────────────────────────────────────────
    @staticmethod
    def _detect_chrome_version():
        """설치된 Chrome 메이저 버전을 미리 감지한다."""
        import subprocess, re as _re
        # 방법 1: 레지스트리 조회 (Windows)
        try:
            result = subprocess.run(
                ['reg', 'query', r'HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon', '/v', 'version'],
                capture_output=True, text=True, timeout=5
            )
            m = _re.search(r'(\d+)\.\d+\.\d+\.\d+', result.stdout)
            if m:
                return int(m.group(1))
        except Exception:
            pass
        # 방법 2: chrome.exe --version
        chrome_paths = [
            os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
        ]
        for cp in chrome_paths:
            if os.path.exists(cp):
                try:
                    result = subprocess.run([cp, '--version'], capture_output=True, text=True, timeout=5)
                    m = _re.search(r'(\d+)\.', result.stdout)
                    if m:
                        return int(m.group(1))
                except Exception:
                    pass
        return None

    @staticmethod
    def _clean_session_files(profile_dir):
        """프로필 디렉터리의 이전 세션 파일을 삭제하여 탭 복원을 방지한다."""
        if not profile_dir or not os.path.isdir(profile_dir):
            return
        session_files = [
            'Current Session', 'Current Tabs',
            'Last Session', 'Last Tabs',
            os.path.join('Default', 'Current Session'),
            os.path.join('Default', 'Current Tabs'),
            os.path.join('Default', 'Last Session'),
            os.path.join('Default', 'Last Tabs'),
        ]
        for sf in session_files:
            fp = os.path.join(profile_dir, sf)
            try:
                if os.path.exists(fp):
                    os.remove(fp)
            except Exception:
                pass

        sessions_dir = os.path.join(profile_dir, 'Default', 'Sessions')
        try:
            if os.path.isdir(sessions_dir):
                for name in os.listdir(sessions_dir):
                    if name.startswith(('Session_', 'Tabs_')):
                        try:
                            os.remove(os.path.join(sessions_dir, name))
                        except Exception:
                            pass
        except Exception:
            pass

        prefs_path = os.path.join(profile_dir, 'Default', 'Preferences')
        try:
            if os.path.exists(prefs_path):
                # ─── [자가 치유 가드레일] Preferences 비정상 비대화(OOM 프리징) 차단 ───
                prefs_size = os.path.getsize(prefs_path)
                if prefs_size > 10 * 1024 * 1024:  # 10MB 초과 시 비정상 손상 파일로 간주하여 자동 청소
                    try:
                        os.remove(prefs_path)
                    except Exception:
                        pass
                    return

                with open(prefs_path, 'r', encoding='utf-8') as f:
                    prefs = json.load(f)
                profile = prefs.setdefault('profile', {})
                profile['exit_type'] = 'Normal'
                profile['exited_cleanly'] = True
                with open(prefs_path, 'w', encoding='utf-8') as f:
                    json.dump(prefs, f, ensure_ascii=False, separators=(',', ':'))
        except Exception:
            pass

    def _create_driver(self, options, profile_dir=None):
        """
        core.driver_manager.create_uc_driver를 호출하여 안전하게 Chrome 실행.
        """
        # 세션 파일 삭제 → 탭 복원 차단
        if profile_dir:
            self._clean_session_files(profile_dir)

        # 공용 드라이버 매니저 호출 (Windows 환경 안정성을 위해 use_subprocess=True 유지)
        return create_uc_driver(options, use_subprocess=True, log_func=self._log_func)

    def _build_chrome_options(self, profile_dir=None):
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")
        options.add_argument("--window-size=1500,900")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        # 세션/탭 복원 차단
        options.add_argument("--disable-session-crashed-bubble")
        options.add_argument("--hide-crash-restore-bubble")
        apply_quiet_chrome_options(options)
        if profile_dir:
            options.add_argument(f"--user-data-dir={profile_dir}")
        return options

    # ── SourceCrawler 구현 ────────────────────────────────────────────────

    def login(self, user_id: str, user_pw: str, profile_name: str = "메인") -> bool:
        """
        카카오스토리 로그인.
        기존 KakaoCrawlerUI.start_login() 의 드라이버 생성 + 로그인 로직을 이전.
        """
        self.log(f"{user_id} 로 카카오스토리 로그인 시작...")

        # 1) 기존 드라이버 유효성 확인
        if self.driver is not None:
            try:
                _ = self.driver.title
                self.log("기존 드라이버 재사용")
                profile_dir = None
            except Exception as e:
                self.log(f"⚠️ 기존 드라이버 세션 만료: {e}. 새로 실행합니다.")
                self.driver = None

        # 2) 드라이버 새로 생성
        if self.driver is None:
            profile_dir = None
            try:
                # 프로필 적용
                if self.profile_manager and profile_name:
                    try:
                        profile_dir = self.profile_manager.get_profile_dir(
                            profile_name, platform="kakao"
                        )
                        self.log(f"카카오 프로필 적용: {profile_name}")
                    except Exception as e:
                        self.log(f"⚠️ 프로필 적용 실패 (새 프로필로 진행): {e}")
                        profile_dir = None

                options = self._build_chrome_options(profile_dir)
                try:
                    self.driver = self._create_driver(options, profile_dir)
                except Exception:
                    # 프로필 때문에 실패 시 → 프로필 없이 재시도
                    if profile_dir:
                        self.log("프로필 충돌 → 프로필 없이 재시도", "WARNING")
                        options2 = self._build_chrome_options()
                        self.driver = self._create_driver(options2)
                    else:
                        raise

                # 창 위치/크기 보정
                try:
                    self.driver.set_window_position(0, 0)
                    self.driver.set_window_size(1500, 900)
                except Exception:
                    pass

                self.log("✅ 크롬 실행 완료")

            except Exception as e:
                self.log(f"❌ 드라이버 실행 오류: {e}", "ERROR")
                return False

        # 3) 쿠키 삭제 (프로필 미사용 시만)
        if not profile_dir:
            try:
                self.driver.delete_all_cookies()
            except Exception as e:
                self.log(f"⚠️ 쿠키 삭제 실패: {e}")

        # 4) 카카오 로그인 페이지로 이동
        self.log("카카오스토리 로그인 페이지로 이동 중...")
        try:
            self.driver.get(
                "https://accounts.kakao.com/login?continue=https://story.kakao.com/"
            )
        except Exception as e:
            self.log(f"❌ 페이지 이동 실패: {e}", "ERROR")
            return False

        # 4-1) [추가] 로그인할 카카오계정 선택 화면 처리
        time.sleep(1.5)
        try:
            target_node = None
            
            # CSS Selector로 tit_profile 클래스를 선제 탐색
            spans = self.driver.find_elements(By.CSS_SELECTOR, "span.tit_profile")
            for span in spans:
                try:
                    if span.is_displayed() and user_id.lower() in span.text.lower():
                        target_node = span
                        self.log(f"📌 저장된 카카오계정 tit_profile 노드 발견: {span.text}")
                        break
                except Exception:
                    pass
            
            # CSS로 탐색 실패 시 XPath 텍스트 매칭 백업 작동
            if not target_node:
                try:
                    nodes = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{user_id}')]")
                    for node in nodes:
                        if node.is_displayed():
                            target_node = node
                            self.log("📌 XPath text() 매칭으로 계정 노드 발견")
                            break
                except Exception:
                    pass
            
            if target_node:
                self.log(f"📌 저장된 카카오계정({user_id}) 선택 화면 클릭을 수행합니다.")
                
                # 클릭 타겟 후보군 생성 (자식 노드 자체부터 상위 3대 조상 노드까지 순차적 감싸기)
                click_targets = [target_node]
                curr = target_node
                for _ in range(3):
                    try:
                        curr = curr.find_element(By.XPATH, "..")
                        if curr:
                            click_targets.append(curr)
                    except Exception:
                        break
                
                clicked = False
                for target in click_targets:
                    try:
                        tag = target.tag_name.lower()
                        if tag in ['a', 'button', 'li', 'span', 'div']:
                            target.click()
                            clicked = True
                            self.log(f"✅ 계정 노드 클릭 성공 (태그: {tag})")
                            break
                    except Exception:
                        pass
                
                # 일반 클릭이 막힐 경우 JavaScript를 통한 강제 클릭 실행
                if not clicked:
                    try:
                        self.driver.execute_script("arguments[0].click();", target_node)
                        self.log("✅ 계정 노드 JS click 강제 호출 완료")
                        clicked = True
                    except Exception as e:
                        self.log(f"⚠️ JS click 실패: {e}")
                
                if clicked:
                    time.sleep(3)
        except Exception as e:
            self.log(f"⚠️ 계정 선택 화면 처리 중 오류: {e}")

        try:
            current_url = self.driver.current_url
            if "story.kakao.com" in current_url and "login" not in current_url:
                self.log("✅ 계정 선택을 통해 로그인 성공 (스토리 홈 진입 완료)")
                return True
        except Exception:
            pass

        # 5) 로그인 폼 로드 대기
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "loginId--1"))
            )
        except Exception as e:
            self.log(f"로그인 페이지 로드 오류 (이미 로그인 상태일 수 있음): {e}")
            return True  # 이미 로그인된 경우로 간주

        # 6) 자동 입력
        try:
            email_field = self.driver.find_element(By.ID, "loginId--1")
            pw_field    = self.driver.find_element(By.ID, "password--2")
            email_field.clear()
            email_field.send_keys(user_id)
            pw_field.clear()
            pw_field.send_keys(user_pw)
            btn = self.driver.find_element(
                By.CSS_SELECTOR, "button.btn_g.highlight.submit"
            )
            btn.click()
            self.log("✅ 자동 입력 및 로그인 버튼 클릭 완료")
            time.sleep(2)
        except Exception:
            self.log("로그인 폼 없음 또는 이미 로그인 상태")

        return True

    def crawl(
        self,
        start_date,
        end_date,
        max_count: int,
        selected_cat_text: str,
        target_folder: str,
        transform_function=None,
        progress_callback=None,
        result_callback=None,
    ) -> list[dict]:
        """
        카카오스토리 게시물 크롤링.

        기존 CrawlingThread.run() 로직을 그대로 이전.

        Args:
            start_date:         datetime
            end_date:           datetime
            max_count:          최대 크롤링 수
            selected_cat_text:  카테고리 텍스트 (예: "여성의류")
            target_folder:      이미지 저장 폴더
            transform_function: 텍스트 변환 함수 (None 이면 내부 유틸 사용)
            progress_callback:  진행률 콜백 fn(count)
            result_callback:    결과 1건 콜백 fn(item_dict)

        Returns:
            공통 스키마 dict 목록
        """
        if self.driver is None:
            self.log("❌ 드라이버가 없습니다. 먼저 login()을 호출하세요.", "ERROR")
            return []

        # 유틸 함수 준비
        _transform = transform_function or self._utils.get("transform_kakao_story_text_alt")
        _parse_ddg  = self._utils.get("parse_ddg_value")
        _compute    = self._utils.get("compute_sale_price")
        _get_code   = self._utils.get("get_final_code")
        _gen_code   = self._utils.get("generate_product_code")

        results    = []
        count      = 0
        posts_sel  = "div.section._activity"
        self.stop_flag = False

        self.log("🔁 카카오스토리 크롤링 시작")

        # ── 드라이버 유효성 확인 ────────────────────────────────────────
        try:
            _ = self.driver.title
            self.log("✅ 드라이버 연결 양호")
        except Exception as e:
            self.log(f"⚠️ 드라이버 세션 유효하지 않음: {e}", "WARNING")
            return []

        # ── 초기 스크롤 ─────────────────────────────────────────────────
        try:
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            last_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
        except Exception as e:
            self.log(f"❌ 초기 스크롤 실패: {e}", "ERROR")
            return []

        # ── 메인 크롤링 루프 ────────────────────────────────────────────
        while count < max_count and not self.stop_flag:
            try:
                posts = self.driver.find_elements(By.CSS_SELECTOR, posts_sel)
                self.log(f"현재 게시물 개수: {len(posts)}")
            except Exception as e:
                self.log(f"❌ 게시물 찾기 오류: {e}")
                break

            # 게시물이 부족하면 스크롤
            if len(posts) <= count:
                try:
                    old_post_count = len(posts)
                    retries = 3
                    while retries > 0:
                        if posts:
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", posts[-1])
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(2)
                        
                        posts = self.driver.find_elements(By.CSS_SELECTOR, posts_sel)
                        if len(posts) > old_post_count:
                            break
                            
                        # 약간 위로 올렸다가 다시 끝까지 스크롤하여 로딩 트리거
                        self.driver.execute_script("window.scrollBy(0, -500);")
                        time.sleep(1)
                        if posts:
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", posts[-1])
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(2)
                        
                        posts = self.driver.find_elements(By.CSS_SELECTOR, posts_sel)
                        if len(posts) > old_post_count:
                            break
                            
                        retries -= 1

                    if len(posts) <= old_post_count:
                        self.log("더 이상 게시물이 없습니다. (최종)")
                        break
                    continue
                except Exception as e:
                    self.log(f"❌ 스크롤 오류: {e}")
                    break

            # 게시물 배치 처리 (3개씩 병렬 이미지 다운로드)
            BATCH_SIZE = 3
            pending_posts = posts[count:]
            batch_start = 0

            while batch_start < len(pending_posts) and count < max_count and not self.stop_flag:
                batch = pending_posts[batch_start:batch_start + BATCH_SIZE]
                batch_start += len(batch)

                # ── 1단계: DOM에서 데이터 순차 추출 (Selenium 제약) ──
                extracted = []
                for post in batch:
                    if count + len(extracted) >= max_count or self.stop_flag:
                        break
                    try:
                        post_date = self._extract_post_date(post)
                        if not post_date:
                            self.log("날짜 정보 없음, 건너뜁니다.")
                            continue

                        if not (start_date <= post_date <= end_date):
                            self.log(
                                f"날짜 범위 밖: {post_date} "
                                f"({start_date} ~ {end_date})"
                            )
                            if post_date < start_date:
                                self.log("더 오래된 게시물 → 크롤링 종료")
                                self.stop_flag = True
                            continue

                        try:
                            content_el = post.find_element(
                                By.CSS_SELECTOR, "div.fd_cont div._content"
                            )
                            raw_text = content_el.text.strip()
                        except Exception as e:
                            self.log(f"❌ 본문 추출 오류: {e}")
                            raw_text = ""

                        # 이미지 URL 수집 (다운로드는 아직 안 함)
                        img_tasks = []
                        try:
                            images = post.find_elements(
                                By.CSS_SELECTOR, "div.wrap_swipe img, div.cont_media img, div.media_wrap img, a._linkMedia img, a._btnZoom img"
                            )
                            for idx, img in enumerate(images):
                                src = img.get_attribute("src")
                                if src:
                                    ts = datetime.now().strftime("%Y%m%d%H%M%S")
                                    filename = f"{ts}_{count + len(extracted) + 1}_{idx + 1}.jpg"
                                    filepath = os.path.join(target_folder, filename)
                                    img_tasks.append((src, filepath, filename))
                        except Exception as e:
                            self.log(f"⚠️ 이미지 URL 수집 오류: {e}")

                        extracted.append({
                            "post_date": post_date,
                            "raw_text": raw_text,
                            "img_tasks": img_tasks,
                        })
                    except Exception as e:
                        self.log(f"⚠️ 게시물 데이터 추출 오류: {e}")
                        continue

                if not extracted:
                    continue

                # ── 2단계: 이미지 병렬 다운로드 (3개 게시물 동시) ──
                all_img_tasks = []
                for ex in extracted:
                    all_img_tasks.extend(ex["img_tasks"])

                def _dl(args):
                    src, path, _ = args
                    try:
                        r = requests.get(src, timeout=5)
                        with open(path, "wb") as f:
                            f.write(r.content)
                        return True
                    except Exception:
                        return False

                if all_img_tasks:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
                        ok_list = list(ex.map(_dl, all_img_tasks))
                else:
                    ok_list = []

                # 다운로드 결과를 각 게시물별로 분배
                dl_offset = 0
                for ei, ex_data in enumerate(extracted):
                    task_count = len(ex_data["img_tasks"])
                    ex_data["image_files"] = [
                        ex_data["img_tasks"][j][2]
                        for j in range(task_count)
                        if dl_offset + j < len(ok_list) and ok_list[dl_offset + j]
                    ]
                    dl_offset += task_count

                # ── 3단계: 텍스트 변환 + 결과 등록 ──
                for ex_data in extracted:
                    if count >= max_count or self.stop_flag:
                        break
                    raw_text = ex_data["raw_text"]
                    post_date = ex_data["post_date"]
                    image_files = ex_data.get("image_files", [])

                    if callable(_transform):
                        title, body = _transform(raw_text)
                    else:
                        lines = raw_text.splitlines()
                        title = lines[0] if lines else ""
                        body  = "\n".join(lines[1:])

                    ddg_value  = _parse_ddg(raw_text)  if callable(_parse_ddg)  else ""
                    sale_price = _compute(ddg_value, selected_cat_text) if callable(_compute) else ""
                    basic_code = _get_code(raw_text, selected_cat_text) if callable(_get_code) else ""
                    prod_code  = _gen_code(basic_code, basic_code)      if callable(_gen_code) else ""

                    item = {
                        "title":           title,
                        "body":            body,
                        "raw_description": raw_text,
                        "product_code":    prod_code,
                        "image_files":     image_files,
                        "local_image_dir": target_folder,
                        "price_input":     ddg_value,
                        "sale_price":      sale_price,
                        "created_at":      post_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "source":          "kakao",
                        "full_text":       raw_text,
                    }

                    results.append(item)
                    count += 1

                    if callable(result_callback):
                        result_callback(item)
                    if callable(progress_callback):
                        progress_callback(count)

                    self.log(
                        f"게시물 {count} 완료 | 날짜:{post_date} "
                        f"| 코드:{prod_code} | 제목:{title}"
                    )

            # 다음 페이지 스크롤
            if count < max_count and not self.stop_flag:
                try:
                    old_post_count = len(posts)
                    retries = 3
                    while retries > 0:
                        if posts:
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", posts[-1])
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(2)
                        
                        posts = self.driver.find_elements(By.CSS_SELECTOR, posts_sel)
                        if len(posts) > old_post_count:
                            break
                            
                        # 약간 위로 올렸다가 다시 끝까지 스크롤하여 로딩 트리거
                        self.driver.execute_script("window.scrollBy(0, -500);")
                        time.sleep(1)
                        if posts:
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", posts[-1])
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(2)
                        
                        posts = self.driver.find_elements(By.CSS_SELECTOR, posts_sel)
                        if len(posts) > old_post_count:
                            break
                            
                        retries -= 1

                    if len(posts) <= old_post_count:
                        self.log("더 이상 게시물이 없습니다. (최종)")
                        break
                except Exception as e:
                    self.log(f"❌ 스크롤 오류: {e}")
                    break

        self.log(f"✅ 크롤링 완료! 총 {count}개 게시물")
        return results

    def quit(self):
        """드라이버 종료."""
        if self.driver:
            try:
                self.driver.quit()
                self.log("✅ 카카오 드라이버 종료")
            except Exception as e:
                self.log(f"⚠️ 드라이버 종료 오류: {e}")
            finally:
                self.driver = None

    # ── 내부 유틸 (CrawlingThread 에서 이전) ──────────────────────────────

    def _extract_post_date(self, post_elem):
        """카카오스토리 포스트 엘리먼트에서 날짜 추출."""
        try:
            date_anchor = post_elem.find_element(
                By.CSS_SELECTOR, "a.time._linkPost"
            )
            tooltip = date_anchor.get_attribute("title") or ""

            if re.search(r"\d{4}년", tooltip):
                self.log(f"📆 툴팁(절대): {tooltip}")
                return self._parse_date_from_text(tooltip)

            try:
                span_elem = post_elem.find_element(
                    By.CSS_SELECTOR, "span.time span[data-tooltip]"
                )
                span_tooltip = span_elem.get_attribute("data-tooltip") or ""
                if re.search(r"\d{4}년", span_tooltip):
                    self.log(f"📆 span 툴팁(절대): {span_tooltip}")
                    return self._parse_date_from_text(span_tooltip)
            except NoSuchElementException:
                pass

            text = date_anchor.text.strip()
            self.log(f"⏱ anchor.text: {text}")
            return self._parse_date_from_text(text)

        except Exception as e:
            self.log(f"❌ 날짜 추출 오류: {e}")
            return None

    def _parse_date_from_text(self, text: str):
        """날짜 문자열 → datetime 파싱."""
        # 오전/오후 단독
        short = re.match(r"(오전|오후)\s*(\d{1,2}):(\d{2})", text)
        if short:
            ampm, h, m = short.groups()
            h = int(h)
            if ampm == "오후" and h < 12:
                h += 12
            elif ampm == "오전" and h == 12:
                h = 0
            today = datetime.now()
            return today.replace(hour=h, minute=int(m), second=0, microsecond=0)

        try:
            if not text or not text.strip():
                return None

            # 상대 시간 (예: "7시간 전")
            rel = re.match(r"(\d+)\s*(시간|분|초|일|주|개월|년)\s*전", text)
            if rel:
                num, unit = rel.groups()
                num = int(num)
                now = datetime.now()
                delta_map = {
                    "초": timedelta(seconds=num),
                    "분": timedelta(minutes=num),
                    "시간": timedelta(hours=num),
                    "일": timedelta(days=num),
                    "주": timedelta(weeks=num),
                    "개월": timedelta(days=num * 30),
                    "년": timedelta(days=num * 365),
                }
                return now - delta_map.get(unit, timedelta(0))

            # 절대시간 (연도 포함)
            m1 = re.match(
                r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s*(\d{1,2}):(\d{2})",
                text,
            )
            if m1:
                y, mo, d, ampm, h, mi = m1.groups()
            else:
                # 연도 없음
                m2 = re.match(
                    r"(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s*(\d{1,2}):(\d{2})",
                    text,
                )
                if not m2:
                    self.log(f"⚠️ 날짜 형식 인식 실패: {text}")
                    return None
                y = datetime.now().year
                mo, d, ampm, h, mi = m2.groups()

            h = int(h)
            if ampm == "오후" and h < 12:
                h += 12
            elif ampm == "오전" and h == 12:
                h = 0

            dt = datetime(int(y), int(mo), int(d), h, int(mi))
            self.log(f"📆 파싱 성공: {text} → {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            return dt

        except Exception as e:
            self.log(f"❌ 날짜 파싱 오류: {e}")
            return None

    def _download_images(self, post_elem, count: int, target_folder: str) -> list:
        """이미지 추출 및 다운로드."""
        image_files = []
        try:
            images = post_elem.find_elements(
                By.CSS_SELECTOR, "div.wrap_swipe img, div.cont_media img, div.media_wrap img, a._linkMedia img, a._btnZoom img"
            )
            tasks = []
            for idx, img in enumerate(images):
                src = img.get_attribute("src")
                if src:
                    ts       = datetime.now().strftime("%Y%m%d%H%M%S")
                    filename = f"{ts}_{count+1}_{idx+1}.jpg"
                    filepath = os.path.join(target_folder, filename)
                    tasks.append((src, filepath, filename))

            def _dl(args):
                src, path, _ = args
                try:
                    r = requests.get(src, timeout=5)
                    with open(path, "wb") as f:
                        f.write(r.content)
                    return True
                except Exception:
                    return False

            with concurrent.futures.ThreadPoolExecutor(max_workers=7) as ex:
                ok_list = list(ex.map(_dl, tasks))

            image_files = [tasks[i][2] for i, ok in enumerate(ok_list) if ok]
        except Exception as e:
            self.log(f"❌ 이미지 처리 오류: {e}")
        return image_files
