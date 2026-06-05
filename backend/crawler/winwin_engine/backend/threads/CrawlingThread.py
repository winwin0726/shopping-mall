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
from PyQt5.QtGui import QColor, QFont
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

# 루트 경로 참조
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class CrawlingThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    result_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(int)  # 크롤링된 총 아이템 수

    def __init__(self, driver, start_date, end_date, max_count, selected_cat_text, target_folder, transform_function=None, parent=None):
            super().__init__(parent)
            self.driver = driver
            self.start_date = start_date
            self.end_date = end_date
            self.max_count = max_count
            self.selected_cat_text = selected_cat_text
            self.target_folder = target_folder
            self.stop_flag = False
            self.transform_function = transform_function

    def extract_post_date(self, post_elem):
        """
        카카오스토리 포스트 엘리먼트에서 실제 등록일시(절대시간 또는 상대시간)를
        datetime으로 돌려줍니다.
        """
        try:
            # ————————————— 1. data-tooltip(절대시간) 추출 —————————————
            date_anchor = post_elem.find_element(By.CSS_SELECTOR, "a.time._linkPost")
            tooltip = date_anchor.get_attribute("title") or ""

            # “YYYY년”(예: 2025년) 이 포함된 경우만 절대시간으로 간주
            if re.search(r"\d{4}년", tooltip):
                self.log_signal.emit(f"📆 툴팁(절대): {tooltip}")
                return self.parse_date_from_text(tooltip)

            # ————————————— 2. 수정됨 span[data-tooltip] —————————————
            try:
                span_elem = post_elem.find_element(By.CSS_SELECTOR, "span.time span[data-tooltip]")
                span_tooltip = span_elem.get_attribute("data-tooltip") or ""
                if re.search(r"\d{4}년", span_tooltip):
                    self.log_signal.emit(f"📆 span 툴팁(절대): {span_tooltip}")
                    return self.parse_date_from_text(span_tooltip)
            except NoSuchElementException:
                pass

            # ————————————— 3. anchor.text (상대표현 or 간략시간) —————————————
            text = date_anchor.text.strip()
            self.log_signal.emit(f"⏱ anchor.text: {text}")
            return self.parse_date_from_text(text)

        except Exception as e:
            self.log_signal.emit(f"❌ 날짜 추출 오류: {e}")
            return None

    def parse_date_from_text(self, text):
        """
        날짜 문자열을 datetime 객체로 파싱
        지원 형식:
          - "2025년 4월 19일 오후 03:27"
          - "4월 19일 오후 03:27"
          - "7시간 전" 등의 상대적 시간 표현
        """
        
        # 새 패턴: "오전 01:33" 또는 "오후 6:07"
        short_match = re.match(r"(오전|오후)\s*(\d{1,2}):(\d{2})", text)
        if short_match:
            ampm, h, m = short_match.groups()
            h = int(h)
            if ampm == "오후" and h < 12:
                h += 12
            elif ampm == "오전" and h == 12:
                h = 0
            today = datetime.now()
            return today.replace(hour=h, minute=int(m), second=0, microsecond=0)
            
        try:
            if not text or text.strip() == "":
                self.log_signal.emit("❗ 날짜 텍스트가 비어있음")
                return None

            # 상대적 시간 표현 처리 (예: "7시간 전")
            relative_time_match = re.match(r'(\d+)\s*(시간|분|초|일|주|개월|년)\s*전', text)
            if relative_time_match:
                num, unit = relative_time_match.groups()
                num = int(num)
                now = datetime.now()
            
                if unit == '초':
                    return now - timedelta(seconds=num)
                elif unit == '분':
                    return now - timedelta(minutes=num)
                elif unit == '시간':
                    return now - timedelta(hours=num)
                elif unit == '일':
                    return now - timedelta(days=num)
                elif unit == '주':
                    return now - timedelta(weeks=num)
                elif unit == '개월':
                    # 근사값으로 30일로 계산
                    return now - timedelta(days=num*30)
                elif unit == '년':
                    # 근사값으로 365일로 계산
                    return now - timedelta(days=num*365)

            current_year = datetime.now().year

            # 1. 연도 포함 형식 (예: "2025년 4월 19일 오후 03:27")
            match = re.match(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s*(\d{1,2}):(\d{2})", text)
            if match:
                y, m, d, ampm, h, min = match.groups()
            else:
                # 2. 연도 없음 형식 (예: "4월 19일 오후 03:27")
                match = re.match(r"(\d{1,2})월\s*(\d{1,2})일\s*(오전|오후)\s*(\d{1,2}):(\d{2})", text)
                if not match:
                    self.log_signal.emit(f"⚠️ 날짜 형식 인식 실패: {text}")
                    return None
                y = current_year
                m, d, ampm, h, min = match.groups()

            h = int(h)
            if ampm == '오후' and h < 12:
                h += 12
            elif ampm == '오전' and h == 12:
                h = 0

            dt = datetime(int(y), int(m), int(d), h, int(min))
            self.log_signal.emit(f"📆 날짜 파싱 성공: {text} → {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            return dt

        except Exception as e:
            self.log_signal.emit(f"❌ 날짜 파싱 오류: {e}")
            return None

    def run(self):

        self.log_signal.emit("🔁 QThread 크롤링 시작")
        count = 0
        posts_selector = "div.section._activity"

        # 드라이버 유효성 검사 및 복구 로직 추가
        try:
            # 간단한 명령으로 드라이버 유효성 테스트
            self.driver.title
            self.log_signal.emit("✅ 드라이버 연결 상태 양호")
        except Exception as e:
            self.log_signal.emit(f"⚠️ 드라이버 세션이 유효하지 않습니다: {str(e)}")
            self.log_signal.emit("🔄 새 드라이버 세션을 생성하지 않고 현재 창에서 계속합니다...")
            
            # 현재 열려있는 창에서 계속 진행하기 위한 처리
            try:
                # 부모 객체(UI 클래스)에서 새 드라이버 생성 요청
                self.log_signal.emit("🔄 부모 객체에 새 드라이버 생성 요청...")
                
                # 이 부분은 메인 UI 클래스에 새 메서드를 추가해야 합니다
                # 여기서는 emit으로 신호만 보내고, 실제 구현은 아래에서 설명합니다
                return
            except Exception as e:
                self.log_signal.emit(f"❌ 드라이버 복구 실패: {str(e)}")
                self.finished_signal.emit(0)
                return

        try:
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
        except Exception as e:
            self.log_signal.emit(f"❌ 초기 스크롤 실패: {str(e)}")
            return

        try:
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
        except Exception as e:
            self.log_signal.emit(f"❌ 초기 스크롤 실패: {str(e)}")
            return

        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
        except Exception as e:
            self.log_signal.emit(f"❌ 스크롤을 위한 드라이버 명령 실행 오류: {str(e)}")
            return

        while count < self.max_count and not self.stop_flag:
            try:
                posts = self.driver.find_elements(By.CSS_SELECTOR, posts_selector)
                self.log_signal.emit(f"현재 게시물 개수: {len(posts)}")
            except Exception as e:
                self.log_signal.emit(f"❌ 게시물 찾기 오류: {str(e)}")
                break

            # 현재 게시물 수가 부족하면 스크롤하여 추가 로드
            if len(posts) <= count:
                try:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    self.log_signal.emit(f"스크롤 후 새 높이: {new_height}, 이전 높이: {last_height}")
                    
                    if new_height == last_height:
                        self.log_signal.emit("더 이상 게시물이 로드되지 않습니다.")
                        break
                    
                    last_height = new_height
                    continue
                except Exception as e:
                    self.log_signal.emit(f"❌ 스크롤 명령 실행 오류: {str(e)}")
                    break

            # 각 게시물을 순차적으로 처리
            for post in posts[count:]:
                if count >= self.max_count or self.stop_flag:
                    break
                
                try:
                    # 날짜 정보 추출
                    try:
                        post_date = self.extract_post_date(post)
                        if not post_date:
                            self.log_signal.emit("게시물에서 날짜 정보를 찾을 수 없습니다. 해당 게시물을 건너뜁니다.")
                            continue
                    except Exception as e:
                        self.log_signal.emit(f"❌ 날짜 정보 추출 중 오류: {e}")
                        continue

                    if not post_date:
                        self.log_signal.emit("게시물에서 날짜 정보를 찾을 수 없습니다. 해당 게시물을 건너뜁니다.")
                        continue

                    # 날짜 범위 확인
                    if not (self.start_date <= post_date <= self.end_date):
                        self.log_signal.emit(f"게시물 날짜 {post_date}가 선택 범위({self.start_date} ~ {self.end_date}) 밖입니다. 건너뜁니다.")
                        if post_date < self.start_date:
                            self.log_signal.emit("더 오래된 게시물이므로, 크롤링을 종료합니다.")
                            self.stop_flag = True
                        continue

                    # 본문 텍스트 추출
                    try:
                        content_element = post.find_element(By.CSS_SELECTOR, "div.fd_cont div._content")
                        raw_text = content_element.text.strip()
                        self.log_signal.emit(f"게시물 raw_text: {raw_text}")
                    except Exception as e:
                        self.log_signal.emit(f"❌ 본문 텍스트 추출 오류: {str(e)}")
                        raw_text = ""

                    # 이미지 추출 및 다운로드
                    try:
                        images = post.find_elements(By.CSS_SELECTOR, "div.wrap_swipe img")
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
                                    return True
                                except Exception:
                                    return False
                            
                            results = list(executor.map(lambda args: download_image(args[0], args[1]), [(t[0], t[1]) for t in tasks]))
                            image_files = [tasks[i][2] for i, r in enumerate(results) if r]
                    except Exception as e:
                        self.log_signal.emit(f"❌ 이미지 처리 오류: {str(e)}")
                        image_files = []

                    # 게시물 처리: 제목, 도매가, 판매가 등을 변환
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
                    self.log_signal.emit(f"게시물 {count} 크롤링 완료. 날짜: {post_date} / 상품코드: {product_code} / 제목: {title} / 도매가: {ddg_value} / 판매가: {sale_price}")
                    
                except Exception as e:
                    self.log_signal.emit(f"⚠️ 게시물 처리 오류: {str(e)}")
                    continue

            # 더 많은 게시물 로드를 위해 스크롤
            if count < self.max_count and not self.stop_flag:
                try:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    
                    if new_height == last_height:
                        self.log_signal.emit("더 이상 게시물이 로드되지 않습니다.")
                        break
                    
                    last_height = new_height
                except Exception as e:
                    self.log_signal.emit(f"❌ 스크롤 명령 실행 오류: {str(e)}")
                    break

        self.log_signal.emit(f"✅ 크롤링 완료! 총 {count}개 게시물 처리")
        self.finished_signal.emit(count)
    
    def stop(self):
        self.stop_flag = True
        self.log_signal.emit("크롤링 중지 요청이 접수되었습니다.")
