import logging
import time
import os
from datetime import datetime
from PyQt5.QtWidgets import QTextEdit, QProgressBar, QStatusBar, QWidget, QVBoxLayout, QLabel, QProgressBar, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QTextCharFormat, QBrush, QPalette, QLinearGradient

class DetailedProgressWidget(QWidget):
    """상세 진행 상황을 표시하는 위젯"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.total_items = 0
        self.processed_items = 0
        self.success_items = 0
        self.error_items = 0
        self.total_images = 0
        self.processed_images = 0
        self.current_mode = "crawling"  # 기본 모드는 크롤링
        
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 진행 상태 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.set_crawling_style()  # 기본 스타일 설정
        layout.addWidget(self.progress_bar)
        
        # 상세 정보 레이블 (한 줄로 통합)
        self.info_label = QLabel("준비 중...")
        self.info_label.setAlignment(Qt.AlignLeft)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        self.setLayout(layout)
    
    def set_crawling_style(self):
        """크롤링 모드 스타일 설정 (파란색)"""
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f0f0;
                color: #000;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #1e3a8a;  /* 짙은 파란색 */
                border-radius: 5px;
            }
        """)
        self.current_mode = "crawling"
    
    def set_band_posting_style(self):
        """밴드 자동글쓰기 모드 스타일 설정 (녹색)"""
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                background-color: #f0f0f0;
                color: #000;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #22c55e;  /* 녹색 */
                border-radius: 5px;
            }
        """)
        self.current_mode = "band_posting"
        
    def start_progress(self, total_items, mode="crawling"):
        """진행 상황 초기화 및 시작"""
        self.total_items = total_items
        self.processed_items = 0
        self.success_items = 0
        self.error_items = 0
        self.total_images = 0
        self.processed_images = 0
        self.progress_bar.setMaximum(total_items)
        self.progress_bar.setValue(0)
        
        # 모드에 따라 스타일 설정
        if mode == "band_posting":
            self.set_band_posting_style()
        else:
            self.set_crawling_style()
            
        # 정보 레이블 초기화
        self.update_info_label("작업 시작")
        
    def update_progress(self, processed_items, is_success=True, image_count=0, message=""):
        """진행 상황 업데이트"""
        self.processed_items = processed_items
        
        # 성공/실패 카운터 업데이트 방식 변경
        if is_success:
            # 이전 방식: self.success_items += 1
            # 새로운 방식: 현재 항목이 성공이면 성공 카운터만 증가
            self.success_items = processed_items  # 현재까지 처리된 항목 수를 성공 카운터로 설정
        else:
            # 실패한 경우 실패 카운터 증가
            self.error_items += 1
            
        # 이미지 카운터 업데이트
        self.total_images += image_count
        
        # 프로그레스 바 업데이트
        self.progress_bar.setValue(processed_items)
        
        # 정보 레이블 업데이트
        self.update_info_label(message)
        
    def update_info_label(self, message=""):
        """정보 레이블 업데이트 (한 줄로 통합)"""
        if self.total_items > 0:
            percent = (self.processed_items / self.total_items) * 100
            
            # 모드에 따라 다른 텍스트 표시
            if self.current_mode == "band_posting":
                mode_text = "밴드자동글쓰기"
            else:
                mode_text = "크롤링"
                
            # 성공/실패 정보와 게시물 처리 정보를 한 줄로 통합
            info_text = f"성공: {self.success_items} 실패: {self.error_items} 이미지: {self.total_images}개 | 게시물 {self.processed_items}/{self.total_items} 처리완료 ({percent:.1f}%) | {mode_text}"
            if message:
                info_text += f" | {message}"
            self.info_label.setText(info_text)
        else:
            self.info_label.setText("준비 중...")
            
    def reset(self):
        """모든 상태와 카운터를 초기화"""
        self.total_items = 0
        self.processed_items = 0
        self.success_items = 0
        self.error_items = 0
        self.total_images = 0
        self.processed_images = 0
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        self.info_label.setText("준비 중...")            
            
    def finish_progress(self):
        """진행 완료 처리"""
        self.progress_bar.setValue(self.total_items)
        self.update_info_label("작업 완료")
        
    def set_mode(self, mode):
        """모드 설정 (crawling 또는 band_posting)"""
        if mode == "band_posting":
            self.set_band_posting_style()
        else:
            self.set_crawling_style()
        self.update_info_label()

class EnhancedLogger:
    """향상된 로깅 기능을 제공하는 클래스"""
    
    def __init__(self, parent, log_widget, progress_bar=None, status_bar=None):
        self.parent = parent
        self.log_text_widget = log_widget  # 이 부분이 중요! log_widget을 log_text_widget으로 저장
        self.progress_bar = progress_bar
        self.status_bar = status_bar
        
        # 로그 레벨별 색상 설정
        self.log_colors = {
            "DEBUG": QColor(100, 100, 100),  # 회색
            "INFO": QColor(0, 0, 0),         # 검정
            "WARNING": QColor(255, 165, 0),  # 주황
            "ERROR": QColor(255, 0, 0),      # 빨강
            "CRITICAL": QColor(128, 0, 128)  # 보라
        }
        
        # 타이머 및 상태 관련 변수 초기화
        self.start_time = None
        self.last_update_time = 0
        self.update_interval = 1.0  # 상태 업데이트 간격 (초)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_display)
        
    def log(self, message, level="INFO", show_status=False):
        """로그 메시지 출력"""
        # 현재 시간 포맷팅
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        # 로그 레벨에 따른 아이콘 설정
        icon = {
            "DEBUG": "🔍",
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🔥"
        }.get(level, "ℹ️")
        
        # 로그 메시지 포맷팅
        formatted_message = f"[{timestamp}] {icon} {message}"
        
        # UI 로그 위젯에 추가
        self.log_text_widget.append(formatted_message)
        self.log_text_widget.ensureCursorVisible()
        
        # 로깅 모듈에도 기록
        logger = logging.getLogger()
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(message)
        
        # 상태 표시줄에도 표시 (필요한 경우)
        if show_status and self.status_bar:
            self.status_bar.showMessage(message, 5000)  # 5초간 표시
            
        # 콘솔에도 출력
        print(f"[{timestamp}] [{level}] {message}")

    def setup_file_logging(self):
        """파일 로깅 설정"""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        # 파일 핸들러 설정
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', '%Y-%m-%d %H:%M:%S'))
        
        # 루트 로거에 핸들러 추가
        logger = logging.getLogger()
        logger.addHandler(file_handler)
        
        self.log(f"로그 파일이 생성되었습니다: {log_file}", level="INFO")
    
    def start_crawling(self, total_items):
        """크롤링 시작 시 호출"""
        self.start_time = time.time()
        self.total_items = total_items
        self.processed_items = 0
        self.success_count = 0
        self.error_count = 0
        self.image_count = 0
        
        # 프로그레스 바 초기화
        if self.progress_bar:
            self.progress_bar.setValue(0)
            self.progress_bar.setMaximum(total_items)
        
        # 상태 표시 타이머 시작
        self.status_timer.start(1000)  # 1초마다 상태 업데이트
        
        self.log(f"🚀 크롤링 시작: 총 {total_items}개 게시물 처리 예정", level="INFO", show_status=True)
    
    def update_progress(self, current, success=True, image_count=0):
        """진행 상황 업데이트"""
        self.processed_items = current
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        
        self.image_count += image_count
        
        # 프로그레스 바 업데이트
        if self.progress_bar:
            self.progress_bar.setValue(current)
        
        # 상태 표시 업데이트 (너무 자주 업데이트하지 않도록)
        current_time = time.time()
        if current_time - self.last_update_time >= self.update_interval:
            self.update_status_display()
            self.last_update_time = current_time
    
    def update_status_display(self):
        """상태 표시 업데이트"""
        if not self.start_time:
            return
            
        # 경과 시간 계산
        elapsed_time = time.time() - self.start_time
        
        # 남은 시간 예측
        if self.processed_items > 0:
            time_per_item = elapsed_time / self.processed_items
            remaining_items = self.total_items - self.processed_items
            estimated_remaining_time = time_per_item * remaining_items
        else:
            estimated_remaining_time = 0
        
        # 진행률 계산
        progress_percent = (self.processed_items / self.total_items * 100) if self.total_items > 0 else 0
        
        # 상태 메시지 생성
        status_msg = (
            f"진행: {self.processed_items}/{self.total_items} ({progress_percent:.1f}%) | "
            f"성공: {self.success_count} | 실패: {self.error_count} | 이미지: {self.image_count}개 | "
            f"경과: {self.format_time(elapsed_time)} | 예상 남은 시간: {self.format_time(estimated_remaining_time)}"
        )
        
        # 상태 표시줄이 있으면 업데이트
        if self.status_bar:
            self.status_bar.showMessage(status_msg)
        
        # 로그에도 주기적으로 상태 업데이트 (10% 단위로)
        if self.processed_items > 0 and self.processed_items % max(1, self.total_items // 10) == 0:
            self.log(f"📊 {status_msg}", level="INFO")
    
    def finish_crawling(self):
        """크롤링 완료 시 호출"""
        if not self.start_time:
            return
            
        # 타이머 중지
        self.status_timer.stop()
        
        # 총 소요 시간
        total_time = time.time() - self.start_time
        
        # 완료 메시지
        completion_msg = (
            f"✅ 크롤링 완료! 총 {self.processed_items}개 처리 "
            f"(성공: {self.success_count}, 실패: {self.error_count}, 이미지: {self.image_count}개) | "
            f"소요 시간: {self.format_time(total_time)}"
        )
        
        self.log(completion_msg, level="INFO", show_status=True)
        
        # 프로그레스 바 완료 표시
        if self.progress_bar:
            self.progress_bar.setValue(self.total_items)
    
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
