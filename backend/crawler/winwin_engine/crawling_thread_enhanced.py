from PyQt5.QtCore import QThread, pyqtSignal
import time
import os
import concurrent.futures
import requests
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class EnhancedCrawlingThread(QThread):
    """향상된 로깅 기능이 추가된 크롤링 스레드"""
    
    # 기존 시그널
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    result_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(int)
    
    # 새로운 상세 로깅 시그널
    detailed_log_signal = pyqtSignal(str, str, bool)  # 메시지, 레벨, 상태표시 여부
    detailed_progress_signal = pyqtSignal(int, bool, int, str)  # 현재 진행, 성공여부, 이미지 수, 작업 설명
    stats_signal = pyqtSignal(dict)  # 통계 정보
    
    def __init__(self, driver, start_date, end_date, max_count, selected_cat_text, target_folder, parent=None):
        super().__init__(parent)
        self.driver = driver
        self.start_date = start_date
        self.end_date = end_date
        self.max_count = max_count
        self.selected_cat_text = selected_cat_text
        self.target_folder = target_folder
        self.stop_flag = False
        
        # 통계 정보
        self.stats = {
            "start_time": None,
            "end_time": None,
            "total_posts": 0,
            "processed_posts": 0,
            "success_posts": 0,
            "error_posts": 0,
            "total_images": 0,
            "downloaded_images": 0,
            "failed_images": 0,
            "skipped_posts": 0,
            "current_task": "초기화 중..."
        }
    
    def extract_post_date(self, post_elem):
        """게시물 요소에서 날짜를 추출하여 datetime 객체로 반환"""
        try:
            # data-tooltip 속성에서 날짜 추출 (예: "2025년 4월 19일 오후 03:27")
            date_anchor = post_elem.find_element(By.CSS_SELECTOR, "a.time._linkPost")
            tooltip = date_anchor.get_attribute("data-tooltip")
            
            if tooltip and tooltip.strip() and tooltip.lower() != "true":
                self.detailed_log_signal.emit(f"날짜 추출: {tooltip}", "DEBUG", False)
                return self.parse_date_from_text(tooltip)
            else:
                text_date = date_anchor.text
                self.detailed_log_signal.emit(f"data-tooltip 속성이 없거나 유효하지 않음, 텍스트 사용: {text_date}", "WARNING", False)
                return self.parse_date_from_text(text_date)
            
        except Exception as e:
            self.detailed_log_signal.emit(f"날짜 추출 오류: {e}", "ERROR", False)
            return None
    
    def parse_date_from_text(self, text):
        """날짜 문자열을 datetime 객체로 파싱"""
        from datetime import datetime, timedelta
        import re

        try:
            if not text or text.strip() == "":
                self.detailed_log_signal.emit("날짜 텍스트가 비어있음", "WARNING", False)
                return None

            # 상세 로깅 추가
            self.detailed_log_signal.emit(f"날짜 파싱 시도: '{text}'", "DEBUG", False)

            # 상대적 시간 표현 처리 (예: "7시간 전")
            relative_time_match = re.match(r'(\d+)\s*(시간|분|초|일|주|개월|년)\s*전', text)
            if relative_time_match:
                num, unit = relative_time_match.groups()
                num = int(num)
                now = datetime.now()
                
                time_map = {
                    '초': timedelta(seconds=num),
                    '분': timedelta(minutes=num),
                    '시간': timedelta(hours=num),
                    '일': timedelta(days=num),
                    '주': timedelta(weeks=num),
                    '개월': timedelta(days=num*30),  # 근사값
                    '년': timedelta(days=num*365)    # 근사값
                }
                
                result_date = now - time_map.get(unit, timedelta(0))
                self.detailed_log_signal.emit(f"상대적 시간 변환: '{text}' → {result_date.strftime('%Y-%m-%d %H:%M:%S')}", "DEBUG", False)
                return result_date

            current_year = datetime.now().year

            # 1. 연도 포함 형식 (예: "2025년 4월 19일 오후 03:27")
            match = re.match(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s*(\d{1,2}):(\d{2})", text)
            if match:
                y, m, d, ampm, h, min = match.groups()
                self.detailed_log_signal.emit(f"연도 포함 형식 매치: {match.groups()}", "DEBUG", False)
            else:
                # 2. 연도 없음 형식 (예: "4월 19일 오후 03:27")
                match = re.match(r"(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s*(\d{1,2}):(\d{2})", text)
                if not match:
                    self.detailed_log_signal.emit(f"날짜 형식 인식 실패: {text}", "WARNING", False)
                    return None
                y = current_year
                m, d, ampm, h, min = match.groups()
                self.detailed_log_signal.emit(f"연도 없는 형식 매치: {match.groups()}, 현재 연도({y}) 사용", "DEBUG", False)

            h = int(h)
            if ampm == '오후' and h < 12:
                h += 12
            elif ampm == '오전' and h == 12:
                h = 0

            dt = datetime(int(y), int(m), int(d), h, int(min))
            self.detailed_log_signal.emit(f"날짜 파싱 성공: {text} → {dt.strftime('%Y-%m-%d %H:%M:%S')}", "INFO", False)
            return dt

        except Exception as e:
            self.detailed_log_signal.emit(f"날짜 파싱 오류: {e}", "ERROR", False)
            return None
    
    def run(self):
        """크롤링 실행"""
        from datetime import datetime
        import time
        import os
        import concurrent.futures
        import requests

        # 통계 초기화
        self.stats["start_time"] = time.time()
        self.stats["total_posts"] = self.max_count
        
        self.detailed_log_signal.emit("크롤링 시작", "INFO", True)
        self.stats["current_task"] = "페이지 초기화 중..."
        self.stats_signal.emit(self.stats)
        
        count = 0
        posts_selector = "div.section._activity"

        try:
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
        except Exception as e:
            self.detailed_log_signal.emit(f"초기 스크롤 실패: {str(e)}", "ERROR", True)
            return

        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
        except Exception as e:
            self.detailed_log_signal.emit(f"스크롤을 위한 드라이버 명령 실행 오류: {str(e)}", "ERROR", True)
            return

        while count < self.max_count and not self.stop_flag:
            try:
                self.stats["current_task"] = "게시물 목록 로딩 중..."
                self.stats_signal.emit(self.stats)
                
                posts = self.driver.find_elements(By.CSS_SELECTOR, posts_selector)
                post_count = len(posts)
                self.detailed_log_signal.emit(f"현재 로드된 게시물 개수: {post_count}", "INFO", False)
            except Exception as e:
                self.detailed_log_signal.emit(f"게시물 찾기 오류: {str(e)}", "ERROR", True)
                break

            # 현재 게시물 수가 부족하면 스크롤하여 추가 로드
            if len(posts) <= count:
                try:
                    self.stats["current_task"] = "추가 게시물 로딩을 위해 스크롤 중..."
                    self.stats_signal.emit(self.stats)
                    
                    self.detailed_log_signal.emit("더 많은 게시물을 로드하기 위해 스크롤 중...", "INFO", False)
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    self.detailed_log_signal.emit(f"스크롤 후 새 높이: {new_height}, 이전 높이: {last_height}", "DEBUG", False)
                    
                    if new_height == last_height:
                        self.detailed_log_signal.emit("더 이상 게시물이 로드되지 않습니다.", "WARNING", True)
                        break
                    
                    last_height = new_height
                    continue
                except Exception as e:
                    self.detailed_log_signal.emit(f"스크롤 명령 실행 오류: {str(e)}", "ERROR", True)
                    break

            # 각 게시물을 순차적으로 처리
            for post in posts[count:]:
                if count >= self.max_count or self.stop_flag:
                    break
                
                try:
                    self.stats["current_task"] = f"게시물 {count+1}/{self.max_count} 처리 중..."
                    self.stats_signal.emit(self.stats)
                    
                    # 날짜 정보 추출
                    try:
                        post_date = self.extract_post_date(post)
                        if not post_date:
                            self.detailed_log_signal.emit("게시물에서 날짜 정보를 찾을 수 없습니다. 해당 게시물을 건너뜁니다.", "WARNING", False)
                            self.stats["skipped_posts"] += 1
                            continue
                    except Exception as e:
                        self.detailed_log_signal.emit(f"날짜 정보 추출 중 오류: {e}", "ERROR", False)
                        self.stats["skipped_posts"] += 1
                        continue

                    if not post_date:
                        self.detailed_log_signal.emit("게시물에서 날짜 정보를 찾을 수 없습니다. 해당 게시물을 건너뜁니다.", "WARNING", False)
                        self.stats["skipped_posts"] += 1
                        continue

                    # 날짜 범위 확인
                    if not (self.start_date <= post_date <= self.end_date):
                        self.detailed_log_signal.emit(
                            f"게시물 날짜 {post_date.strftime('%Y-%m-%d %H:%M')}가 선택 범위 밖입니다. 건너뜁니다.", 
                            "INFO", False
                        )
                        self.stats["skipped_posts"] += 1
                        if post_date < self.start_date:
                            self.detailed_log_signal.emit("더 오래된 게시물이므로, 크롤링을 종료합니다.", "INFO", True)
                            self.stop_flag = True
                        continue

                    # 본문 텍스트 추출
                    try:
                        content_element = post.find_element(By.CSS_SELECTOR, "div.fd_cont div._content")
                        raw_text = content_element.text.strip()
                        self.detailed_log_signal.emit(f"게시물 텍스트 추출 성공 (길이: {len(raw_text)}자)", "DEBUG", False)
                    except Exception as e:
                        self.detailed_log_signal.emit(f"본문 텍스트 추출 오류: {str(e)}", "ERROR", False)
                        raw_text = ""

                    # 이미지 추출 및 다운로드
                    try:
                        self.stats["current_task"] = f"게시물 {count+1}/{self.max_count} 이미지 처리 중..."
                        self.stats_signal.emit(self.stats)
                        
                        images = post.find_elements(By.CSS_SELECTOR, "div.wrap_swipe img")
                        image_count = len(images)
                        self.detailed_log_signal.emit(f"게시물에서 {image_count}개의 이미지 발견", "INFO", False)
                        self.stats["total_images"] += image_count
                        
                        image_files = []
                        
                        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
                            tasks = []
                            for idx, img in enumerate(images):
                                src = img.get_attribute("src")
                                if src:
                                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                                    filename = f"{timestamp}_{count+1}_{idx+1}.jpg"
                                    filepath = os.path.join(self.target_folder, filename)
                                    tasks.append((src, filepath, filename))
                            
                            # 이미지 다운로드 함수
                            def download_image(src, filepath):
                                try:
                                    r = requests.get(src, timeout=5)
                                    with open(filepath, "wb") as f:
                                        f.write(r.content)
                                    self.stats["downloaded_images"] += 1
                                    return True
                                except Exception as e:
                                    self.detailed_log_signal.emit(f"이미지 다운로드 실패: {src} - {e}", "ERROR", False)
                                    self.stats["failed_images"] += 1
                                    return False
                            
                            # 다운로드 진행 상황 로깅
                            self.detailed_log_signal.emit(f"이미지 다운로드 시작: {len(tasks)}개", "INFO", False)
                            
                            results = list(executor.map(lambda args: download_image(args[0], args[1]), [(t[0], t[1]) for t in tasks]))
                            image_files = [tasks[i][2] for i, r in enumerate(results) if r]
                            
                            self.detailed_log_signal.emit(f"이미지 다운로드 완료: {len(image_files)}/{len(tasks)}개 성공", "INFO", False)
                    except Exception as e:
                        self.detailed_log_signal.emit(f"이미지 처리 오류: {str(e)}", "ERROR", False)
                        image_files = []

                    # 게시물 처리: 제목, 도매가, 판매가 등을 변환
                    self.stats["current_task"] = f"게시물 {count+1}/{self.max_count} 데이터 변환 중..."
                    self.stats_signal.emit(self.stats)
                    
                    title, body = transform_kakao_story_text_alt(raw_text)
                    ddg_value = parse_ddg_value(raw_text)
                    sale_price = compute_sale_price(ddg_value, self.selected_cat_text)
                    basic_code = get_final_code(raw_text, self.selected_cat_text)
                    product_code = generate_product_code(basic_code, basic_code)

                    # 결과 전송
                    result_data = {
                        "title": title,
                        "body": body,
                        "raw_description": raw_text,
                        "product_code": product_code,
                        "image_files": image_files,
                        "price_input": ddg_value,
                        "sale_price": sale_price,
                        "created_at": post_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "full_text": raw_text
                    }
                    
                    self.result_signal.emit(result_data)
                    count += 1
                    self.progress_signal.emit(count)
                    
                    # 상세 진행 정보 업데이트
                    self.stats["processed_posts"] += 1
                    self.stats["success_posts"] += 1
                    self.detailed_progress_signal.emit(count, True, len(image_files), f"게시물 {count}/{self.max_count} 처리 완료")
                    
                    self.detailed_log_signal.emit(
                        f"게시물 {count} 크롤링 완료. 날짜: {post_date.strftime('%Y-%m-%d %H:%M')} / "
                        f"상품코드: {product_code} / 제목: {title} / 도매가: {ddg_value} / 판매가: {sale_price} / "
                        f"이미지: {len(image_files)}개",
                        "INFO", True
                    )
                    
                except Exception as e:
                    self.detailed_log_signal.emit(f"게시물 처리 오류: {str(e)}", "ERROR", True)
                    self.stats["error_posts"] += 1
                    continue

            # 더 많은 게시물 로드를 위해 스크롤
            if count < self.max_count and not self.stop_flag:
                try:
                    self.stats["current_task"] = "추가 게시물 로딩을 위해 스크롤 중..."
                    self.stats_signal.emit(self.stats)
                    
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    
                    if new_height == last_height:
                        self.detailed_log_signal.emit("더 이상 게시물이 로드되지 않습니다.", "WARNING", True)
                        break
                    
                    last_height = new_height
                except Exception as e:
                    self.detailed_log_signal.emit(f"스크롤 명령 실행 오류: {str(e)}", "ERROR", True)
                    break

        # 크롤링 완료 통계
        self.stats["end_time"] = time.time()
        self.stats["current_task"] = "크롤링 완료"
        self.stats_signal.emit(self.stats)
        
        # 소요 시간 계산
        elapsed_time = self.stats["end_time"] - self.stats["start_time"]
        elapsed_str = self.format_time(elapsed_time)
        
        self.detailed_log_signal.emit(
            f"크롤링 완료! 총 {count}개 게시물 처리 (성공: {self.stats['success_posts']}, "
            f"실패: {self.stats['error_posts']}, 건너뜀: {self.stats['skipped_posts']}) | "
            f"이미지: {self.stats['downloaded_images']}/{self.stats['total_images']}개 | "
            f"소요 시간: {elapsed_str}",
            "INFO", True
        )
        
        self.finished_signal.emit(count)
    
    def stop(self):
        """크롤링 중지"""
        self.stop_flag = True
        self.detailed_log_signal.emit("크롤링 중지 요청이 접수되었습니다.", "WARNING", True)
    
    def format_time(self, seconds):
        """시간을 읽기 쉬운 형식으로 변환"""
        if seconds < 60:
            return f"{seconds:.1f}초"
        elif seconds < 3600:
            minutes = seconds // 60
            seconds %= 60
            return f"{int(minutes)}분 {int(seconds)}초"
        else:
            hours = seconds // 3600
            seconds %= 3600
            minutes = seconds // 60
            seconds %= 60
            return f"{int(hours)}시간 {int(minutes)}분 {int(seconds)}초"
