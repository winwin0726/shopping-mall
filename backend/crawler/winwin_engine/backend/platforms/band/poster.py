"""
band_poster.py
──────────────
TargetPoster 의 밴드(band.us) 구현체.

기존 BandPostingThread (band_posting_thread.py) 의 핵심 로직을 이 클래스로 통합.
BandPostingThread 는 내부에서 BandPoster 에 위임하여 하위호환을 유지한다.
"""

import os
import time
import random
import shutil
import tempfile
import socket

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import undetected_chromedriver as uc

from backend.browser_sensors import (
    BrowserSensorError,
    apply_quiet_chrome_options,
    clear_editable,
    get_editable_text,
    normalize_text,
    verify_text_prefix,
    wait_contenteditable_ready,
)
from platform_base import TargetPoster


class BandPoster(TargetPoster):
    """
    밴드(band.us) 포스터.

    사용법:
        poster = BandPoster()
        poster.set_log_func(self.log)
        poster.login()
        for item in items:
            poster.post(item)
        poster.quit()
    """

    # 밴드 최대 프로필 크기 (MB)
    MAX_PROFILE_MB = 50

    def __init__(
        self,
        post_list: list = None,
        final_target_folder: str = "",
        delay_min: float = 3.0,
        delay_max: float = 7.0,
        driver=None,
    ):
        """
        Args:
            post_list:            포스팅할 게시물 목록 (run() 방식 호환용)
            final_target_folder:  이미지 원본 폴더 (임시 복사 시 fallback)
            delay_min / delay_max: 게시물 간 딜레이 범위 (초)
            driver:               기존 드라이버 재사용 시
        """
        super().__init__()
        self.post_list           = post_list or []
        self.final_target_folder = final_target_folder
        self.delay_min           = delay_min
        self.delay_max           = delay_max
        self.band_driver         = driver

        self.login_confirmed = False
        self.success_count   = 0
        self.error_count     = 0

        # 콜백 (PipelineEngine 에서 진행률/상태 업데이트 시 사용)
        self.progress_callback: callable = None
        self.status_callback: callable   = None   # fn(idx, "성공"|"실패")

    # ──────────────────────────────────────────────────────────────────────
    # TargetPoster 구현
    # ──────────────────────────────────────────────────────────────────────

    def login(self, user_id: str = "", user_pw: str = "") -> bool:
        """
        밴드 드라이버 초기화 + 로그인 페이지 접근 + 자동 로그인 시도.

        기존 BandPostingThread.run() 의 0~4단계 로직 이전.
        user_id / user_pw 는 perform_auto_login() 에서 QSettings 로 읽으므로
        현재는 서명 통일 목적으로만 유지한다.
        """
        # ── 0. 프로필 디렉토리 설정 & 캐시 정리 ──────────────────────────
        profile_dir = os.path.join(os.getcwd(), "band_profile_optimized")
        self._clean_profile_cache(profile_dir)

        # ── 1. 크롬 옵션 설정 ────────────────────────────────────────────
        options = uc.ChromeOptions()
        for arg in [
            "--disable-blink-features=AutomationControlled",
            "--start-maximized", "--disable-extensions", "--disable-gpu",
            "--disable-dev-shm-usage", "--no-sandbox",
            "--disable-application-cache", "--disable-infobars",
            "--disable-notifications", "--disable-popup-blocking",
            "--js-flags=--expose-gc", "--disable-renderer-backgrounding",
            "--disable-background-networking", "--disable-sync",
            "--disable-translate", "--disable-plugins-discovery",
            "--disable-backgrounding-occluded-windows",
        ]:
            options.add_argument(arg)
        apply_quiet_chrome_options(options)
        options.add_argument(f"--user-data-dir={profile_dir}")

        # ── 2. 드라이버 실행 ─────────────────────────────────────────────
        if self.band_driver is None:
            # 쓰기 권한 테스트
            try:
                test_file = os.path.join(profile_dir, "test.txt")
                with open(test_file, "w") as f:
                    f.write("ok")
                os.remove(test_file)
                self.log("프로필 쓰기 권한 OK")
            except Exception as e:
                self.log(f"⚠️ 쓰기 권한 문제: {e}. 새 프로필 사용.")
                profile_dir = os.path.join(os.getcwd(), "band_profile_new")
                os.makedirs(profile_dir, exist_ok=True)
                options.add_argument(f"--user-data-dir={profile_dir}")

            max_retries = 3
            for i in range(max_retries):
                try:
                    self.log(f"Chrome 시작 시도 {i+1}/{max_retries}")
                    self.band_driver = uc.Chrome(options=options)
                    self.log("✅ 밴드 드라이버 실행 완료")
                    break
                except Exception as e:
                    self.log(f"드라이버 실패 ({i+1}): {e}")
                    if i == max_retries - 1:
                        if os.path.exists(profile_dir):
                            shutil.rmtree(profile_dir)
                        os.makedirs(profile_dir, exist_ok=True)
                        self.log("❌ 드라이버 초기화 최종 실패", "ERROR")
                        return False
                    time.sleep(2)

        # ── 3. 밴드 페이지 이동 ──────────────────────────────────────────
        self.log("밴드 로그인 페이지로 이동 중...")
        self._check_network()

        loaded = False
        for url in ["https://band.us/home", "https://band.us", "https://band.us/feed"]:
            try:
                self.band_driver.set_page_load_timeout(30)
                self.band_driver.get(url)
                WebDriverWait(self.band_driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                if "band.us" in self.band_driver.current_url:
                    loaded = True
                    break
            except Exception as e:
                self.log(f"{url} 접근 실패: {e}")

        if not loaded:
            self.log("❌ 밴드 페이지 접근 실패", "ERROR")
            return False

        # ── 4. 자동 로그인 시도 ──────────────────────────────────────────
        self.log("자동 로그인 시도 중...")
        login_ok = self._perform_auto_login()

        if not login_ok:
            # 이미 로그인된 경우 확인
            try:
                WebDriverWait(self.band_driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".uHeaderProfile")
                    )
                )
                self.log("✅ 이미 로그인 상태")
                self.login_confirmed = True
            except Exception:
                self.log("수동 로그인 필요 (로그인 후 진행하세요)", "WARNING")
                # PipelineEngine 이 login_confirmed 를 폴링할 수 있음
                return False

        # 팝업 처리
        self._handle_post_login_popups()
        return True

    def post(self, item: dict) -> bool:
        """
        밴드에 게시물 1건 포스팅.

        기존 BandPostingThread.run() 의 6단계(글쓰기 루프 내부) 이전.

        Args:
            item: 공통 게시물 스키마 dict

        Returns:
            True → 성공, False → 실패
        """
        if self.band_driver is None:
            self.log("❌ 드라이버가 없습니다. login()을 먼저 호출하세요.", "ERROR")
            return False

        title = item.get("title", "")
        self.log(f"글쓰기 시작: {title}")

        # 6-0 팝업 닫기
        self._dismiss_popups()

        # 6-1 글쓰기 버튼 클릭
        delay = random.uniform(
            min(self.delay_min, self.delay_max),
            max(self.delay_min, self.delay_max),
        )
        self.log(f"⏱ {delay:.1f}초 후 글쓰기")
        time.sleep(delay)

        try:
            write_btn = None
            # 여러 셀렉터를 순차적으로 시도 (밴드 UI 변경에 대응)
            selectors = [
                (By.CSS_SELECTOR, "button.uButton.-sizeL.-confirm.sf_bg._btnPostWrite"),
                (By.CSS_SELECTOR, "button._btnPostWrite"),
                (By.CSS_SELECTOR, "button.uButton._btnPostWrite"),
                (By.CSS_SELECTOR, "button.-confirm.sf_bg"),
                (By.XPATH, "//button[contains(text(),'글쓰기')]"),
                (By.XPATH, "//button[contains(@class,'uWriteBtn')]"),
                (By.XPATH, "//button[contains(@class,'_btnPostWrite')]"),
                (By.CSS_SELECTOR, "button[data-uiselector='btnPostWrite']"),
                (By.CSS_SELECTOR, ".uButtonWrite button, .writeBtn button"),
                (By.XPATH, "//a[contains(@class,'uWriteBtn')]"),
                (By.XPATH, "//span[contains(text(),'글쓰기')]/ancestor::button"),
            ]
            for by, sel in selectors:
                try:
                    write_btn = WebDriverWait(self.band_driver, 10).until(
                        EC.element_to_be_clickable((by, sel))
                    )
                    self.log(f"✅ 글쓰기 버튼 발견: {sel[:40]}")
                    break
                except Exception:
                    continue

            if not write_btn:
                raise Exception("글쓰기 버튼을 찾지 못했습니다. 밴드 그룹 내에 있는지 확인하세요.")

            self.band_driver.execute_script("arguments[0].scrollIntoView();", write_btn)
            self.band_driver.execute_script("arguments[0].click();", write_btn)
        except Exception as e:
            self.log(f"글쓰기 버튼 오류: {e}")
            return False

        # 6-2 본문 입력
        try:
            editor = self._wait_write_editor_ready(timeout=25)

            raw = item.get("raw_description", "").strip()
            clean = self._filter_bmp(raw)
            if not clean:
                clean = self._filter_bmp(title)

            def _insert_body_text():
                for line in clean.split("\n"):
                    self.band_driver.execute_script(
                        "arguments[0].focus();"
                        "document.execCommand('insertText',false,arguments[1]);"
                        "document.execCommand('insertParagraph');",
                        editor, line,
                    )
                    time.sleep(0.06)

            _insert_body_text()

            if not self._verify_editor_prefix(editor, clean, timeout=5):
                self.log("⚠️ 본문 앞부분 입력 누락 감지 → 에디터 안정화 후 1회 재입력")
                editor = self._wait_write_editor_ready(timeout=12)
                self._clear_editor(editor)
                time.sleep(0.4)
                _insert_body_text()
                if not self._verify_editor_prefix(editor, clean, timeout=5):
                    raise Exception("본문 입력 검증 실패: 앞부분이 에디터에 반영되지 않았습니다.")

            for _ in range(3):
                ActionChains(self.band_driver).send_keys(Keys.ENTER).perform()
                time.sleep(0.1)

        except Exception as e:
            self.log(f"본문 입력 오류: {e}")

        # 6-3 이미지 첨부
        image_files = item.get("image_files", [])
        local_image_dir = item.get("local_image_dir", "")
        if image_files:
            self._attach_images_from_list(image_files, local_image_dir)

        # 6-4 게시 버튼 클릭
        time.sleep(3)
        upload_success = False
        try:
            post_btn = WebDriverWait(self.band_driver, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), '게시')]")
                )
            )
            self.band_driver.execute_script("arguments[0].click();", post_btn)
            self.log("게시 버튼 클릭 완료. 네트워크 업로드(최대 60초) 대기 중...")

            try:
                # 업로드가 완료되면 에디터 창이 완전히 사라지므로 이를 통해 업로드 완료를 감지 (센서)
                WebDriverWait(self.band_driver, 60).until_not(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        "div.contentEditor._richEditor[contenteditable='true']",
                    ))
                )
                self.log(f"✅ 게시 완료: {title}")
                upload_success = True
            except Exception:
                self.log("게시 완료 확인 시간 초과")

        except Exception as e:
            self.log(f"게시 버튼 오류: {e}")

        if upload_success:
            self.success_count += 1
        else:
            self.error_count += 1

        return upload_success

    def _wait_write_editor_ready(self, timeout: float = 25):
        try:
            return wait_contenteditable_ready(
                self.band_driver,
                selectors=[
                    "div[contenteditable='true']",
                    "div.contentEditor",
                    "div._richEditor",
                    "div.uEditorArea",
                    "[contenteditable='true']",
                ],
                timeout=timeout,
                min_width=120,
                min_height=40,
                stable_polls=2,
                frame_selectors="iframe[class*='editor'],iframe[title*='editor'],iframe,frame",
                log=lambda msg: self.log(f"✅ 글쓰기 창 에디터 준비 완료 ({msg})"),
                label="Band write editor",
            )
        except BrowserSensorError as e:
            raise Exception(f"에디터 준비 대기 실패: {e}")

        """글쓰기 창과 에디터가 완전히 열린 뒤 입력 가능한 상태가 될 때까지 기다린다."""
        end_at = time.time() + timeout
        editor_selectors = [
            "div[contenteditable='true']",
            "div.contentEditor",
            "div._richEditor",
            "div.uEditorArea",
            "[contenteditable='true']",
        ]
        frame_selectors = "iframe[class*='editor'],iframe[title*='에디터'],iframe,frame"
        last_rect = None
        stable_hits = 0
        last_error = None

        while time.time() < end_at:
            try:
                self.band_driver.switch_to.default_content()
            except Exception as e:
                last_error = e

            contexts = [None]
            try:
                contexts.extend(self.band_driver.find_elements(By.CSS_SELECTOR, frame_selectors))
            except Exception:
                pass

            for frame in contexts:
                try:
                    self.band_driver.switch_to.default_content()
                    if frame is not None:
                        self.band_driver.switch_to.frame(frame)
                except Exception as e:
                    last_error = e
                    continue

                for selector in editor_selectors:
                    try:
                        candidates = self.band_driver.find_elements(By.CSS_SELECTOR, selector)
                    except Exception as e:
                        last_error = e
                        continue

                    for editor in candidates:
                        try:
                            ready = self.band_driver.execute_script("""
                                const el = arguments[0];
                                const rect = el.getBoundingClientRect();
                                const style = window.getComputedStyle(el);
                                const disabled = el.getAttribute('aria-disabled') === 'true'
                                    || el.getAttribute('contenteditable') === 'false';
                                const visible = style.display !== 'none'
                                    && style.visibility !== 'hidden'
                                    && rect.width >= 120
                                    && rect.height >= 40
                                    && rect.bottom > 0
                                    && rect.right > 0;
                                return {
                                    ok: visible && !disabled,
                                    rect: [Math.round(rect.left), Math.round(rect.top), Math.round(rect.width), Math.round(rect.height)]
                                };
                            """, editor) or {}
                            if not ready.get("ok"):
                                continue

                            rect = tuple(ready.get("rect") or [])
                            if rect == last_rect:
                                stable_hits += 1
                            else:
                                stable_hits = 0
                                last_rect = rect

                            try:
                                ActionChains(self.band_driver).move_to_element(editor).click().perform()
                            except Exception:
                                self.band_driver.execute_script("arguments[0].focus();", editor)

                            focused = self.band_driver.execute_script("""
                                const el = arguments[0];
                                const active = document.activeElement;
                                return active === el || el.contains(active);
                            """, editor)
                            if focused and stable_hits >= 2:
                                self.log("✅ 글쓰기 창/에디터 준비 완료")
                                time.sleep(0.35)
                                return editor
                        except Exception as e:
                            last_error = e
                            continue

            time.sleep(0.25)

        if last_error:
            raise Exception(f"에디터 준비 대기 실패: {str(last_error)[:120]}")
        raise Exception("에디터 준비 대기 실패: 입력 가능한 글쓰기 창을 찾지 못했습니다.")

    def _get_editor_text(self, editor) -> str:
        return get_editable_text(self.band_driver, editor)

        try:
            return self.band_driver.execute_script("""
                const el = arguments[0];
                return (el.innerText || el.textContent || '').trim();
            """, editor) or ""
        except Exception:
            return ""

    @staticmethod
    def _normalize_editor_text(text: str) -> str:
        return normalize_text(text)

        return " ".join((text or "").replace("\u200b", "").split())

    def _verify_editor_prefix(self, editor, expected_text: str, timeout: float = 5) -> bool:
        return verify_text_prefix(
            self.band_driver,
            editor,
            expected_text,
            timeout=timeout,
            prefix_len=24,
            log=self.log,
        )

        expected = self._normalize_editor_text(expected_text)
        if not expected:
            return True
        prefix = expected[: min(24, len(expected))]
        end_at = time.time() + timeout
        while time.time() < end_at:
            actual = self._normalize_editor_text(self._get_editor_text(editor))
            if actual.startswith(prefix) or prefix in actual[: max(80, len(prefix) + 10)]:
                return True
            time.sleep(0.25)
        actual = self._normalize_editor_text(self._get_editor_text(editor))
        self.log(f"⚠️ 본문 검증 실패: 기대 시작='{prefix[:20]}', 실제 시작='{actual[:20]}'")
        return False

    def _clear_editor(self, editor):
        clear_editable(self.band_driver, editor)
        return

        try:
            self.band_driver.execute_script("""
                arguments[0].focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('delete', false, null);
            """, editor)
        except Exception:
            try:
                ActionChains(self.band_driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
            except Exception:
                pass

    def quit(self):
        """드라이버 종료."""
        if self.band_driver:
            try:
                self.band_driver.quit()
                self.log("✅ 밴드 드라이버 종료")
            except Exception as e:
                self.log(f"⚠️ 드라이버 종료 오류: {e}")
            finally:
                self.band_driver = None

    # ──────────────────────────────────────────────────────────────────────
    # 내부 유틸 (기존 BandPostingThread 메서드 이전)
    # ──────────────────────────────────────────────────────────────────────

    def _clean_profile_cache(self, profile_dir: str):
        """프로필 크기 과다 시 캐시만 정리."""
        if not os.path.exists(profile_dir):
            os.makedirs(profile_dir, exist_ok=True)
            self.log(f"프로필 디렉토리 생성: {profile_dir}")
            return

        size_mb = self._get_dir_size(profile_dir) / (1024 * 1024)
        self.log(f"프로필 크기: {size_mb:.2f} MB")

        if size_mb > self.MAX_PROFILE_MB:
            self.log(f"프로필 과대({size_mb:.2f}MB) → 캐시 정리")
            for cache_path in [
                os.path.join(profile_dir, "Default", "Cache"),
                os.path.join(profile_dir, "Default", "Media Cache"),
                os.path.join(profile_dir, "Service Worker"),
            ]:
                if os.path.exists(cache_path):
                    try:
                        shutil.rmtree(cache_path)
                        self.log(f"🗑️ 캐시 삭제: {cache_path}")
                    except Exception as e:
                        self.log(f"캐시 삭제 실패: {e}")

    def _get_dir_size(self, path: str) -> int:
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except (FileNotFoundError, PermissionError):
                    pass
        return total

    def _check_network(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=5)
            self.log("네트워크 연결 확인 완료")
        except Exception as e:
            self.log(f"네트워크 연결 오류: {e}", "WARNING")

    def _perform_auto_login(self) -> bool:
        """
        밴드 자동 로그인.
        기존 BandPostingThread.perform_auto_login() 이전.
        """
        try:
            self.log("밴드 자동 로그인 시작...")

            # 로그인 버튼
            try:
                btn = WebDriverWait(self.band_driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, "a.login._loginLink")
                    )
                )
                self.band_driver.execute_script("arguments[0].click();", btn)
                time.sleep(random.uniform(2, 3))
            except Exception as e:
                self.log(f"로그인 버튼 클릭 오류: {e}")

            # 이메일로 로그인 버튼
            try:
                email_btn = WebDriverWait(self.band_driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a#email_login_a"))
                )
                self.band_driver.execute_script("arguments[0].click();", email_btn)
                time.sleep(random.uniform(2, 3))
            except Exception as e:
                self.log(f"이메일 로그인 버튼 오류: {e}")

            # 최적 계정 선택
            account = self._select_best_account()
            if not account:
                self.log("사용 가능한 계정 없음 (일일 한도 초과)")
                return False

            # 이메일 입력
            email_input = None
            for sel in [
                "input#input_email", "input[type='email']",
                "input[name='email']", "input[placeholder='이메일']",
            ]:
                try:
                    email_input = WebDriverWait(self.band_driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    break
                except Exception:
                    pass

            if not email_input:
                self.log("이메일 입력 필드 미발견")
                return False

            email_input.clear()
            email_input.send_keys(account.get("id", ""))
            time.sleep(random.uniform(1, 2))

            # 비밀번호 입력
            pw_input = None
            for sel in [
                "input#input_password", "input[type='password']",
                "input[name='password']",
            ]:
                try:
                    pw_input = WebDriverWait(self.band_driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    break
                except Exception:
                    pass

            if not pw_input:
                self.log("비밀번호 입력 필드 미발견")
                return False

            pw_input.clear()
            pw_input.send_keys(account.get("pw", ""))
            time.sleep(random.uniform(1, 2))

            # 로그인 버튼 클릭
            for sel in [
                "button[type='submit']", "button.uButton.-confirm",
                "button.submit", "input[type='submit']",
            ]:
                try:
                    submit = WebDriverWait(self.band_driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                    self.band_driver.execute_script("arguments[0].click();", submit)
                    self.log(f"로그인 버튼 클릭: {sel}")
                    break
                except Exception:
                    pass

            time.sleep(3)

            # 로그인 성공 확인
            try:
                WebDriverWait(self.band_driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".uHeaderProfile")
                    )
                )
                self.log("✅ 자동 로그인 성공")
                self.login_confirmed = True
                return True
            except Exception:
                self.log("자동 로그인 확인 실패")
                return False

        except Exception as e:
            self.log(f"자동 로그인 오류: {e}")
            return False

    def _select_best_account(self) -> dict:
        """
        QSettings 에서 밴드 계정 목록 로드 후 사용 가능한 계정 반환.
        기존 load_band_profiles() + select_best_account() 통합.
        """
        try:
            from PyQt5.QtCore import QSettings
            settings = QSettings("WinWin", "KakaoCrawler")
            profiles = settings.value("band/profiles", {})

            if not isinstance(profiles, dict):
                return {}

            accounts = []
            for name, data in profiles.items():
                if isinstance(data, dict):
                    accounts.append({
                        "name": name,
                        "id":   data.get("id", ""),
                        "pw":   data.get("pw", ""),
                    })

            return accounts[0] if accounts else {}
        except Exception as e:
            self.log(f"계정 로드 오류: {e}")
            return {}

    def _handle_post_login_popups(self):
        """로그인 후 팝업 처리."""
        try:
            self.log("로그인 후 팝업 확인 중...")

            try:
                alert = self.band_driver.switch_to.alert
                self.log(f"알림창: {alert.text}")
                alert.accept()
                time.sleep(1)
            except Exception:
                pass

            for _ in range(3):
                close_btns = []
                for sel in [
                    "button.uButton._btnClose", "button.close",
                    "a.close", "button._cancel",
                ]:
                    try:
                        for btn in self.band_driver.find_elements(By.CSS_SELECTOR, sel):
                            if btn.is_displayed():
                                close_btns.append(btn)
                    except Exception:
                        pass

                if close_btns:
                    for btn in close_btns:
                        try:
                            self.band_driver.execute_script("arguments[0].click();", btn)
                            time.sleep(1)
                        except Exception:
                            pass
                else:
                    break

            try:
                ActionChains(self.band_driver).send_keys(Keys.ESCAPE).perform()
                time.sleep(0.5)
            except Exception:
                pass

            self.log("팝업 처리 완료")

        except Exception as e:
            self.log(f"팝업 처리 오류: {e}")

    def _dismiss_popups(self):
        """게시물 올리기 전 팝업 닫기."""
        try:
            for sel in [
                "button.uButton._btnClose", "button.close",
                "a.close", "button._cancel",
            ]:
                for btn in self.band_driver.find_elements(By.CSS_SELECTOR, sel):
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(0.2)
            ActionChains(self.band_driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.5)
        except Exception:
            pass

    def _attach_images_from_list(self, image_files: list, local_image_dir: str = ""):
        """
        이미지 파일 경로 목록을 밴드 에디터에 첨부.
        기존 BandPostingThread 의 이미지 첨부 로직 이전.
        """
        time.sleep(random.uniform(3, 5))

        # 유효한 이미지 경로만 필터링
        valid_paths = []
        for img_path in image_files:
            # image_files 는 파일명만 있을 수도 있어 폴더 기반 탐색
            candidates = [
                img_path,
                os.path.join(local_image_dir, img_path) if local_image_dir else None,
                os.path.join(self.final_target_folder, img_path)
                if self.final_target_folder else None,
            ]
            for c in candidates:
                if c and os.path.exists(c) and os.path.getsize(c) > 1024:
                    valid_paths.append(os.path.abspath(c))
                    break

        # 네이버 밴드 업로드 제한(100장) 준수를 위해 슬라이싱 적용
        valid_paths = valid_paths[:100]

        if not valid_paths:
            self.log("⚠️ 첨부할 유효 이미지 없음")
            return

        image_count = len(valid_paths)
        self.log(f"이미지 첨부 시작: {image_count}개")

        # file input 탐색
        photo_input = None
        for sel in [
            "input[type='file'][accept='image/*']",
            "input[type='file']",
            "input.uFile",
            ".uploadInput input",
        ]:
            try:
                photo_input = WebDriverWait(self.band_driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                break
            except Exception:
                pass

        if not photo_input:
            try:
                img_btn = WebDriverWait(self.band_driver, 3).until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        ".uButton._btnAttachPhoto, button.attachPhoto",
                    ))
                )
                self.band_driver.execute_script("arguments[0].click();", img_btn)
                photo_input = WebDriverWait(self.band_driver, 3).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "input[type='file']")
                    )
                )
            except Exception as e:
                self.log(f"이미지 첨부 버튼 실패: {e}")
                return

        if not photo_input:
            self.log("❌ file input 미발견")
            return

        # input 표시 & 경로 전달
        self.band_driver.execute_script(
            "var i=arguments[0]; i.style.display='block';"
            "i.style.visibility='visible'; i.style.opacity='1';",
            photo_input,
        )
        photo_input.send_keys("\n".join(valid_paths))
        self.log("이미지 경로 입력 완료")

        # 입력 즉시 반응할 시간을 부여
        time.sleep(2)

        # 이미지 로드 썸네일 대기 (최대 45초 - 센서)
        start = time.time()
        while time.time() - start < 45:
            try:
                thumbs = self.band_driver.find_elements(By.CSS_SELECTOR, "img._thumbImg")
                attach_btns = self.band_driver.find_elements(
                    By.XPATH, "//button[contains(text(), '첨부')]"
                )
                if len(thumbs) >= image_count and attach_btns and attach_btns[0].is_enabled():
                    self.log(f"✅ 썸네일 {image_count}개 로드 완료 ({(time.time()-start):.1f}초)")
                    break
            except Exception:
                pass
            time.sleep(1)

        # 로드가 끝나고 약간 안정화될 때까지 대기
        time.sleep(5)

        # 첨부 모달에서 '첨부' 버튼 클릭하여 에디터로 사진 보내기
        for sel in [
            "//button[contains(text(), '첨부')]",
            "//button[contains(@class, 'submit')]",
            "//button[contains(@class, 'uButton') and contains(@class, '-confirm')]",
        ]:
            try:
                attach_btn = WebDriverWait(self.band_driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                self.band_driver.execute_script("arguments[0].click();", attach_btn)
                self.log("창 내 '첨부' 버튼 클릭 성공, 본문 전송 중...")
                time.sleep(4)  # 에디터 본문에 사진 뿌려지는 시간 대기
                break
            except Exception:
                pass

    @staticmethod
    def _filter_bmp(text: str) -> str:
        """유니코드 BMP 외 문자 제거."""
        if not text:
            return ""
        return "".join(c for c in text if ord(c) < 0x10000)
