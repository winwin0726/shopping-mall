import sys
import os
import time
import random
import json
import shutil
import logging
import requests
import re
import traceback
from datetime import datetime, timedelta
import concurrent.futures

from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition, QObject
from PyQt5.QtWidgets import QApplication
import undetected_chromedriver as uc
from core.driver_manager import create_uc_driver
from PyQt5.QtGui import QColor, QFont
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

# 루트 경로 참조
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class BandPostingThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    status_update_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal()
    login_required_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    profile_restore_signal = pyqtSignal()
    
    # 상세 진행 상황 업데이트를 위한 시그널 추가
    detailed_progress_signal = pyqtSignal(int, bool, int, str)
    set_mode_signal = pyqtSignal(str)  # 모드 설정 시그널
    reset_progress_signal = pyqtSignal()  # 진행 상황 초기화 시그널 추가
    
    def __init__(self, post_list, crawled_products, final_target_folder, delay_min, delay_max, band_id=None, band_pw=None):
        super().__init__()
        self.post_list = post_list
        self.crawled_products = crawled_products
        self.final_target_folder = final_target_folder
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.band_id = band_id
        self.band_pw = band_pw
        
        self.is_running = True
        self.driver = None
        self.login_confirmed = False
        self.paused = False
        self.login_wait_timeout = 300
        
        # 설정값 로드
        self.settings = QSettings("WINWIN", "AutoCrawler")
        self.stop_flag = False
        self.band_driver = None
        self.success_count = 0  # 성공 카운터 추가
        self.error_count = 0    # 실패 카운터 추가      

    def click_attach_button(self):
        try:
            attach_btn = WebDriverWait(self.band_driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '첨부')]"))
            )
            self.band_driver.execute_script("arguments[0].click();", attach_btn)
            self.log_signal.emit("첨부 버튼 클릭 성공 (3초 후)")
        except Exception as e:
            self.log_signal.emit(f"첨부 버튼 클릭 실패 (3초 후): {e}")       

    def confirm_login(self):
        self.login_confirmed = True
    
    def run(self):
        # 0. 크롬 프로필 디렉토리 전역 선언 (오류 방지용)
        profile_dir = os.path.join(os.getcwd(), "band_profile_optimized")
        
        # ─── 0. 프로필 크기/캐시 정리 ─────────────────────────────
        MAX_PROFILE_MB = 50
        def get_dir_size_mb(path):
            total = 0
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total += os.path.getsize(fp)
                    except:
                        pass
            return total / (1024*1024)

        if os.path.exists(profile_dir):
            size_mb = get_dir_size_mb(profile_dir)
            self.log_signal.emit(f"⚠️ 프로필 크기: {size_mb:.2f} MB")
            if size_mb > MAX_PROFILE_MB:
                self.log_signal.emit(f"⚠️ 프로필 크기 과다({size_mb:.2f}MB) → 캐시만 정리")
                for cp in [
                    os.path.join(profile_dir, "Default", "Cache"),
                    os.path.join(profile_dir, "Default", "Media Cache"),
                    os.path.join(profile_dir, "Service Worker")
                ]:
                    if os.path.exists(cp):
                        try:
                            shutil.rmtree(cp)
                            self.log_signal.emit(f"🗑️ 캐시 폴더 삭제: {cp}")
                        except:
                            pass
        else:
            os.makedirs(profile_dir, exist_ok=True)
            self.log_signal.emit(f"프로필 디렉토리 생성: {profile_dir}")

        try:
            # ─── options 선언 ────────────────────────────────────────
            options = uc.ChromeOptions()

            # ─── 1. 크롬 옵션 설정 ────────────────────────────────────
            cache_args = [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized", "--disable-extensions", "--disable-gpu",
                "--disable-dev-shm-usage", "--no-sandbox", "--disable-application-cache",
                "--disable-infobars", "--disable-notifications", "--disable-popup-blocking",
                "--js-flags=--expose-gc", "--disable-renderer-backgrounding",
                "--disable-background-networking", "--disable-sync",
                "--disable-translate", "--disable-plugins-discovery",
                "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"
            ]
            for arg in cache_args:
                options.add_argument(arg)
            options.add_argument(f"--user-data-dir={profile_dir}")

        except Exception as e:
            # options 설정 중 오류 발생 시 로깅 및 프로필 초기화
            self.log_signal.emit(f"⚠️ 크롬 옵션 설정 오류: {e}")
            shutil.rmtree(profile_dir, ignore_errors=True)
            os.makedirs(profile_dir, exist_ok=True)
            # 재생성한 profile_dir로 다시 옵션 설정
            options = uc.ChromeOptions()
            for arg in cache_args:
                options.add_argument(arg)
            options.add_argument(f"--user-data-dir={profile_dir}")

        # 진행 상황 초기화
        self.reset_progress_signal.emit()
        self.set_mode_signal.emit("band_posting")
        total_posts = len(self.crawled_products)
        self.detailed_progress_signal.emit(0, True, 0, "밴드 자동글쓰기 준비 중...")

        # 2. 크롬 드라이버 실행
        try:
            options = uc.ChromeOptions()
            for arg in [
                "--disable-blink-features=AutomationControlled",
                "--start-maximized", "--disable-extensions", "--disable-gpu",
                "--disable-dev-shm-usage", "--no-sandbox", "--disable-application-cache",
                "--disable-infobars", "--disable-notifications", "--disable-popup-blocking",
                "--js-flags=--expose-gc", "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows"
            ]:
                options.add_argument(arg)
            self.log_signal.emit(f"프로필 디렉토리 확인: {profile_dir}")
            if os.path.exists(profile_dir):
                size_mb = self.get_dir_size(profile_dir)/(1024*1024)
                self.log_signal.emit(f"프로필 크기: {size_mb:.2f} MB")
                if size_mb>500:
                    self.log_signal.emit(f"⚠️ 프로필 크기가 큽니다 ({size_mb:.2f} MB)")
            else:
                os.makedirs(profile_dir, exist_ok=True)
                self.log_signal.emit(f"프로필 디렉토리 생성: {profile_dir}")
            # 쓰기 권한 테스트
            try:
                test = os.path.join(profile_dir,"test.txt")
                with open(test,"w") as f: f.write("ok")
                os.remove(test)
                self.log_signal.emit("프로필 쓰기 권한 OK")
            except Exception as e:
                self.log_signal.emit(f"⚠️ 권한 문제: {e}")
                profile_dir = os.path.join(os.getcwd(),"band_profile_new")
                os.makedirs(profile_dir, exist_ok=True)
                self.log_signal.emit(f"새 프로필 생성: {profile_dir}")
            options.add_argument(f"--user-data-dir={profile_dir}")

            # 드라이버 시작 재시도
            max_retries=3
            for i in range(max_retries):
                try:
                    self.log_signal.emit(f"Chrome 시작 시도 {i+1}/{max_retries}")
                    # 공용 드라이버 매니저 호출 (Windows 환경 안정성을 위해 use_subprocess=True 유지)
                    self.band_driver = create_uc_driver(options, use_subprocess=True, log_func=self.log_signal.emit)
                    self.log_signal.emit("밴드 드라이버 실행 완료")
                    break
                except Exception as e:
                    self.log_signal.emit(f"드라이버 실패 ({i+1}): {e}")
                    if i==max_retries-1:
                        if os.path.exists(profile_dir):
                            shutil.rmtree(profile_dir)
                        os.makedirs(profile_dir, exist_ok=True)
                        self.log_signal.emit("프로필 초기화 후 재시도 필요")
                        raise
                    time.sleep(2)
            self.detailed_progress_signal.emit(0, True, 0, "드라이버 초기화 완료")
        except Exception as e:
            self.log_signal.emit(f"드라이버 실행 오류: {e}")
            self.error_signal.emit(f"브라우저 오류: {e}")
            self.profile_restore_signal.emit()
            return

        # 3. 밴드 로그인 페이지 이동
        self.log_signal.emit("밴드 로그인 페이지 이동 중...")
        try: self.check_network_connection()
        except Exception as e: self.log_signal.emit(f"네트워크 확인 실패: {e}")
        band_urls = ["https://band.us/home","https://band.us","https://band.us/feed"]
        loaded=False
        for url in band_urls:
            try:
                self.log_signal.emit(f"URL 시도: {url}")
                self.band_driver.set_page_load_timeout(30)
                self.band_driver.get(url)
                WebDriverWait(self.band_driver,10).until(
                    lambda d:d.execute_script("return document.readyState")=="complete"
                )
                cur = self.band_driver.current_url
                self.log_signal.emit(f"현재: {cur}")
                if "band.us" in cur:
                    loaded=True
                    break
            except Exception as e:
                self.log_signal.emit(f"{url} 실패: {e}")
        if not loaded:
            self.log_signal.emit("밴드 페이지 접근 실패")
            if self.band_driver: self.band_driver.quit()
            self.finished_signal.emit("페이지 접근에 실패했습니다.")
            return

        # 4. 로그인 확인
        try:
            WebDriverWait(self.band_driver,5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,".uHeaderProfile"))
            )
            self.log_signal.emit("이미 로그인됨")
            self.login_confirmed=True
        except:
            self.log_signal.emit("로그인 필요 - 로그인 후 글올릴 그룹으로 이동")
            self.login_required_signal.emit()
            while not self.login_confirmed and not self.stop_flag:
                time.sleep(1)
            if self.stop_flag:
                self.log_signal.emit("사용자 취소")
                if self.band_driver: self.band_driver.quit()
                return

        # 5. 임시 폴더 생성
        temp_folder = self.create_temp_folders_for_posts()
        self.log_signal.emit(f"임시 폴더: {temp_folder}")

        # 6. 게시물 업로드 루프
        self.success_count=0
        self.error_count=0
        self.progress_signal.emit(0)
        self.detailed_progress_signal.emit(0, True, 0,f"시작 (총 {total_posts}개)")
        for current_idx, product in enumerate(self.post_list, start=1):
            if self.stop_flag:
                self.log_signal.emit("중지됨")
                break
            self.progress_signal.emit(current_idx)
            upload_success=False

            self.log_signal.emit(f"[{current_idx}/{total_posts}] 글쓰기 시작: {product.get('title','')}")
            self.detailed_progress_signal.emit(
                current_idx-1, True, len(product.get("image_files",[])),
                f"[{current_idx}/{total_posts}] 쓰기 중"
            )

            # 6-0 팝업 닫기
            try:
                for sel in ["button.uButton._btnClose","button.close","a.close","button._cancel"]:
                    for btn in self.band_driver.find_elements(By.CSS_SELECTOR,sel):
                        if btn.is_displayed():
                            btn.click()
                            time.sleep(0.2)
                ActionChains(self.band_driver).send_keys(Keys.ESCAPE).perform()
                time.sleep(0.5)
            except: pass

            # 6-1 글쓰기 버튼 클릭
            sec_min, sec_max = sorted([self.delay_min, self.delay_max])
            delay = random.uniform(sec_min, sec_max)
            self.log_signal.emit(f"⏱ {delay:.1f}초 후 글쓰기 클릭")
            time.sleep(delay)
            try:
                write_btn = WebDriverWait(self.band_driver,5).until(
                    EC.element_to_be_clickable((By.XPATH,"//button[contains(text(),'글쓰기')]"))
                )
                self.band_driver.execute_script("arguments[0].scrollIntoView();",write_btn)
                self.band_driver.execute_script("arguments[0].click();",write_btn)
            except Exception as e:
                self.log_signal.emit(f"글쓰기 버튼 오류: {e}")
                continue

            # 6-2 본문 입력
            try:
                self.band_driver.switch_to.default_content()
                try:
                    frm = WebDriverWait(self.band_driver,3).until(
                        EC.presence_of_element_located((
                            By.CSS_SELECTOR,
                            "iframe[class*='editor'],iframe[title='에디터 영역']"
                        ))
                    )
                    self.band_driver.switch_to.frame(frm)
                    self.log_signal.emit("✅ 에디터 iframe 전환")
                except:
                    self.log_signal.emit("❗ iframe 없음")

                editor=None
                for sel in ["div[contenteditable='true']","div.contentEditor",
                            "div._richEditor","div.uEditorArea"]:
                    try:
                        editor = WebDriverWait(self.band_driver,2).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR,sel))
                        )
                        self.log_signal.emit(f"본문 에디터 발견: {sel}")
                        break
                    except: pass
                if not editor:
                    raise Exception("에디터 미발견")

                # --- 6-2.5 이전 작성 중이던 임시 데이터(글, 사진) 초기화 ---
                try:
                    # 1. 에디터 텍스트 초기화
                    self.band_driver.execute_script("arguments[0].innerHTML = '';", editor)
                    
                    # 2. 첨부된 이미지/파일 삭제 버튼 클릭
                    remove_selectors = [
                        "button.btnDelete", "button.removeBtn", 
                        "button._btnRemove", "button.btnDel", 
                        "button.uButton.-sizeS.-bgLight"
                    ]
                    for rm_sel in remove_selectors:
                        rm_btns = self.band_driver.find_elements(By.CSS_SELECTOR, rm_sel)
                        for btn in rm_btns:
                            if btn.is_displayed():
                                self.band_driver.execute_script("arguments[0].click();", btn)
                                time.sleep(0.2)
                except Exception as e:
                    self.log_signal.emit(f"에디터 초기화 중 예외: {e}")

                ActionChains(self.band_driver).move_to_element(editor).click().perform()
                time.sleep(0.3)
                raw = product.get("raw_description","").strip()
                clean = self.filter_bmp(raw)
                for line in clean.split("\n"):
                    self.band_driver.execute_script(
                        "arguments[0].focus();" +
                        "document.execCommand('insertText',false,arguments[1]);" +
                        "document.execCommand('insertParagraph');",
                        editor, line
                    )
                    time.sleep(0.05)
                for _ in range(3):
                    ActionChains(self.band_driver).send_keys(Keys.ENTER).perform()
                    time.sleep(0.1)
            except Exception as e:
                self.log_signal.emit(f"본문 입력 오류: {e}")

            # 6-3. 이미지 첨부
            time.sleep(random.uniform(3, 5))  # 사진 붙여넣기 후 대기
            try:
                # 크롤링된 전체 리스트(self.crawled_products) 기준의 인덱스를 사용하여 올바른 이미지 폴더 경로 생성
                folder_index = product.get("_original_index", current_idx - 1) + 1
                
                # 각 상품에 저장된 진짜 원본 사진 폴더 경로를 최우선으로 찾습니다.
                # 크롤러가 새로 생성한 고유 폴더(band_post_1 등) 형식을 그대로 따라가게 합니다.
                local_dir = product.get("local_image_dir")
                if local_dir and os.path.exists(local_dir):
                    folder_path = local_dir
                else:
                    # fallback: 기존 번호 방식
                    folder_path = os.path.join(temp_folder, str(folder_index))
                image_files = [f for f in os.listdir(folder_path) if f.endswith('.jpg')]

                if image_files:
                    # 이미지 파일 디버깅
                    valid_image_paths = self.debug_image_attachment(folder_path, image_files)

                    if valid_image_paths:
                        image_count = len(valid_image_paths)
                        self.log_signal.emit(f"찾은 이미지 파일: {image_count}개")

                        # 파일 입력 요소 찾기
                        photo_input = None
                        selectors = [
                            "input[type='file'][accept='image/*']",
                            "input[type='file']",
                            "input.uFile",
                            ".uploadInput input"
                        ]
                        for selector in selectors:
                            try:
                                photo_input = WebDriverWait(self.band_driver, 3).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                                )
                                self.log_signal.emit(f"이미지 입력 요소 찾음: {selector}")
                                break
                            except:
                                continue

                        if not photo_input:
                            # 이미지 첨부 버튼 클릭 후 input 재탐색
                            try:
                                img_btn = WebDriverWait(self.band_driver, 3).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".uButton._btnAttachPhoto, button.attachPhoto"))
                                )
                                self.band_driver.execute_script("arguments[0].click();", img_btn)
                                self.log_signal.emit("이미지 첨부 버튼 클릭 성공")
                                photo_input = WebDriverWait(self.band_driver, 3).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                                )
                            except Exception as e:
                                self.log_signal.emit(f"이미지 첨부 버튼 클릭 실패: {e}")

                        if photo_input:
                            # 경로 변환 및 업로드
                            abs_paths = [os.path.abspath(p) for p in valid_image_paths]
                            paths_str = "\n".join(abs_paths)
                            self.log_signal.emit(f"이미지 경로: {paths_str}")

                            self.band_driver.execute_script("""
                                var input = arguments[0];
                                input.style.display = 'block';
                                input.style.visibility = 'visible';
                                input.style.opacity = '1';
                            """, photo_input)

                            photo_input.send_keys(paths_str)
                            self.log_signal.emit("이미지 경로 입력 성공")

                            # --- 수정된 부분 시작 ---
                            start_time = time.time()
                            timeout = 10  # 최대 15초 대기

                            while True:
                                try:
                                    thumbs = self.band_driver.find_elements(By.CSS_SELECTOR, "img._thumbImg")
                                    attach_btns = self.band_driver.find_elements(By.XPATH, "//button[contains(text(), '첨부')]")

                                    if len(thumbs) == image_count and attach_btns and attach_btns[0].is_enabled():
                                        self.log_signal.emit(f"✅ 이미지 {image_count}개 로드 완료 확인!")
                                        break

                                except Exception:
                                    pass

                                if time.time() - start_time > timeout:
                                    self.log_signal.emit(f"⚠️ 이미지 로드 대기 시간 초과 (현재: {len(thumbs)}개)")
                                    break

                                time.sleep(0.2)

                            time.sleep(3)   # 로드 완료 후 3초 대기

                            try:
                                attach_btn = None
                                for selector in [
                                    "//button[contains(text(), '첨부')]",
                                    "//button[contains(@class, 'submit')]",
                                    "//button[contains(@class, 'uButton') and contains(@class, '-confirm')]"
                                ]:
                                    try:
                                        attach_btn = WebDriverWait(self.band_driver, 3).until(
                                            EC.element_to_be_clickable((By.XPATH, selector))
                                        )
                                        self.log_signal.emit(f"첨부 버튼 찾음: {selector}")
                                        break
                                    except:
                                        continue

                                if attach_btn:
                                    self.band_driver.execute_script("arguments[0].click();", attach_btn)
                                    self.log_signal.emit("첨부 버튼 클릭 성공")
                                    time.sleep(2)
                                else:
                                    self.log_signal.emit("첨부 버튼을 찾지 못했습니다.")
                            except Exception as e:
                                self.log_signal.emit(f"첨부 버튼 클릭 실패: {e}")
                            # --- 수정된 부분 끝 ---

                    else:
                        self.log_signal.emit("유효한 이미지 파일이 없습니다.")
                else:
                    self.log_signal.emit("이미지 파일이 없습니다.")
            except Exception as e:
                self.log_signal.emit(f"이미지 첨부 실패: {e}")



            # 6-4. 게시 버튼 클릭 (이미지 첨부 후 대기 추가)
            time.sleep(20)  # 이미지 첨부 후 게시 버튼 클릭 전 충분한 대기 시간 추가
            try:
                post_btn = WebDriverWait(self.band_driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '게시')]"))
                )
                
                # 게시 버튼 클릭 전 다시 확인
                self.log_signal.emit("게시 버튼 클릭 준비 완료")
                
                # 게시 버튼 클릭
                self.band_driver.execute_script("arguments[0].click();", post_btn)
                self.log_signal.emit("게시 버튼 클릭 완료")
                
                # 에디터가 사라질 때까지 대기
                try:
                    WebDriverWait(self.band_driver, 10).until_not(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.contentEditor._richEditor[contenteditable='true']"))
                    )
                    self.log_signal.emit(f"[{current_idx+1}] 게시 완료 확인")
                    upload_success = True
                except:
                    self.log_signal.emit("게시 완료 확인 시간 초과")
                    upload_success = False
                    
            except Exception as e:
                self.log_signal.emit(f"게시 버튼 오류: {str(e)}")
                upload_success = False  # 실패 설정

            # 상태 업데이트 신호 발생 (UI 테이블 업데이트)
            original_idx = product.get("_original_index", current_idx - 1)
            self.status_update_signal.emit(original_idx, "성공" if upload_success else "실패")

            # 6-5. 다음 게시물 전 대기
            if current_idx < total_posts - 1 and not self.stop_flag:
                min_delay = self.delay_min
                max_delay = self.delay_max
                if min_delay > max_delay:
                    min_delay, max_delay = max_delay, min_delay  # 순서가 반대인 경우 교체

                delay = random.uniform(min_delay, max_delay)
                self.log_signal.emit(f"다음 게시물 전 {delay}초 대기 중...")
                time.sleep(delay)

        # 7. 완료
        self.log_signal.emit(
            f"모든 게시물 완료! 성공:{self.success_count}, 실패:{self.error_count}"
        )
        self.detailed_progress_signal.emit(
            total_posts,True,0,
            f"완료! 성공:{self.success_count}, 실패:{self.error_count}"
        )
        self.finished_signal.emit()
        try:
            if self.band_driver:
                self.band_driver.quit()
        except: pass   
            
    def safe_emit_progress(self, value, message=""):
        """안전하게 진행 상황 시그널을 발생시키는 함수"""
        try:
            if hasattr(self, 'progress_signal') and self.progress_signal and not sip.isdeleted(self.progress_signal):
                self.progress_signal.emit(value, message)
        except Exception as e:
            print(f"진행 상황 시그널 발생 중 오류: {str(e)}")        
        
    def debug_image_attachment(self, folder_path, image_files=None):
        """이미지 첨부 과정에 대한 상세 정보를 로깅하는 디버그 함수."""
        # ① image_files 인자가 없으면 폴더에서 .jpg 파일 리스트 자동 생성
        if image_files is None:
            image_files = [
                f for f in os.listdir(folder_path)
                if f.lower().endswith('.jpg')
            ]
            self.log_signal.emit(f"디버그: image_files 인자 미전달, 폴더에서 자동 추출 - {len(image_files)}개")
        else:
            self.log_signal.emit(f"디버그: 이미지 첨부 시작 - 파일 {len(image_files)}개")
        
        self.log_signal.emit(f"디버그: 폴더 경로: {folder_path}")
        valid_image_paths = []

        # ② 파일 존재 여부 및 유효성 확인
        for img_file in image_files:
            full_path = os.path.join(folder_path, img_file)
            if os.path.exists(full_path):
                try:
                    # 파일 열어서 읽어보기
                    with open(full_path, 'rb') as f:
                        f.read()
                    size = os.path.getsize(full_path)
                    valid_image_paths.append(full_path)
                    self.log_signal.emit(
                        f"디버그: 이미지 {img_file} - 존재 및 유효 (크기: {size} 바이트)"
                    )
                except Exception as e:
                    self.log_signal.emit(
                        f"디버그: 이미지 {img_file} - 유효성 검사 실패: {e}"
                    )
            else:
                self.log_signal.emit(
                    f"디버그: 이미지 {img_file} - 파일이 존재하지 않음"
                )

        # ③ 최종 유효 경로 목록 반환
        return valid_image_paths
        
    
    def filter_bmp(self, text):
        # BMP(0x0000 ~ 0xFFFF) 범위 내의 문자만 남기고, 나머지는 제거
        return ''.join(ch for ch in text if ord(ch) <= 0xFFFF)
        
    def check_chromedriver_version(self):
        """크롬 드라이버 버전 확인 및 업데이트 필요 여부 확인"""
        try:
            # 크롬 버전 확인
            chrome_version = self.get_chrome_version()
            self.log_signal.emit(f"현재 Chrome 버전: {chrome_version}")
            
            # 드라이버 버전 확인
            try:
                driver_version = uc.get_browser_version()
                self.log_signal.emit(f"현재 ChromeDriver 버전: {driver_version}")
                
                # 버전 비교 (주 버전만 비교)
                chrome_major = chrome_version.split('.')[0] if chrome_version else ""
                driver_major = driver_version.split('.')[0] if driver_version else ""
                
                if chrome_major and driver_major and chrome_major != driver_major:
                    self.log_signal.emit(f"⚠️ Chrome 버전({chrome_major})과 ChromeDriver 버전({driver_major})이 일치하지 않습니다.")
                    return False
                return True
            except Exception as e:
                self.log_signal.emit(f"ChromeDriver 버전 확인 실패: {str(e)}")
                return False
        except Exception as e:
            self.log_signal.emit(f"버전 확인 중 오류: {str(e)}")
            return False
    
    def check_network_connection_detailed(self):
        """상세한 네트워크 연결 상태 확인"""
        try:
            # DNS 확인
            import socket
            try:
                socket.gethostbyname("band.us")
                self.log_signal.emit("✅ DNS 확인 성공: band.us")
            except socket.gaierror:
                self.log_signal.emit("❌ DNS 확인 실패: band.us")
                return False
            
            # 인터넷 연결 확인
            test_urls = [
                ("https://www.google.com", "Google"),
                ("https://band.us", "Band"),
                ("https://www.naver.com", "Naver")
            ]
            
            success_count = 0
            for url, name in test_urls:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        self.log_signal.emit(f"✅ 네트워크 연결 확인 성공: {name} ({url})")
                        success_count += 1
                    else:
                        self.log_signal.emit(f"⚠️ 네트워크 응답 코드 비정상: {name} ({url}) - {response.status_code}")
                except requests.RequestException as e:
                    self.log_signal.emit(f"❌ 네트워크 연결 확인 실패: {name} ({url}) - {str(e)}")
            
            # 최소 하나 이상의 사이트 접속 성공 필요
            if success_count > 0:
                self.log_signal.emit(f"네트워크 연결 확인 완료: {success_count}/{len(test_urls)} 성공")
                return True
            else:
                self.log_signal.emit("❌ 모든 테스트 URL에 접속 실패. 네트워크 연결에 문제가 있습니다.")
                return False
        except Exception as e:
            self.log_signal.emit(f"네트워크 확인 중 오류: {str(e)}")
            return False
    
    def setup_proxy(self, options):
        """프록시 설정 추가 (필요한 경우)"""
        try:
            # 프록시 설정 (필요한 경우 주석 해제)
            # options.add_argument('--proxy-server=http://your-proxy-server:port')
            
            # 또는 환경 변수에서 프록시 설정 가져오기
            proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
            if proxy:
                self.log_signal.emit(f"시스템 프록시 설정 감지: {proxy}")
                options.add_argument(f'--proxy-server={proxy}')
                return True
            return False
        except Exception as e:
            self.log_signal.emit(f"프록시 설정 중 오류: {str(e)}")
            return False        
        
    def get_dir_size(self, path):
        """디렉토리 크기를 바이트 단위로 계산"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
        return total_size

    def get_chrome_version(self):
        """시스템에 설치된 Chrome 버전 확인"""
        try:
            if sys.platform.startswith('win'):
                # Windows
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Google\Chrome\BLBeacon')
                version, _ = winreg.QueryValueEx(key, 'version')
                return version
            elif sys.platform.startswith('darwin'):
                # macOS
                process = subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version'], 
                                          stdout=subprocess.PIPE)
                version = process.communicate()[0].decode('UTF-8').replace('Google Chrome ', '').strip()
                return version
            elif sys.platform.startswith('linux'):
                # Linux
                process = subprocess.Popen(['google-chrome', '--version'], 
                                          stdout=subprocess.PIPE)
                version = process.communicate()[0].decode('UTF-8').replace('Google Chrome ', '').strip()
                return version
        except Exception as e:
            return f"확인 실패: {str(e)}"
        return "알 수 없음"

    def check_network_connection(self):
        """네트워크 연결 상태 확인"""
        try:
            # 인터넷 연결 확인
            test_urls = ["https://www.google.com", "https://band.us"]
            for url in test_urls:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        self.log_signal.emit(f"네트워크 연결 확인 성공: {url}")
                        return True
                except requests.RequestException as e:
                    self.log_signal.emit(f"네트워크 연결 확인 실패 ({url}): {str(e)}")
            
            # 모든 URL 테스트 실패
            self.log_signal.emit("⚠️ 네트워크 연결 문제가 있을 수 있습니다.")
            return False
        except Exception as e:
            self.log_signal.emit(f"네트워크 확인 중 오류: {str(e)}")
            return False        
        
    def create_temp_folders_for_posts(self):
        """
        크롤링한 게시물을 임시 폴더에 저장하는 함수 (개선 버전)
        """
        self.log_signal.emit("임시 폴더에 크롤링한 게시물 저장 중...")
        
        # 임시 폴더 기본 경로 설정
        temp_base_folder = os.path.join(os.getcwd(), "TEMP_CRAWLED")
        if not os.path.exists(temp_base_folder):
            os.makedirs(temp_base_folder)
        
        # 기존 임시 폴더 정리
        try:
            shutil.rmtree(temp_base_folder)
            os.makedirs(temp_base_folder)
            self.log_signal.emit(f"기존 임시 폴더를 정리하고 새로 생성했습니다: {temp_base_folder}")
        except Exception as e:
            self.log_signal.emit(f"임시 폴더 정리 중 오류: {str(e)}")
            # 폴더가 없거나 삭제할 수 없는 경우 새로 생성
            os.makedirs(temp_base_folder, exist_ok=True)
        
        # 각 게시물별로 폴더 생성 및 내용 저장
        for current_idx, product in enumerate(self.crawled_products, 1):
            # 폴더 생성 (1, 2, 3, ... 번호 순서대로)
            folder_name = str(current_idx)
            folder_path = os.path.join(temp_base_folder, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            
            # 텍스트 파일 저장 (게시물 내용)
            text_file_path = os.path.join(folder_path, f"{folder_name}_content.txt")
            with open(text_file_path, "w", encoding="utf-8") as f:
                # 원본 크롤링 내용 사용 (텍스트 크기 변경 없이)
                f.write(product.get("raw_description", ""))
            
            # 이미지 파일 복사
            image_count = 0
            
            # 여기서부터 수정: 원본 저장 경로(local_image_dir)를 최우선으로 찾습니다.
            src_dir = product.get("local_image_dir", self.final_target_folder)
            
            for img_idx, img_file in enumerate(product.get("image_files", []), 1):
                src_path = os.path.join(src_dir, img_file)
                dst_path = os.path.join(folder_path, f"{folder_name}_image_{img_idx}.jpg")
                
                if os.path.exists(src_path):
                    try:
                        shutil.copy2(src_path, dst_path)
                        image_count += 1
                    except Exception as e:
                        self.log_signal.emit(f"이미지 복사 오류 ({src_path}): {str(e)}")
                else:
                    self.log_signal.emit(f"이미지 파일이 존재하지 않습니다: {src_path}")
            
            self.log_signal.emit(f"게시물 {current_idx}: 내용 저장 및 이미지 {image_count}개 복사 완료")
        
        self.log_signal.emit(f"총 {len(self.crawled_products)}개 게시물이 임시 폴더에 저장되었습니다.")
        return temp_base_folder
        
    def stop(self):
        self.stop_flag = True
        self.log_signal.emit("작업 중지 요청이 접수되었습니다.")
        
    def confirm_login(self):
        self.login_confirmed = True
