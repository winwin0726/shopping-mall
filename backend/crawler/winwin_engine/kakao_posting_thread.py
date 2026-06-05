import os
import time
import random
import shutil
import json
import sys
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import undetected_chromedriver as uc
from PyQt5.QtCore import QThread, pyqtSignal
from core.driver_manager import create_uc_driver

class KakaoPostingThread(QThread):
    # UI 업데이트를 위한 시그널 정의 (BandPostingThread와 동일 구조 유지)
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    status_update_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal()
    login_required_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    profile_restore_signal = pyqtSignal()
    detailed_progress_signal = pyqtSignal(int, bool, int, str)
    
    def __init__(self, post_list, crawled_products, final_target_folder, delay_min, delay_max, kakao_id="", kakao_pw="", parent=None):
        super().__init__(parent)
        self.post_list = post_list
        self.crawled_products = crawled_products
        self.final_target_folder = final_target_folder
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.kakao_id = kakao_id
        self.kakao_pw = kakao_pw
        self.stop_flag = False
        self.kakao_driver = None
        self.login_confirmed = False
        self.success_count = 0
        self.error_count = 0
        self.is_running = False
        
    def load_kakao_profiles(self):
        """Settings나 JSON에서 카카오 계정 로드"""
        try:
            from PyQt5.QtCore import QSettings
            settings = QSettings("WINWIN", "AutoCrawler")
            
            self.log_signal.emit("카카오 프로필 로드 시도 중...")
            kakao_profiles = settings.value("kakao/profiles", {})
            
            profiles_list = []
            if isinstance(kakao_profiles, dict):
                for name, data in kakao_profiles.items():
                    profiles_list.append({
                        "id": data.get("id", ""),
                        "pw": data.get("pw", "")
                    })
            
            if not profiles_list:
                # 저장된 프로필이 없을 경우 빈 목록 반환 (에러 로깅)
                self.log_signal.emit("저장된 카카오 프로필이 없습니다.")
                
            return profiles_list
            
        except Exception as e:
            self.log_signal.emit(f"카카오 프로필 로드 오류: {e}")
            return []

    def log(self, text):
        """내부 로깅 헬퍼"""
        print(f"[KakaoUpload] {text}")
        self.log_signal.emit(text)

    def safe_emit_progress(self, val):
        try:
            self.progress_signal.emit(val)
        except Exception:
            pass

    def stop(self):
        self.stop_flag = True
        self.log("작업 중지 요청이 접수되었습니다.")

    def get_dir_size(self, path):
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
        except Exception:
            pass
        return total_size

    def create_temp_folders_for_kakao_posts(self):
        """임시 이미지 폴더 생성 (밴드 스레드 코드 차용)"""
        base_dir = os.path.join(os.getcwd(), "temp_kakao_images")
        
        # 기존 폴더 삭제
        if os.path.exists(base_dir):
            try:
                shutil.rmtree(base_dir)
                import stat
                def remove_readonly(func, path, _):
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                shutil.rmtree(base_dir, onerror=remove_readonly)
            except Exception as e:
                self.log(f"임시 폴더 삭제 실패: {e}")

        os.makedirs(base_dir, exist_ok=True)
        
        # 각 게시물별 폴더 생성 및 파일 복사
        for idx, post in enumerate(self.post_list, 1):
            target_path = os.path.join(base_dir, str(idx))
            os.makedirs(target_path, exist_ok=True)
            
            img_files = post.get("image_files", [])
            local_img_dir = post.get("local_image_dir", self.final_target_folder)
            
            for file_path in img_files:
                try:
                    if os.path.isabs(file_path):
                        abs_file_path = file_path
                    else:
                        abs_file_path = os.path.join(local_img_dir, os.path.basename(file_path))
                        
                    if os.path.exists(abs_file_path):
                        shutil.copy2(abs_file_path, target_path)
                    else:
                        self.log(f"원본 이미지 파일 찾기 실패: {abs_file_path}")
                except Exception as e:
                    self.log(f"파일 복사 오류 ({file_path}): {e}")
                    
        return base_dir

    def perform_auto_login(self):
        """카카오스토리 자동 로그인 (이메일 폼 매핑)"""
        try:
            self.log("카카오스토리 자동 로그인 시작...")
            
            # 이미 로그인된 상태인지 확인 (내 프로필 또는 글쓰기 버튼)
            try:
                WebDriverWait(self.kakao_driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.btn_write, div.profile_info"))
                )
                self.log("이미 로그인된 세션입니다.")
                self.login_confirmed = True
                return True
            except:
                pass

            # 이미 카카오계정 로그인 페이지로 넘어갔는지 체크
            if "accounts.kakao.com" in self.kakao_driver.current_url:
                self.log("이미 카카오계정 로그인 페이지에 진입해 있습니다.")
            else:
                # 메인 로그인 버튼 찾기
                login_btn = None
                for sel in ["a.btn_login", "button.btn_login", "a.link_login"]:
                    try:
                        login_btn = WebDriverWait(self.kakao_driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                        )
                        break
                    except: continue
                    
                if login_btn:
                    self.log("메인 로그인 버튼 클릭")
                    self.kakao_driver.execute_script("arguments[0].click();", login_btn)
                    time.sleep(random.uniform(2, 3))
                else:
                    if "accounts.kakao.com" not in self.kakao_driver.current_url:
                        self.log("로그인 버튼을 찾지 못해 로그인 페이지로 강제 이동합니다.")
                        self.kakao_driver.get("https://accounts.kakao.com/login?continue=https%3A%2F%2Fstory.kakao.com")
                        time.sleep(random.uniform(2, 3))
                
            if not self.kakao_id or not self.kakao_pw:
                self.log("카카오 계정 정보가 없습니다. 수동 로그인을 진행해주세요.")
                return False

            self.log(f"선택된 계정: {self.kakao_id}")

            # 이메일, 비밀번호 입력 필드 타겟팅 (카카오 통합 로그인 페이지 DOM)
            login_id_input = WebDriverWait(self.kakao_driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input#loginId--1, input[name='loginId']"))
            )
            password_input = WebDriverWait(self.kakao_driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input#password--2, input[name='password']"))
            )
            
            # 입력 전 초기화
            login_id_input.clear()
            time.sleep(0.5)
            # send_keys 는 봇 탐지에 걸릴 수 있어 JS로 값 입력 후 dispatchEvent 처리하거나 한글자씩 입력
            for char in self.kakao_id:
                login_id_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
                
            time.sleep(random.uniform(0.5, 1.5))
            
            password_input.clear()
            time.sleep(0.5)
            for char in self.kakao_pw:
                password_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
                
            time.sleep(random.uniform(1, 2))
            
            # 최종 로그인 버튼 클릭
            submit_btn = WebDriverWait(self.kakao_driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn_g.highlight.submit"))
            )
            self.kakao_driver.execute_script("arguments[0].click();", submit_btn)
            
            # 2단계 인증이나 봇 체크 대기 (수동 대응 필요시 대비)
            time.sleep(random.uniform(3, 5))
            
            try:
                WebDriverWait(self.kakao_driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.btn_write, div.profile_info"))
                )
                self.log("카카오 자동 로그인 성공!")
                self.login_confirmed = True
                return True
            except:
                self.log("자동 로그인 후 세션 확인 실패 (캡챠 또는 2단계 인증 요구 가능성)")
                return False
                
        except Exception as e:
            self.log(f"카카오 자동 로그인 에러: {e}")
            return False

    def debug_image_attachment(self, folder_path, files):
        valid = []
        for f in files:
            p = os.path.join(folder_path, f)
            if os.path.getsize(p) > 0:
                valid.append(p)
        return valid

    def run(self):
        try:
            self.is_running = True
            self.log("========== 카카오스토리 자동 업로드 시작 ==========")
            self.safe_emit_progress(0)
            
            profile_dir = os.path.join(os.getcwd(), "kakao_profile_optimized")
            MAX_PROFILE_MB = 50
            
            if os.path.exists(profile_dir):
                size_mb = self.get_dir_size(profile_dir) / (1024*1024)
                if size_mb > MAX_PROFILE_MB:
                    self.log(f"프로필 캐시 정리 (크기: {size_mb:.2f}MB)")
                    for cp in [
                        os.path.join(profile_dir, "Default", "Cache"),
                        os.path.join(profile_dir, "Default", "Media Cache")
                    ]:
                        if os.path.exists(cp):
                            try: shutil.rmtree(cp)
                            except: pass
            else:
                os.makedirs(profile_dir, exist_ok=True)
                
            max_retries = 3
            self.kakao_driver = None
            
            for i in range(max_retries):
                try:
                    self.log(f"Chrome 시작 시도 {i+1}/{max_retries}")
                    
                    options = uc.ChromeOptions()
                    options.add_argument("--disable-blink-features=AutomationControlled")
                    options.add_argument("--start-maximized")
                    options.add_argument(f"--user-data-dir={profile_dir}")
                    
                    # 공용 드라이버 매니저 호출 (Windows 환경 안정성을 위해 use_subprocess=True 유지)
                    self.kakao_driver = create_uc_driver(options, use_subprocess=True, log_func=self.log)
                    self.log("드라이버 실행 완료")
                    break
                except Exception as e:
                    self.log(f"드라이버 실패 ({i+1}): {e}")
                    if i == max_retries-1: raise
                    time.sleep(2)
            
            if not self.kakao_driver:
                raise Exception("카카오 드라이버 초기화 실패")
                
            self.detailed_progress_signal.emit(0, True, 0, "드라이버 초기화 완료")
            
            # 3. 사이트 진입 및 로그인 처리
            self.log("카카오스토리 페이지 이동 중...")
            self.kakao_driver.get("https://story.kakao.com/")
            time.sleep(3)
            
            login_success = self.perform_auto_login()
            if not login_success:
                self.log("로그인 필요 - 브라우저 창에서 수동으로 로그인을 완료해주세요.")
                self.login_required_signal.emit()
                
                # 사용자가 로그인할 때까지 무한 대기 (stop_flag 트리거 전까지)
                while not self.login_confirmed and not self.stop_flag:
                    time.sleep(1)
                    
                if self.stop_flag:
                    self.log("사용자 로그인 대기 중 취소됨")
                    return
            
            # 4. 임시 폴더 생성 (사진 격리용)
            temp_folder = self.create_temp_folders_for_kakao_posts()
            self.log(f"임시 이미지 폴더 세팅 완료: {temp_folder}")
            
            total_posts = len(self.post_list)
            self.success_count = 0
            self.error_count = 0
            
            # 5. 업로드 루프 시작
            for current_idx, product in enumerate(self.post_list, start=1):
                if self.stop_flag:
                    self.log("작업 중지됨")
                    break
                    
                self.safe_emit_progress(current_idx)
                upload_success = False
                
                title = product.get("title", f"상품 {current_idx}")
                self.log(f"[{current_idx}/{total_posts}] 카카오 포스팅 시작: {title}")
                self.detailed_progress_signal.emit(current_idx-1, True, len(product.get("image_files", [])), f"[{current_idx}/{total_posts}] 쓰기 중")
                
                # ---- 루프 내부 세부 동작 ----
                
                # 5-1. (홈 또는 내스토리 이동 후) 글쓰기 영역 오픈 대기
                sec_min, sec_max = sorted([self.delay_min, self.delay_max])
                delay = random.uniform(sec_min, sec_max)
                self.log(f"⏱ {delay:.1f}초 후 작성 시작")
                time.sleep(delay)
                
                try:
                    # 카카오스토리는 기본적으로 최상단에 글쓰기 폼이 있음 (새소식올리기 버튼)
                    write_btn = WebDriverWait(self.kakao_driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a.link_write._toggleWriteButton, a.btn_write"))
                    )
                    self.kakao_driver.execute_script("arguments[0].click();", write_btn)
                    time.sleep(1.5)
                except Exception as e:
                    self.log(f"⚠️ 글쓰기 박스 켜기 버튼 탐색 실패: {e}")
                
                try:
                    # 5-2. 사진 첨부 (input[type='file'])
                    folder_path = os.path.join(temp_folder, str(current_idx))
                    image_files = [f for f in os.listdir(folder_path) if f.endswith('.jpg')]
                    
                    if image_files:
                        valid_paths = self.debug_image_attachment(folder_path, image_files)
                        if valid_paths:
                            # 카카오스토리 사진 첨부 input
                            photo_input = WebDriverWait(self.kakao_driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "input._photoFileInputOutmost[type='file']"))
                            )
                            abs_paths = [os.path.abspath(p) for p in valid_paths]
                            paths_str = "\n".join(abs_paths)
                            
                            self.kakao_driver.execute_script("""
                                arguments[0].style.display = 'block';
                                arguments[0].style.visibility = 'visible';
                            """, photo_input)
                            
                            photo_input.send_keys(paths_str)
                            self.log(f"이미지 {len(valid_paths)}개 파일 전송 완료, 썸네일 로딩 대기중...")
                            
                            # 썸네일 노출 대기 (카카오 특유의 class: .item_photo 등)
                            wait_time = 0
                            while wait_time < 15:
                                try:
                                    # 카카오 사진 리스트 요소 패턴
                                    thumbs = self.kakao_driver.find_elements(By.CSS_SELECTOR, "div.preview_img, .list_photo li, figure.figure_img")
                                    if len(thumbs) >= len(valid_paths):
                                        self.log(f"✅ 사진 썸네일 {len(thumbs)}개 확인 완료")
                                        break
                                except: pass
                                time.sleep(1)
                                wait_time += 1
                                
                    else:
                        self.log("ℹ️ 첨부할 이미지가 없습니다.")
                    
                    time.sleep(random.uniform(1.5, 3.0))
                    
                    # 5-3. 텍스트 본문 입력
                    # 카카오스토리의 내용 영역 (보통 textarea가 아닌 contenteditable div를 사용)
                    editor = WebDriverWait(self.kakao_driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div#contents_write._editable[contenteditable='true']"))
                    )
                    
                    # 클릭하여 포커스
                    ActionChains(self.kakao_driver).move_to_element(editor).click().perform()
                    time.sleep(0.5)
                    
                    raw = product.get("raw_description", "").strip()
                    
                    # 카카오스토리 에디터는 paste 이벤트 발생 시 해시태그와 줄바꿈을 완벽히 파싱합니다.
                    paste_script = """
                        var editor = arguments[0];
                        var text = arguments[1];
                        editor.focus();
                        var dataTransfer = new DataTransfer();
                        dataTransfer.setData('text/plain', text);
                        var event = new ClipboardEvent('paste', {
                            clipboardData: dataTransfer,
                            bubbles: true,
                            cancelable: true
                        });
                        editor.dispatchEvent(event);
                    """
                    self.kakao_driver.execute_script(paste_script, editor, raw)
                    time.sleep(1)
                    
                    # 텍스트의 맨 끝부분 해시태그가 미인식되는 것을 방지하기 위해 스페이스 이벤트 1회 주입
                    ActionChains(self.kakao_driver).send_keys(Keys.SPACE).perform()
                        
                    self.log("✅ 본문 해시태그 및 텍스트 paste 완료")
                    time.sleep(1.5)

                    # 5-3.5. 친구공개 설정
                    try:
                        self.log("친구공개 설정 진행...")
                        # 공개설정 버튼 클릭 (열려있지 않다면)
                        permission_btn = WebDriverWait(self.kakao_driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "button._permissionBtn.bn_open"))
                        )
                        self.kakao_driver.execute_script("arguments[0].click();", permission_btn)
                        time.sleep(0.5)
                        
                        # "친구공개" 라디오 버튼 클릭
                        friend_rdo = WebDriverWait(self.kakao_driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "input#rdo_friend._permissionRadioInput"))
                        )
                        self.kakao_driver.execute_script("arguments[0].click();", friend_rdo)
                        time.sleep(0.5)
                        self.log("✅ 친구공개 설정 완료")
                    except Exception as perm_e:
                        self.log(f"⚠️ 공개설정 변경 중 오류 발생: {perm_e}")
                        pass
                    
                    time.sleep(1)
                    
                    # 5-4. 최종 [올리기] 버튼 클릭
                    submit_btn = WebDriverWait(self.kakao_driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a._postBtn.btn_com"))
                    )
                    
                    self.kakao_driver.execute_script("arguments[0].click();", submit_btn)
                    self.log("올리기 버튼 클릭")
                    
                    # 에디터 창이 사라지거나 새 글 엘리먼트가 나타나는지 대기
                    WebDriverWait(self.kakao_driver, 10).until_not(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div[contenteditable='true'].tf_write"))
                    )
                    
                    self.log(f"[{current_idx}/{total_posts}] 게시 성공 확인!")
                    upload_success = True
                    self.success_count += 1
                    
                except Exception as loop_e:
                    self.log(f"게시물 등록 중 오류: {loop_e}")
                    upload_success = False
                    self.error_count += 1
                
                original_idx = product.get("_original_index", current_idx - 1)
                self.status_update_signal.emit(original_idx, "성공" if upload_success else "실패")
                
            # 6. 완료 처리
            self.log(f"모든 카카오 게시물 업로드 완료! (성공:{self.success_count}, 실패:{self.error_count})")
            self.detailed_progress_signal.emit(total_posts, True, 0, f"완료! 성공:{self.success_count}, 실패:{self.error_count}")

        except Exception as e:
            self.log(f"카카오 글올리기 오류: {str(e)}")
            self.error_signal.emit(f"카카오 스레드 오류: {str(e)}")
        finally:
            if self.kakao_driver:
                try: self.kakao_driver.quit()
                except: pass
            self.is_running = False
            self.finished_signal.emit()

if __name__ == "__main__":
    # 단독 테스트용 코드블록
    # Dummy Data 주입
    app = None
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication(sys.argv)
    except: pass
    
    test_posts = [{"title": "테스트", "image_files": []}]
    t = KakaoPostingThread(test_posts, [], "", 2.0, 5.0)
    t.log_signal.connect(lambda x: print(f" SIGNAL-LOG: {x}"))
    t.start()
    
    if app:
        sys.exit(app.exec_())
