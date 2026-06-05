from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel, 
    QLineEdit, QCheckBox, QPushButton, QGroupBox, QFormLayout, QTextEdit,
    QMessageBox, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter  # 추가: QSplitter 임포트
)
from PyQt5.QtCore import Qt, QSettings, QSize
from PyQt5.QtGui import QFont, QIcon, QBrush, QColor
from datetime import datetime

class ProfileManagementDialog(QDialog):
    def __init__(self, parent=None, colors=None, select_mode=False, select_target=None, **kwargs):
        super().__init__(parent)
        # (PATCH14) 로그인 선택 모드 지원
        self.select_mode = bool(select_mode)
        self.select_target = (select_target or "").lower() if select_target else None
        self._selected_credentials = None  # (profile_name, id, pw)

        self.parent = parent
        self.colors = colors or {
            "primary": "#1e3a8a",
            "primary_light": "#2563eb",
            "secondary": "#64748b",
            "accent": "#3b82f6",
            "success": "#22c55e",
            "warning": "#f59e0b",
            "danger": "#ef4444",
            "light": "#f8fafc",
            "dark": "#0f172a",
            "gray": "#94a3b8",
            "gray_light": "#e2e8f0",
            "white": "#ffffff",
            "black": "#000000",
            "transparent": "transparent"
        }
        self.border_radius = "3px"
        self.settings = QSettings("WINWIN", "AutoCrawler")
        
        # 기본 프로필 정보 (카테고리별 아이디/비밀번호)
        self.default_profiles = {
            "1. 남성의류": {"id": "luxcafe@hotmail.co.kr", "pw": "Vksaodhkd80!!!!"},
            "2. 여성의류": {"id": "replwiz@gmail.com", "pw": "love046090"},
            "3. 가방지갑": {"id": "yueyuan3001@gmail.com", "pw": "love046090"},
            "4. 신발": {"id": "2909447201@qq.com", "pw": "vksaodhkd80!"},
            "5. 시계": {"id": "winwatch77@gmail.com", "pw": "vksaodhkd80!"},
            "6. 악세사리": {"id": "hagisq@gmail.com", "pw": "vksaodhkd80!"},
            "7. 국내배송": {"id": "jkcompany0726@gmail.com", "pw": "vksaodhkd80!"},
            "8. 초고퀄": {"id": "winwinbest1@gmail.com", "pw": "love046090"}
        }
        
        # 기본 밴드 프로필 정보
        self.default_band_profiles = {
            "밴드1": {"id": "hagisq@naver.com", "pw": "vksaodhkd80!!!"},
            "밴드2": {"id": "winwinbest1@gmail.com", "pw": "love046090"},
            "밴드3": {"id": "jkcompany0726@gmail.com", "pw": "vksaodhkd80!"}
        }
        
        self.setWindowTitle("프로필 관리")
        self.setFixedSize(700, 750)
        self.initUI()
        
    def initUI(self):
        main_layout = QVBoxLayout()
        
        # 탭 위젯 생성
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {self.colors["gray_light"]};
                border-radius: {self.border_radius};
                background-color: {self.colors["white"]};
            }}
            QTabBar::tab {{
                background-color: {self.colors["gray_light"]};
                color: {self.colors["dark"]};
                border-top-left-radius: {self.border_radius};
                border-top-right-radius: {self.border_radius};
                padding: 8px 16px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {self.colors["primary"]};
                color: {self.colors["white"]};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {self.colors["secondary"]};
                color: {self.colors["white"]};
            }}
        """)
        self.tabs = tabs
        
        # 카카오스토리 프로필 탭
        kakao_tab = QWidget()
        kakao_layout = QVBoxLayout(kakao_tab)
        
        # 카카오스토리 프로필 관리 그룹
        kakao_group = QGroupBox("")
        kakao_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {self.colors["gray_light"]};
                border-radius: {self.border_radius};
                margin-top: 1ex;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {self.colors["primary"]};
            }}
        """)
        
        # 수직 분할 레이아웃 생성 (QSplitter 사용)
        kakao_splitter = QSplitter(Qt.Vertical)
        kakao_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {self.colors["gray_light"]};
                height: 2px;
            }}
            QSplitter::handle:hover {{
                background-color: {self.colors["primary_light"]};
            }}
        """)
        
        # 상단 위젯 (테이블)
        kakao_table_widget = QWidget()
        kakao_table_layout = QVBoxLayout(kakao_table_widget)
        kakao_table_layout.setContentsMargins(0, 0, 0, 0)
        
        # 프로필 테이블
        # 테이블 초기화 전에 이전 연결 해제
        if hasattr(self, 'band_profile_table'):
            try:
                self.band_profile_table.itemChanged.disconnect()
            except:
                pass
        self.profile_table = QTableWidget()
        self.profile_table.setColumnCount(3)
        self.profile_table.setHorizontalHeaderLabels(["프로필명", "아이디", "비밀번호"])
        self.profile_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.profile_table.setMinimumHeight(200)  # 최소 높이 설정
        self.profile_table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {self.colors["gray_light"]};
                border-radius: {self.border_radius};
                background-color: {self.colors["white"]};
            }}
            QTableWidget::item {{
                padding: 4px;
            }}
            QHeaderView::section {{
                background-color: {self.colors["primary"]};
                color: white;
                padding: 4px;
                border: none;
            }}
        """)

        # 테이블 더블클릭 이벤트 연결
        self.profile_table.cellClicked.connect(self._on_table_clicked)
        self.profile_table.cellDoubleClicked.connect(self._on_table_double_clicked)
        
        # 테이블에 프로필 정보 추가
        self._update_profile_table()
        
        kakao_table_layout.addWidget(self.profile_table)
        
        # 하단 위젯 (편집 폼)
        kakao_edit_widget = QWidget()
        kakao_edit_layout = QVBoxLayout(kakao_edit_widget)
        kakao_edit_layout.setContentsMargins(0, 0, 0, 0)
        
        # 선택된 프로필 편집 영역
        edit_group = QGroupBox("선택된 프로필 편집")
        edit_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {self.colors["gray_light"]};
                border-radius: {self.border_radius};
                margin-top: 1ex;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {self.colors["primary"]};
            }}
        """)
        
        edit_form = QFormLayout()
        
        # 프로필명 입력
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("프로필명 입력")
        self.profile_name.setStyleSheet(self._get_line_edit_style())
        
        # 아이디 입력
        self.kakao_id = QLineEdit()
        self.kakao_id.setPlaceholderText("카카오스토리 아이디 입력")
        self.kakao_id.setStyleSheet(self._get_line_edit_style())
        
        # 비밀번호 입력
        pw_layout = QHBoxLayout()
        self.kakao_pw = QLineEdit()
        self.kakao_pw.setPlaceholderText("비밀번호 입력")
        self.kakao_pw.setEchoMode(QLineEdit.Password)
        self.kakao_pw.setStyleSheet(self._get_line_edit_style())
        pw_layout.addWidget(self.kakao_pw)
        
        # 비밀번호 표시 체크박스
        self.show_pw = QCheckBox("비밀번호 보기")
        self.show_pw.setStyleSheet(f"""
            QCheckBox {{
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
                border: 1px solid {self.colors["gray"]};
                border-radius: 2px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors["primary"]};
                border: 1px solid {self.colors["primary"]};
            }}
        """)
        self.show_pw.toggled.connect(self._toggle_password_visibility)
        pw_layout.addWidget(self.show_pw)
        
        edit_form.addRow("프로필명:", self.profile_name)
        edit_form.addRow("아이디:", self.kakao_id)
        edit_form.addRow("비밀번호:", pw_layout)
        
        edit_group.setLayout(edit_form)
        kakao_edit_layout.addWidget(edit_group)
        
        # 버튼 영역
        btn_layout = QHBoxLayout()
        
        # 저장 버튼
        save_btn = QPushButton("저장")
        save_btn.setStyleSheet(self._get_button_style(self.colors["success"]))
        save_btn.clicked.connect(self._save_kakao_profile)
        btn_layout.addWidget(save_btn)
        
        # 삭제 버튼
        delete_btn = QPushButton("삭제")
        delete_btn.setStyleSheet(self._get_button_style(self.colors["danger"]))
        delete_btn.clicked.connect(self._delete_kakao_profile)
        btn_layout.addWidget(delete_btn)
        
        # 초기화 버튼
        reset_btn = QPushButton("기본값으로 초기화")
        reset_btn.setStyleSheet(self._get_button_style(self.colors["warning"]))
        reset_btn.clicked.connect(self._reset_kakao_profiles)
        btn_layout.addWidget(reset_btn)
        
        kakao_edit_layout.addLayout(btn_layout)
        
        # 스플리터에 위젯 추가
        kakao_splitter.addWidget(kakao_table_widget)
        kakao_splitter.addWidget(kakao_edit_widget)
        
        # 스플리터 크기 비율 설정 (60:40)
        kakao_splitter.setSizes([300, 200])
        
        # 그룹 레이아웃에 스플리터 추가
        kakao_form_layout = QVBoxLayout()
        kakao_form_layout.addWidget(kakao_splitter)
        kakao_group.setLayout(kakao_form_layout)
        
        kakao_layout.addWidget(kakao_group)
        
        # 밴드 프로필 탭
        band_tab = QWidget()
        band_layout = QVBoxLayout(band_tab)
        
        # 밴드 프로필 관리 그룹
        band_group = QGroupBox("")
        band_group.setStyleSheet(f"""
            QGroupBox {{
                border: 3px solid {self.colors["gray_light"]};
                border-radius: {self.border_radius};
                margin-top: 1ex;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {self.colors["primary"]};
            }}
        """)
        
        # 밴드 탭용 수직 분할 레이아웃 생성 (QSplitter 사용)
        band_splitter = QSplitter(Qt.Vertical)
        band_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {self.colors["gray_light"]};
                height: 5px;
            }}
            QSplitter::handle:hover {{
                background-color: {self.colors["primary_light"]};
            }}
        """)
        
        # 상단 위젯 (테이블)
        band_table_widget = QWidget()
        band_table_layout = QVBoxLayout(band_table_widget)
        band_table_layout.setContentsMargins(0, 0, 0, 0)
        
        # 밴드 프로필 테이블
        self.band_profile_table = QTableWidget()
        self.band_profile_table.setColumnCount(4)  # 번호, 프로필명, 아이디, 비밀번호
        self.band_profile_table.setHorizontalHeaderLabels(["번호", "프로필명", "아이디", "비밀번호"])
        self.band_profile_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.band_profile_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.band_profile_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.band_profile_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.band_profile_table.setMinimumHeight(200)  # 최소 높이 설정
        self.band_profile_table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {self.colors["gray_light"]};
                border-radius: {self.border_radius};
                background-color: {self.colors["white"]};
            }}
            QTableWidget::item {{
                padding: 4px;
            }}
            QHeaderView::section {{
                background-color: {self.colors["primary"]};
                color: white;
                padding: 4px;
                border: none;
            }}
        """)

        # 테이블 더블클릭 이벤트 연결
        self.band_profile_table.cellDoubleClicked.connect(self._on_band_table_double_clicked)
        
        # 테이블에 밴드 프로필 정보 추가
        self._update_band_profile_table()
        
        band_table_layout.addWidget(self.band_profile_table)
        
        # 하단 위젯 (편집 폼)
        band_edit_widget = QWidget()
        band_edit_layout = QVBoxLayout(band_edit_widget)
        band_edit_layout.setContentsMargins(0, 0, 0, 0)
        
        # 선택된 밴드 프로필 편집 영역
        band_edit_group = QGroupBox("선택된 프로필 편집")
        band_edit_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {self.colors["gray_light"]};
                border-radius: {self.border_radius};
                margin-top: 1ex;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {self.colors["primary"]};
            }}
        """)
        
        band_edit_form = QFormLayout()
        
        # 프로필명 입력
        self.band_profile_name = QLineEdit()
        self.band_profile_name.setPlaceholderText("프로필명 입력")
        self.band_profile_name.setStyleSheet(self._get_line_edit_style())
        
        # 아이디 입력
        self.band_id = QLineEdit()
        self.band_id.setPlaceholderText("밴드 아이디 입력")
        self.band_id.setStyleSheet(self._get_line_edit_style())
        
        # 비밀번호 입력
        band_pw_layout = QHBoxLayout()
        self.band_pw = QLineEdit()
        self.band_pw.setPlaceholderText("비밀번호 입력")
        self.band_pw.setEchoMode(QLineEdit.Password)
        self.band_pw.setStyleSheet(self._get_line_edit_style())
        band_pw_layout.addWidget(self.band_pw)
        
        # 비밀번호 표시 체크박스
        self.band_show_pw = QCheckBox("비밀번호 보기")
        self.band_show_pw.setStyleSheet(f"""
            QCheckBox {{
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
                border: 1px solid {self.colors["gray"]};
                border-radius: 2px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors["primary"]};
                border: 1px solid {self.colors["primary"]};
            }}
        """)
        self.band_show_pw.toggled.connect(self._toggle_band_password_visibility)
        band_pw_layout.addWidget(self.band_show_pw)
        
        band_edit_form.addRow("프로필명:", self.band_profile_name)
        band_edit_form.addRow("아이디:", self.band_id)
        band_edit_form.addRow("비밀번호:", band_pw_layout)
        
        band_edit_group.setLayout(band_edit_form)
        band_edit_layout.addWidget(band_edit_group)
        
        # 버튼 영역
        band_btn_layout = QHBoxLayout()
        
        # 저장 버튼
        band_save_btn = QPushButton("저장")
        band_save_btn.setStyleSheet(self._get_button_style(self.colors["success"]))
        band_save_btn.clicked.connect(self._save_band_profile)
        band_btn_layout.addWidget(band_save_btn)
        
        # 삭제 버튼
        band_delete_btn = QPushButton("삭제")
        band_delete_btn.setStyleSheet(self._get_button_style(self.colors["danger"]))
        band_delete_btn.clicked.connect(self._delete_band_profile)
        band_btn_layout.addWidget(band_delete_btn)
        
        # 초기화 버튼
        band_reset_btn = QPushButton("기본값으로 초기화")
        band_reset_btn.setStyleSheet(self._get_button_style(self.colors["warning"]))
        band_reset_btn.clicked.connect(self._reset_band_profiles)
        band_btn_layout.addWidget(band_reset_btn)
        
        band_edit_layout.addLayout(band_btn_layout)
        
        # 스플리터에 위젯 추가
        band_splitter.addWidget(band_table_widget)
        band_splitter.addWidget(band_edit_widget)
        
        # 스플리터 크기 비율 설정 (60:40)
        band_splitter.setSizes([300, 200])
        
        # 프로필 관리 버튼들 초기화
        band_profile_buttons_layout = self._init_profile_management_buttons()
        
        # 그룹 레이아웃에 스플리터와 버튼 추가
        band_form_layout = QVBoxLayout()
        band_form_layout.addWidget(band_splitter)
        band_form_layout.addLayout(band_profile_buttons_layout)
        band_group.setLayout(band_form_layout)
        
        band_layout.addWidget(band_group)
        
        # 탭에 추가
        tabs.addTab(kakao_tab, "카카오스토리 프로필")
        tabs.addTab(band_tab, "밴드 프로필")
        
        main_layout.addWidget(tabs)
        
        # 닫기 버튼
        close_btn = QPushButton("닫기")
        close_btn.setStyleSheet(self._get_button_style(self.colors["secondary"]))
        close_btn.clicked.connect(self.close)
        
        main_layout.addWidget(close_btn, alignment=Qt.AlignRight)
        
        self.setLayout(main_layout)
        
        # 저장된 설정 불러오기
        self._load_settings()
        
        # 현재 선택된 프로필 정보 표시 (첫 번째 프로필 선택)
        profiles = self._get_saved_profiles()
        if profiles:
            first_profile = list(profiles.keys())[0]
            profile_data = profiles[first_profile]
            self.profile_name.setText(first_profile)
            self.kakao_id.setText(profile_data.get("id", ""))
            self.kakao_pw.setText(profile_data.get("pw", ""))
        
        # 현재 선택된 밴드 프로필 정보 표시 (첫 번째 프로필 선택)
        band_profiles = self._get_saved_band_profiles()
        if band_profiles:
            first_profile = list(band_profiles.keys())[0]
            profile_data = band_profiles[first_profile]
            self.band_profile_name.setText(first_profile)
            self.band_id.setText(profile_data.get("id", ""))
            self.band_pw.setText(profile_data.get("pw", ""))
    
    def _get_line_edit_style(self):
        return f"""
            QLineEdit {{
                border: 1px solid {self.colors["gray_light"]};
                border-radius: {self.border_radius};
                padding: 8px;
                background-color: {self.colors["white"]};
                min-height: 25px;
            }}
            QLineEdit:hover {{
                border: 1px solid {self.colors["primary_light"]};
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors["primary"]};
            }}
        """
        
    def _get_button_style(self, color):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: {self.border_radius};
                padding: 8px 16px;
                min-height: 30px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self._lighten_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self._darken_color(color)};
            }}
        """
        
    def _lighten_color(self, color, factor=0.1):
        """Lighten a hex color by the given factor"""
        if color.startswith('#'):
            color = color[1:]
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _darken_color(self, color, factor=0.1):
        """Darken a hex color by the given factor"""
        if color.startswith('#'):
            color = color[1:]
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"
        
    def _toggle_password_visibility(self, checked):
        if checked:
            self.kakao_pw.setEchoMode(QLineEdit.Normal)
        else:
            self.kakao_pw.setEchoMode(QLineEdit.Password)
            
    def _toggle_band_password_visibility(self, checked):
        if checked:
            self.band_pw.setEchoMode(QLineEdit.Normal)
        else:
            self.band_pw.setEchoMode(QLineEdit.Password)
    
    def _update_profile_table(self):
        """프로필 테이블 업데이트"""
        self.profile_table.setRowCount(0)
        
        # 저장된 프로필 정보 가져오기
        profiles = self._get_saved_profiles()
        
        # 테이블에 추가
        for row, (name, data) in enumerate(profiles.items()):
            self.profile_table.insertRow(row)
            
            # 프로필명
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)  # 편집 불가능하게 설정
            self.profile_table.setItem(row, 0, name_item)
            
            # 아이디
            id_item = QTableWidgetItem(data.get("id", ""))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.profile_table.setItem(row, 1, id_item)
            
            # 비밀번호 (마스킹 처리)
            pw = data.get("pw", "")
            masked_pw = "*" * len(pw) if pw else ""
            pw_item = QTableWidgetItem(masked_pw)
            pw_item.setFlags(pw_item.flags() & ~Qt.ItemIsEditable)
            self.profile_table.setItem(row, 2, pw_item)
            
    def _update_band_profile_table(self):
        """밴드 프로필 테이블 업데이트 - 개선된 버전"""
        self.band_profile_table.setRowCount(0)
        
        # 저장된 밴드 프로필 정보 가져오기
        profiles = self._get_saved_band_profiles()
        
        # 테이블에 추가
        for row, (name, data) in enumerate(profiles.items()):
            self.band_profile_table.insertRow(row)
        
            # 번호 - 가운데 정렬
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
            self.band_profile_table.setItem(row, 0, num_item)
        
            # 프로필명
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.band_profile_table.setItem(row, 1, name_item)
        
            # 아이디
            id_item = QTableWidgetItem(data.get("id", ""))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.band_profile_table.setItem(row, 2, id_item)
        
            # 비밀번호 (마스킹 처리)
            pw = data.get("pw", "")
            masked_pw = "*" * len(pw) if pw else ""
            pw_item = QTableWidgetItem(masked_pw)
            pw_item.setFlags(pw_item.flags() & ~Qt.ItemIsEditable)
            self.band_profile_table.setItem(row, 3, pw_item)
            
            # 행 높이 설정
            self.band_profile_table.setRowHeight(row, 30)
            
            # 짝수/홀수 행 배경색 다르게 설정 (가독성 향상)
            if row % 2 == 0:
                for col in range(4):
                    self.band_profile_table.item(row, col).setBackground(QBrush(QColor("#f8f9fa")))
        
        # 열 너비 조정
        self.band_profile_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 번호
        self.band_profile_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # 프로필명
        self.band_profile_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # 아이디
        self.band_profile_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)  # 비밀번호
        
        # 테이블 선택 모드 설정
        self.band_profile_table.setSelectionBehavior(QTableWidget.SelectRows)  # 행 단위 선택
        self.band_profile_table.setSelectionMode(QTableWidget.SingleSelection)  # 단일 선택
    

    
    def _on_table_clicked(self, row, column):
        """(PATCH14) 1회 클릭: 선택된 프로필을 편집칸(이름/아이디/비번)에 로드"""
        try:
            profile_item = self.profile_table.item(row, 0)
            if not profile_item:
                return
            profile_name = profile_item.text().strip()
            if not profile_name:
                return

            profiles = self._get_saved_profiles() if hasattr(self, "_get_saved_profiles") else {}
            data = profiles.get(profile_name, {}) if isinstance(profiles, dict) else {}

            if hasattr(self, "profile_name"):
                self.profile_name.setText(profile_name)
            if hasattr(self, "kakao_id"):
                self.kakao_id.setText(data.get("id", ""))
            if hasattr(self, "kakao_pw"):
                self.kakao_pw.setText(data.get("pw", ""))
        except Exception:
            return

    def _on_table_double_clicked(self, row, column):
        """테이블 항목 더블클릭 시 호출되는 함수"""
        # (PATCH14) 더블클릭도 먼저 편집칸 로드
        self._on_table_clicked(row, column)

        # (PATCH14) 선택 모드일 때: 로그인 정보 확정 후 창 닫기
        try:
            if getattr(self, "select_mode", False) and (getattr(self, "select_target", None) in (None, "", "kakao", "kakaostory")):
                pnm = self.profile_name.text().strip() if hasattr(self, "profile_name") else ""
                _id = self.kakao_id.text().strip() if hasattr(self, "kakao_id") else ""
                _pw = self.kakao_pw.text().strip() if hasattr(self, "kakao_pw") else ""
                if _id and _pw:
                    self._selected_credentials = (pnm or "메인", _id, _pw)
                    self.accept()
                    return
        except Exception:
            pass

    def _on_band_table_double_clicked(self, row, column):
        """밴드 테이블 항목 더블클릭 시 호출되는 함수"""
        # (PATCH14) 더블클릭도 먼저 편집칸 로드
        try:
            profile_item = self.band_profile_table.item(row, 2)
            if profile_item:
                profile_name = profile_item.text().strip()
                profiles = self._get_saved_band_profiles() if hasattr(self, "_get_saved_band_profiles") else {}
                if isinstance(profiles, dict) and profile_name in profiles:
                    data = profiles[profile_name]
                    if hasattr(self, "band_profile_name"):
                        self.band_profile_name.setText(profile_name)
                    if hasattr(self, "band_id"):
                        self.band_id.setText(data.get("id", ""))
                    if hasattr(self, "band_pw"):
                        self.band_pw.setText(data.get("pw", ""))
        except Exception:
            pass

        # (PATCH14) 선택 모드일 때: 로그인 정보 확정 후 창 닫기
        try:
            if getattr(self, "select_mode", False) and (getattr(self, "select_target", "") == "band"):
                pnm = self.band_profile_name.text().strip() if hasattr(self, "band_profile_name") else ""
                _id = self.band_id.text().strip() if hasattr(self, "band_id") else ""
                _pw = self.band_pw.text().strip() if hasattr(self, "band_pw") else ""
                if _id and _pw:
                    self._selected_credentials = (pnm or "메인", _id, _pw)
                    self.accept()
                    return
        except Exception:
            pass

    def _get_saved_profiles(self):
        """저장된 프로필 정보 가져오기"""
        # 저장된 프로필 정보 가져오기
        saved_profiles = self.settings.value("kakao/profiles", None)
        
        # 만약 한 번도 설정을 건드리지 않아서 아예 값이 없다면 (None) 기본 제공 프로필 복사
        if saved_profiles is None:
            return self.default_profiles.copy()
            
        # 딕셔너리가 아니면 빈 딕셔너리 반환 (오류 방어)
        if not isinstance(saved_profiles, dict):
            return {}
            
        return saved_profiles
        
    def _get_saved_band_profiles(self):
        """저장된 밴드 프로필 정보 가져오기"""
        # 저장된 밴드 프로필 정보 가져오기
        saved_profiles = self.settings.value("band/profiles", None)
        
        # 만약 한 번도 설정을 건드리지 않아서 아예 값이 없다면 (None) 기본 제공 프로필 복사
        if saved_profiles is None:
            return self.default_band_profiles.copy()
            
        # 딕셔너리가 아니면 빈 딕셔너리 반환 (오류 방어)
        if not isinstance(saved_profiles, dict):
            return {}
            
        return saved_profiles
    
    def _save_kakao_profile(self):
        """카카오스토리 프로필 저장"""
        profile_name = self.profile_name.text().strip()
        kakao_id = self.kakao_id.text().strip()
        kakao_pw = self.kakao_pw.text().strip()
        
        if not profile_name or not kakao_id or not kakao_pw:
            QMessageBox.warning(self, "입력 오류", "프로필명, 아이디, 비밀번호를 모두 입력해주세요.")
            return
        
        # 저장된 프로필 정보 가져오기
        profiles = self._get_saved_profiles()
        
        # 프로필 정보 업데이트
        profiles[profile_name] = {
            "id": kakao_id,
            "pw": kakao_pw
        }
        
        # 설정 저장
        self.settings.setValue("kakao/profiles", profiles)
        
        # 마지막 사용 프로필로 설정 (로그인 다이얼로그와 동기화)
        self.settings.setValue("kakao/last_profile", profile_name)
        self.settings.setValue("kakao/last_id", kakao_id)
        self.settings.setValue("kakao/last_pw", kakao_pw)
        
        # 테이블 업데이트
        self._update_profile_table()
        
        QMessageBox.information(self, "저장 완료", f"카카오스토리 프로필 '{profile_name}'이(가) 저장되었습니다.")
    
    def _delete_kakao_profile(self):
        """카카오스토리 프로필 삭제"""
        profile_name = self.profile_name.text().strip()
        
        if not profile_name:
            QMessageBox.warning(self, "선택 오류", "삭제할 프로필을 선택해주세요.")
            return
        
        # 확인 메시지
        reply = QMessageBox.question(
            self, 
            "삭제 확인", 
            f"프로필 '{profile_name}'을(를) 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 저장된 프로필 정보 가져오기
        profiles = self._get_saved_profiles()
        
        # 프로필 삭제
        if profile_name in profiles:
            del profiles[profile_name]
            
            # 설정 저장
            self.settings.setValue("kakao/profiles", profiles)
            
            # 테이블 업데이트
            self._update_profile_table()
            
            QMessageBox.information(self, "삭제 완료", f"카카오스토리 프로필 '{profile_name}'이(가) 삭제되었습니다.")
            
            # 첫 번째 프로필 선택
            if profiles:
                first_profile = list(profiles.keys())[0]
                profile_data = profiles[first_profile]
                self.profile_name.setText(first_profile)
                self.kakao_id.setText(profile_data.get("id", ""))
                self.kakao_pw.setText(profile_data.get("pw", ""))
    
    def _reset_kakao_profiles(self):
        """카카오스토리 프로필 초기화"""
        # 확인 메시지
        reply = QMessageBox.question(
            self, 
            "초기화 확인", 
            "모든 프로필을 기본값으로 초기화하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 설정 초기화
        self.settings.setValue("kakao/profiles", self.default_profiles)
        
        # 테이블 업데이트
        self._update_profile_table()
        
        QMessageBox.information(self, "초기화 완료", "모든 프로필이 기본값으로 초기화되었습니다.")
        
        # 첫 번째 프로필 선택
        if self.default_profiles:
            first_profile = list(self.default_profiles.keys())[0]
            profile_data = self.default_profiles[first_profile]
            self.profile_name.setText(first_profile)
            self.kakao_id.setText(profile_data.get("id", ""))
            self.kakao_pw.setText(profile_data.get("pw", ""))
            
    def _save_band_profile(self):
        """밴드 프로필 저장"""
        profile_name = self.band_profile_name.text().strip()
        band_id = self.band_id.text().strip()
        band_pw = self.band_pw.text().strip()
        
        if not profile_name or not band_id or not band_pw:
            QMessageBox.warning(self, "입력 오류", "프로필명, 아이디, 비밀번호를 모두 입력해주세요.")
            return
        
        # 저장된 밴드 프로필 정보 가져오기
        profiles = self._get_saved_band_profiles()
    
        # 현재 편집 중인 프로필 정보 업데이트
        profiles[profile_name] = {
            "id": band_id,
            "pw": band_pw
        }
    
        # 설정 저장
        self.settings.setValue("band/profiles", profiles)
    
        # 현재 선택된 프로필을 기본 밴드 프로필로 설정
        self.settings.setValue("band/id", band_id)
        self.settings.setValue("band/pw", band_pw)
    
        # 테이블 업데이트
        self._update_band_profile_table()
    
        QMessageBox.information(self, "저장 완료", f"밴드 프로필 '{profile_name}'이(가) 저장되었습니다.")
    
        # 부모 위젯에 로그인 정보 전달 (있는 경우)
        if hasattr(self.parent, 'set_band_credentials'):
            self.parent.set_band_credentials(band_id, band_pw)
            
    def _delete_band_profile(self):
        """밴드 프로필 삭제"""
        profile_name = self.band_profile_name.text().strip()
        
        if not profile_name:
            QMessageBox.warning(self, "선택 오류", "삭제할 프로필을 선택해주세요.")
            return
        
        # 확인 메시지
        reply = QMessageBox.question(
            self, 
            "삭제 확인", 
            f"프로필 '{profile_name}'을(를) 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 저장된 프로필 정보 가져오기
        profiles = self._get_saved_band_profiles()
        
        # 프로필 삭제
        if profile_name in profiles:
            del profiles[profile_name]
            
            # 설정 저장
            self.settings.setValue("band/profiles", profiles)
            
            # 테이블 업데이트
            self._update_band_profile_table()
            
            QMessageBox.information(self, "삭제 완료", f"밴드 프로필 '{profile_name}'이(가) 삭제되었습니다.")
            
            # 첫 번째 프로필 선택
            if profiles:
                first_profile = list(profiles.keys())[0]
                profile_data = profiles[first_profile]
                self.band_profile_name.setText(first_profile)
                self.band_id.setText(profile_data.get("id", ""))
                self.band_pw.setText(profile_data.get("pw", ""))
            else:
                self.band_profile_name.clear()
                self.band_id.clear()
                self.band_pw.clear()
                
    def _reset_band_profiles(self):
        """밴드 프로필 초기화"""
        # 확인 메시지
        reply = QMessageBox.question(
            self, 
            "초기화 확인", 
            "모든 밴드 프로필을 기본값으로 초기화하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 설정 초기화
        self.settings.setValue("band/profiles", self.default_band_profiles)
        
        # 테이블 업데이트
        self._update_band_profile_table()
        
        QMessageBox.information(self, "초기화 완료", "모든 밴드 프로필이 기본값으로 초기화되었습니다.")
        
        # 첫 번째 프로필 선택
        if self.default_band_profiles:
            first_profile = list(self.default_band_profiles.keys())[0]
            profile_data = self.default_band_profiles[first_profile]
            self.band_profile_name.setText(first_profile)
            self.band_id.setText(profile_data.get("id", ""))
            self.band_pw.setText(profile_data.get("pw", ""))
            
    def _backup_band_profile(self):
        """밴드 프로필 백업"""
        if hasattr(self.parent, 'backup_band_profile'):
            success = self.parent.backup_band_profile()
            if success:
                QMessageBox.information(self, "백업 완료", "밴드 프로필이 성공적으로 백업되었습니다.")
            else:
                QMessageBox.warning(self, "백업 실패", "밴드 프로필 백업 중 오류가 발생했습니다.")
        else:
            QMessageBox.warning(self, "기능 미구현", "이 기능은 아직 구현되지 않았습니다.")
            
    def _restore_band_profile(self):
        """밴드 프로필 복원"""
        if hasattr(self.parent, 'restore_band_profile'):
            success = self.parent.restore_band_profile()
            if success:
                QMessageBox.information(self, "복원 완료", "밴드 프로필이 성공적으로 복원되었습니다.")
            else:
                QMessageBox.warning(self, "복원 실패", "밴드 프로필 복원 중 오류가 발생했습니다.")
        else:
            QMessageBox.warning(self, "기능 미구현", "이 기능은 아직 구현되지 않았습니다.")
            
    def _reset_band_profile(self):
        """밴드 프로필 초기화"""
        reply = QMessageBox.question(
            self, 
            "초기화 확인", 
            "밴드 프로필을 완전히 초기화하시겠습니까?\n\n이 작업은 되돌릴 수 없으며, 다시 로그인해야 합니다.",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if hasattr(self.parent, 'reset_band_profile'):
                success = self.parent.reset_band_profile()
                if success:
                    QMessageBox.information(self, "초기화 완료", "밴드 프로필이 초기화되었습니다.")
                else:
                    QMessageBox.warning(self, "초기화 실패", "밴드 프로필 초기화 중 오류가 발생했습니다.")
            else:
                QMessageBox.warning(self, "기능 미구현", "이 기능은 아직 구현되지 않았습니다.")
                
    def _load_settings(self):
        """저장된 설정 불러오기"""
        # 밴드 설정
        band_id = self.settings.value("band/id", "")
        band_pw = self.settings.value("band/pw", "")
        self.band_id.setText(band_id)
        self.band_pw.setText(band_pw)
        
    def get_credentials(self):
        """현재 선택된 프로필의 로그인 정보 반환"""
        profile_name = self.profile_name.text().strip()
        profiles = self._get_saved_profiles()
        
        if profile_name in profiles:
            return profiles[profile_name].get("id", ""), profiles[profile_name].get("pw", "")
        
        return "", ""

    def _init_profile_management_buttons(self):
        """프로필 관리 버튼 초기화"""
        # 프로필 관리 버튼들
        band_profile_buttons_layout = QHBoxLayout()
        
        self.backup_btn = QPushButton("프로필 백업")
        self.backup_btn.setStyleSheet(self._get_button_style(self.colors["success"]))
        self.backup_btn.clicked.connect(self._backup_band_profile)
        
        self.restore_btn = QPushButton("프로필 복원")
        self.restore_btn.setStyleSheet(self._get_button_style(self.colors["warning"]))
        self.restore_btn.clicked.connect(self._restore_band_profile)
        
        self.reset_btn = QPushButton("프로필 초기화")
        self.reset_btn.setStyleSheet(self._get_button_style(self.colors["danger"]))
        self.reset_btn.clicked.connect(self._reset_band_profile)
        
        # 새로운 버튼 추가: 프로필 정리
        self.clean_btn = QPushButton("프로필 정리")
        self.clean_btn.setStyleSheet(self._get_button_style(self.colors["primary"]))
        self.clean_btn.clicked.connect(self._clean_band_profile)
        self.clean_btn.setToolTip("캐시 파일을 삭제하여 프로필 크기를 줄입니다.")
        
       
        band_profile_buttons_layout.addWidget(self.backup_btn)
        band_profile_buttons_layout.addWidget(self.restore_btn)
        band_profile_buttons_layout.addWidget(self.reset_btn)
        band_profile_buttons_layout.addWidget(self.clean_btn)

        
        return band_profile_buttons_layout
        
    def add_usage_stats_tab(self):
        """계정 사용량 통계를 볼 수 있는 탭 추가"""
        usage_tab = QWidget()
        usage_layout = QVBoxLayout(usage_tab)
        
        # 사용량 표시 테이블 추가
        self.usage_table = QTableWidget()
        self.usage_table.setColumnCount(3)
        self.usage_table.setHorizontalHeaderLabels(["계정", "오늘 사용량", "남은 수량"])
        self.usage_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        usage_layout.addWidget(self.usage_table)
        
        # 초기화 버튼 추가
        reset_layout = QHBoxLayout()
        reset_button = QPushButton("사용량 초기화")
        reset_button.clicked.connect(self.reset_account_usage)
        reset_layout.addStretch()
        reset_layout.addWidget(reset_button)
        
        usage_layout.addLayout(reset_layout)
        
        # 탭에 추가
        self.tabs.addTab(usage_tab, "계정 사용량")
        
        # 사용량 데이터 로드
        self.load_usage_stats()
        
    def _add_new_band_profile(self):
        """새 밴드 프로필 추가"""
        # 입력 필드 초기화
        self.band_profile_name.setText("")
        self.band_id.setText("")
        self.band_pw.setText("")
        
        # 프로필명에 기본값 설정 (중복 확인)
        profiles = self._get_saved_band_profiles()
        profile_count = len(profiles)
        
        # 중복되지 않는 프로필명 찾기
        base_name = "새 프로필"
        profile_name = f"{base_name} {profile_count + 1}"
        counter = profile_count + 1
        
        while profile_name in profiles:
            counter += 1
            profile_name = f"{base_name} {counter}"
        
        self.band_profile_name.setText(profile_name)
        
        # 입력 필드에 포커스
        self.band_profile_name.setFocus()
        
        # 사용자에게 안내 메시지 표시
        reply = QMessageBox.information(
            self, 
            "새 프로필 추가", 
            "새 밴드 프로필 정보를 입력한 후 '저장' 버튼을 클릭하세요.\n\n"
            "프로필명: 밴드 계정을 구분할 이름을 입력하세요.\n"
            "아이디: 밴드 로그인에 사용할 이메일을 입력하세요.\n"
            "비밀번호: 밴드 로그인에 사용할 비밀번호를 입력하세요.",
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Ok
        )
        
        # 취소 버튼을 클릭한 경우
        if reply == QMessageBox.Cancel:
            # 입력 필드 초기화
            self.band_profile_name.setText("")
            self.band_id.setText("")
            self.band_pw.setText("")
            
            # 첫 번째 프로필 선택 (있는 경우)
            if profiles:
                first_profile = list(profiles.keys())[0]
                profile_data = profiles[first_profile]
                self.band_profile_name.setText(first_profile)
                self.band_id.setText(profile_data.get("id", ""))
                self.band_pw.setText(profile_data.get("pw", ""))        

    def load_usage_stats(self):
        """계정 사용량 통계 로드 및 표시"""
        # 사용량 데이터 가져오기
        usage_data = self.settings.value("band/account_usage", {})
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # 밴드 프로필 가져오기
        band_profiles = self.settings.value("band/profiles", {})
        
        # 테이블 설정
        self.usage_table.setRowCount(len(band_profiles))
        
        # 테이블 채우기
        for i, (name, profile) in enumerate(band_profiles.items()):
            account_id = profile.get("id", "")
            
            # 계정 이름/아이디
            self.usage_table.setItem(i, 0, QTableWidgetItem(f"{name} ({account_id})"))
            
            # 현재 사용량
            current_usage = usage_data.get(current_date, {}).get(account_id, 0)
            usage_item = QTableWidgetItem(f"{current_usage}/100")
            self.usage_table.setItem(i, 1, usage_item)
            
            # 남은 수량
            remaining = 100 - current_usage
            remaining_item = QTableWidgetItem(f"{remaining}")
            if remaining < 20:
                remaining_item.setForeground(QBrush(QColor("#ef4444")))  # 남은 수량 적으면 빨간색
            self.usage_table.setItem(i, 2, remaining_item)

    def reset_account_usage(self):
        """모든 계정의 사용량 통계 초기화"""
        reply = QMessageBox.question(
            self, 
            "사용량 초기화", 
            "모든 계정의 오늘 사용량을 초기화하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 사용량 데이터 가져와서 초기화
            usage_data = self.settings.value("band/account_usage", {})
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            if current_date in usage_data:
                usage_data[current_date] = {}
                self.settings.setValue("band/account_usage", usage_data)
                self.load_usage_stats()  # 테이블 다시 로드
                QMessageBox.information(self, "초기화 완료", "모든 계정의 사용량이 초기화되었습니다.")        

    def _clean_band_profile(self):
        """밴드 프로필 정리 (캐시 파일 삭제 등)"""
        if hasattr(self.parent, 'clean_profile'):
            success = self.parent.clean_profile()
            if success:
                QMessageBox.information(self, "정리 완료", "밴드 프로필이 성공적으로 정리되었습니다.")
            else:
                QMessageBox.warning(self, "정리 실패", "밴드 프로필 정리 중 오류가 발생했습니다.")
        else:
            QMessageBox.warning(self, "기능 미구현", "이 기능은 아직 구현되지 않았습니다.")

    def _analyze_band_profile(self):
        """밴드 프로필 크기 분석"""
        if hasattr(self.parent, 'analyze_profile'):
            success = self.parent.analyze_profile()
            if success:
                QMessageBox.information(self, "분석 완료", "밴드 프로필 분석이 완료되었습니다.\n자세한 내용은 로그 파일을 확인하세요.")
            else:
                QMessageBox.warning(self, "분석 실패", "밴드 프로필 분석 중 오류가 발생했습니다.")
        else:
            QMessageBox.warning(self, "기능 미구현", "이 기능은 아직 구현되지 않았습니다.")

    def _highlight_selected_rows(self):
        """체크된 행 하이라이트 처리"""
        for row in range(self.band_profile_table.rowCount()):
            checkbox_item = self.band_profile_table.item(row, 0)
            is_checked = checkbox_item.checkState() == Qt.Checked
        
            # 모든 열에 대해 배경색 설정
            for col in range(self.band_profile_table.columnCount()):
                item = self.band_profile_table.item(row, col)
                if item:
                    if is_checked:
                        item.setBackground(QBrush(QColor("#e2e8f0")))  # 연한 회색으로 하이라이트
                    else:
                        item.setBackground(QBrush(QColor("#ffffff")))  # 흰색 배경

    def _on_checkbox_changed(self, item):
        """체크박스 상태 변경 시 호출되는 함수 - 개선된 버전"""
        if item.column() == 0:  # 체크박스 열인 경우에만 처리
            row = item.row()
            is_checked = item.checkState() == Qt.Checked
            
            # 모든 열에 대해 배경색 설정
            for col in range(self.band_profile_table.columnCount()):
                cell_item = self.band_profile_table.item(row, col)
                if cell_item:
                    if is_checked:
                        # 선택된 행 강조 표시
                        cell_item.setBackground(QBrush(QColor("#e7f5ff")))  # 연한 파란색
                        # 글꼴 굵게 설정
                        font = cell_item.font()
                        font.setBold(True)
                        cell_item.setFont(font)
                    else:
                        # 짝수/홀수 행 배경색 다르게 설정
                        bg_color = "#f8f9fa" if row % 2 == 0 else "#ffffff"
                        cell_item.setBackground(QBrush(QColor(bg_color)))
                        # 글꼴 일반으로 설정
                        font = cell_item.font()
                        font.setBold(False)
                        cell_item.setFont(font)
    def get_selected_credentials(self):
        """(PATCH14) winwin58.py 호환: (프로필명, id, pw) 반환"""
        if getattr(self, "_selected_credentials", None):
            return self._selected_credentials
        try:
            if hasattr(self, "get_credentials"):
                creds = self.get_credentials()
                if isinstance(creds, (tuple, list)) and len(creds) == 2:
                    return ("메인", creds[0], creds[1])
                if isinstance(creds, (tuple, list)) and len(creds) == 3:
                    return tuple(creds)
        except Exception:
            pass
        pnm = self.profile_name.text().strip() if hasattr(self, "profile_name") else "메인"
        _id = self.kakao_id.text().strip() if hasattr(self, "kakao_id") else ""
        _pw = self.kakao_pw.text().strip() if hasattr(self, "kakao_pw") else ""
        return (pnm or "메인", _id, _pw)

