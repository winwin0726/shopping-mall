import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QCheckBox, QSizePolicy, QCompleter
)
from PyQt5.QtCore import Qt
from ui_styles import StyledButton

class WeishangCrawlTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 입력 컨테이너 (URL, API 등)
        ws_input_layout = QHBoxLayout()
        # 업체 선택 콤보박스 (검색 가능)
        ws_input_layout.addWidget(QLabel("업체 선택:"))
        
        # 메인 윈도우의 속성으로 만듦 (기존 코드 호환성을 위해)
        self.main_window.weishang_vendor_combo = QComboBox()
        self.main_window.weishang_vendor_combo.setEditable(True)
        self.main_window.weishang_vendor_combo.setInsertPolicy(QComboBox.NoInsert)
        self.main_window.weishang_vendor_combo.setMinimumWidth(300)
        
        # vendors.txt 로드
        self.main_window.weishang_vendors = [] # [(name, url), ...]
        # 경로를 winwin60.py 위치 기준 (tabs의 부모 디렉토리)으로 맞춤
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        vendors_path = os.path.join(base_dir, "vendors.txt")
        item_list = []
        if os.path.exists(vendors_path):
            with open(vendors_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split(",", 1)
                        if len(parts) == 2:
                            name = parts[0].strip()
                            url = parts[1].strip()
                            self.main_window.weishang_vendors.append((name, url))
                            self.main_window.weishang_vendor_combo.addItem(name, userData=url)
                            item_list.append(name)
                            
        # 검색 자동완성 (QCompleter) 연결
        completer = QCompleter(item_list, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains) # 부분 일치 검색 활성화
        self.main_window.weishang_vendor_combo.setCompleter(completer)
        
        # 기본값 설정
        if self.main_window.weishang_vendors:
            self.main_window.weishang_vendor_combo.setCurrentIndex(0)
            
        ws_input_layout.addWidget(self.main_window.weishang_vendor_combo)
        
        ws_input_layout.addWidget(QLabel("Gemini API 키:"))
        self.main_window.weishang_api_key = QLineEdit()
        self.main_window.weishang_api_key.setPlaceholderText("비워두면 번역 안함")
        self.main_window.weishang_api_key.setEchoMode(QLineEdit.PasswordEchoOnEdit)
        
        saved_api_key = self.main_window.settings.value("weishang/api_key", "")
        if saved_api_key:
            self.main_window.weishang_api_key.setText(saved_api_key)
        ws_input_layout.addWidget(self.main_window.weishang_api_key)
        
        # 동작 방식 컨테이너
        ws_options_layout = QHBoxLayout()
        self.main_window.weishang_headless_chk = QCheckBox("백그라운드 실행 (숨기기)")
        self.main_window.weishang_headless_chk.setChecked(False) # 처음 로그인QR 위해 False 권장
        self.main_window.weishang_trans_chk = QCheckBox("Gemini 자동번역 사용")
        self.main_window.weishang_trans_chk.setChecked(True)
        
        ws_options_layout.addWidget(self.main_window.weishang_headless_chk)
        ws_options_layout.addWidget(self.main_window.weishang_trans_chk)
        ws_options_layout.addStretch()

        # 버튼 컨테이너
        ws_btn_layout = QHBoxLayout()
        ws_btn_layout.setSpacing(10)
        self.main_window.weishang_crawl_btn = StyledButton("웨이상 가져오기", color="#8b5cf6")
        self.main_window.weishang_crawl_btn.setMinimumHeight(30)
        self.main_window.weishang_crawl_btn.clicked.connect(self.main_window.start_weishang_crawling)
        
        self.main_window.weishang_stop_crawl_btn = StyledButton("중지", color="#ef4444")
        self.main_window.weishang_stop_crawl_btn.setMinimumHeight(30)
        self.main_window.weishang_stop_crawl_btn.clicked.connect(self.main_window.stop_crawling_action)
        
        for btn in [self.main_window.weishang_crawl_btn, self.main_window.weishang_stop_crawl_btn]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
        ws_btn_layout.addWidget(self.main_window.weishang_crawl_btn)
        ws_btn_layout.addWidget(self.main_window.weishang_stop_crawl_btn)
        
        # 합치기
        layout.addLayout(ws_input_layout)
        layout.addLayout(ws_options_layout)
        layout.addLayout(ws_btn_layout)
