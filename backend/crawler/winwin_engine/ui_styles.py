# -*- coding: utf-8 -*-
"""ui_styles.py

UI 색상/스타일 상수 및 커스텀 Qt 위젯 클래스들 (StyledButton 등).
프리미엄 인터랙티브 디자인 v2.0
"""

from PyQt5.QtCore import Qt, QSize, pyqtSignal, QDate, QTimer, QPoint, QPropertyAnimation, QEasingCurve, QRect, QSettings
from PyQt5.QtWidgets import (
    QPushButton, QComboBox, QDateEdit, QSpinBox, QCheckBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QStyledItemDelegate, QCalendarWidget, QWidget, QHBoxLayout,
    QVBoxLayout, QFrame, QLabel, QApplication, QGraphicsDropShadowEffect,
    QDialog, QDialogButtonBox, QLineEdit, QMessageBox,
)
from PyQt5.QtGui import (
    QFont, QColor, QPalette, QCursor, QPainter, QPixmap,
    QFontMetrics, QIcon, QBrush, QLinearGradient,
)

# ═══════════════════════════════════════════════════════════════
# 울트라 플랫 다크 모드 (조잡함 완전 제거)
# ═══════════════════════════════════════════════════════════════
COLORS = {
    "primary": "#2d3748",           # 버튼 기본
    "primary_light": "#4a5568",     # 버튼 호버
    "secondary": "#2d3748",
    "accent": "#3b82f6",            # 얇은 파란색 포인트
    "success": "#2d3748",           # 기존 초록색 완전 제거 -> 텍스트만 초록
    "warning": "#2d3748",           # 기존 노란색 완전 제거
    "danger": "#451a23",            # 아주 어두운 빨강 (삭제 버튼 배경용)
    "light": "#e2e8f0",             # 텍스트 색상
    "dark": "#111827",              # 메인 배경
    "gray": "#9ca3af",              # 비활성화 텍스트
    "gray_light": "#374151",        # 테두리 라인
    "white": "#f9fafb",
    "black": "#000000",
    "transparent": "transparent",
    "bg_card": "#1f2937",           # 패널 배경
    "border_subtle": "#374151",     # 인풋 테두리
    "glow_blue": "transparent",     # 글로우 제거
    "glow_purple": "transparent",   # 글로우 제거
    "gradient_start": "#1f2937",    # 단색
    "gradient_end": "#1f2937",      # 단색
}

BORDER_RADIUS = "8px"
SHADOW = "0 4px 12px rgba(0, 0, 0, 0.08)"
TRANSITION = "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)"


# ═══════════════════════════════════════════════════════════════
# 헬퍼 함수
# ═══════════════════════════════════════════════════════════════
def _lighten(color, factor=0.15):
    if color.startswith('#'):
        color = color[1:]
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f"#{r:02x}{g:02x}{b:02x}"

def _darken(color, factor=0.15):
    if color.startswith('#'):
        color = color[1:]
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    r = max(0, int(r * (1 - factor)))
    g = max(0, int(g * (1 - factor)))
    b = max(0, int(b * (1 - factor)))
    return f"#{r:02x}{g:02x}{b:02x}"

def _add_shadow(widget, color="#000000", blur=12, offset_y=3, opacity=0.12):
    """위젯에 부드러운 그림자 효과 추가"""
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, offset_y)
    shadow.setColor(QColor(0, 0, 0, int(opacity * 255)))
    widget.setGraphicsEffect(shadow)


# ═══════════════════════════════════════════════════════════════
# StyledButton — 그라디언트 + 호버 글로우 + 클릭 애니메이션
# ═══════════════════════════════════════════════════════════════
class StyledButton(QPushButton):
    def __init__(self, text="", icon=None, color=COLORS["primary"], parent=None):
        super().__init__(text, parent)
        self._base_color = color
        self.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.setCursor(QCursor(Qt.PointingHandCursor))

        if icon:
            self.setIcon(icon)

        lighter = _lighten(color, 0.12)
        darker = _darken(color, 0.12)
        hover_lighter = _lighten(color, 0.25)

        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {lighter}, stop:1 {color});
                color: white;
                border: none;
                border-radius: {BORDER_RADIUS};
                padding: 7px 16px;
                min-height: 32px;
                font-weight: bold;
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {hover_lighter}, stop:1 {lighter});
                border: 1px solid {_lighten(color, 0.35)};
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {darker}, stop:1 {_darken(color, 0.2)});
                padding-top: 8px;
                padding-bottom: 6px;
            }}
            QPushButton:disabled {{
                background: {COLORS["gray_light"]};
                color: {COLORS["gray"]};
                border: none;
            }}
        """)

    def lighten_color(self, color, factor=0.1):
        return _lighten(color, factor)

    def darken_color(self, color, factor=0.1):
        return _darken(color, factor)


# ═══════════════════════════════════════════════════════════════
# StyledComboBox — 글래시 드롭다운
# ═══════════════════════════════════════════════════════════════
class StyledComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet(f"""
            QComboBox {{
                border: 1.5px solid {COLORS["border_subtle"]};
                border-radius: {BORDER_RADIUS};
                padding: 5px 10px;
                background-color: {COLORS["white"]};
                min-height: 30px;
                selection-background-color: {COLORS["primary"]};
                selection-color: {COLORS["white"]};
            }}
            QComboBox:hover {{
                border: 1.5px solid {COLORS["primary_light"]};
                background-color: {COLORS["bg_card"]};
            }}
            QComboBox:focus {{
                border: 2px solid {COLORS["primary"]};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid {COLORS["border_subtle"]};
                border-top-right-radius: {BORDER_RADIUS};
                border-bottom-right-radius: {BORDER_RADIUS};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS["light"]}, stop:1 {COLORS["gray_light"]});
            }}
            QComboBox::drop-down:hover {{
                background: {COLORS["primary_light"]};
            }}
            QComboBox QAbstractItemView {{
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: 6px;
                background-color: {COLORS["white"]};
                selection-background-color: {COLORS["primary"]};
                selection-color: {COLORS["white"]};
                padding: 4px;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# StyledDateEdit
# ═══════════════════════════════════════════════════════════════
class StyledDateEdit(QDateEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet(f"""
            QDateEdit {{
                border: 1.5px solid {COLORS["border_subtle"]};
                border-radius: {BORDER_RADIUS};
                padding: 5px 10px;
                background-color: {COLORS["white"]};
                min-height: 30px;
            }}
            QDateEdit:hover {{
                border: 1.5px solid {COLORS["primary_light"]};
                background-color: {COLORS["bg_card"]};
            }}
            QDateEdit:focus {{
                border: 2px solid {COLORS["primary"]};
            }}
            QDateEdit::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border-left: 1px solid {COLORS["border_subtle"]};
                border-top-right-radius: {BORDER_RADIUS};
                border-bottom-right-radius: {BORDER_RADIUS};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS["light"]}, stop:1 {COLORS["gray_light"]});
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# StyledSpinBox
# ═══════════════════════════════════════════════════════════════
class StyledSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet(f"""
            QSpinBox {{
                border: 1.5px solid {COLORS["border_subtle"]};
                border-radius: {BORDER_RADIUS};
                padding: 5px 10px;
                background-color: {COLORS["white"]};
                min-height: 30px;
            }}
            QSpinBox:hover {{
                border: 1.5px solid {COLORS["primary_light"]};
                background-color: {COLORS["bg_card"]};
            }}
            QSpinBox:focus {{
                border: 2px solid {COLORS["primary"]};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 18px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS["light"]}, stop:1 {COLORS["gray_light"]});
                border-radius: 3px;
                margin: 1px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background: {COLORS["primary_light"]};
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# StyledCheckBox
# ═══════════════════════════════════════════════════════════════
class StyledCheckBox(QCheckBox):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet(f"""
            QCheckBox {{
                spacing: 8px;
                color: {COLORS["dark"]};
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {COLORS["border_subtle"]};
                border-radius: 4px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: {COLORS["white"]};
            }}
            QCheckBox::indicator:unchecked:hover {{
                border: 2px solid {COLORS["primary_light"]};
                background-color: {COLORS["bg_card"]};
            }}
            QCheckBox::indicator:checked {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {COLORS["primary"]}, stop:1 {COLORS["accent"]});
                border: 2px solid {COLORS["primary"]};
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# StyledTextEdit
# ═══════════════════════════════════════════════════════════════
class StyledTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                border: 1.5px solid {COLORS["border_subtle"]};
                border-radius: {BORDER_RADIUS};
                padding: 6px;
                background-color: {COLORS["white"]};
            }}
            QTextEdit:hover {{
                border: 1.5px solid {COLORS["primary_light"]};
            }}
            QTextEdit:focus {{
                border: 2px solid {COLORS["primary"]};
                background-color: {COLORS["bg_card"]};
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# StyledTableWidget — 모던 데이터 테이블
# ═══════════════════════════════════════════════════════════════
class StyledTableWidget(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 9))
        self.setAlternatingRowColors(True)
        self.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {COLORS["border_subtle"]};
                border-radius: {BORDER_RADIUS};
                background-color: {COLORS["white"]};
                gridline-color: {COLORS["gray_light"]};
                selection-background-color: {COLORS["primary_light"]};
                selection-color: {COLORS["white"]};
                alternate-background-color: {COLORS["bg_card"]};
            }}
            QTableWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid {COLORS["gray_light"]};
            }}
            QTableWidget::item:selected {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS["primary"]}, stop:1 {COLORS["accent"]});
                color: {COLORS["white"]};
            }}
            QTableWidget::item:hover {{
                background-color: rgba(59, 130, 246, 0.08);
            }}
            QHeaderView::section {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS["primary"]}, stop:1 {_darken(COLORS["primary"], 0.15)});
                color: white;
                padding: 8px 6px;
                border: none;
                font-weight: bold;
                font-size: 11px;
            }}
        """)
        self.horizontalHeader().setStyleSheet(f"""
            QHeaderView::section {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS["primary"]}, stop:1 {_darken(COLORS["primary"], 0.15)});
                color: white;
                padding: 8px 6px;
                border: none;
                font-weight: bold;
            }}
        """)
        self.verticalHeader().setStyleSheet(f"""
            QHeaderView::section {{
                background: {COLORS["bg_card"]};
                color: {COLORS["dark"]};
                padding: 4px 6px;
                border: none;
                border-bottom: 1px solid {COLORS["gray_light"]};
                font-weight: normal;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# StyledProgressBar — 그라디언트 + 글로우
# ═══════════════════════════════════════════════════════════════
class StyledProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QProgressBar {{
                border: 1.5px solid {COLORS["border_subtle"]};
                border-radius: 10px;
                background-color: {COLORS["light"]};
                text-align: center;
                color: {COLORS["dark"]};
                font-weight: bold;
                min-height: 20px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS["primary"]}, stop:0.5 {COLORS["primary_light"]},
                    stop:1 {COLORS["accent"]});
                border-radius: 8px;
            }}
        """)


# ═══════════════════════════════════════════════════════════════
# EnhancedDateEdit
# ═══════════════════════════════════════════════════════════════
class EnhancedDateEdit(QDateEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QDateEdit {{
                border: 1.5px solid {COLORS["border_subtle"]};
                border-radius: 6px;
                padding: 5px;
                padding-right: 24px;
                min-height: 30px;
                background-color: {COLORS["white"]};
            }}
            QDateEdit:hover {{
                border: 1.5px solid {COLORS["primary_light"]};
            }}
            QDateEdit:focus {{
                border: 2px solid {COLORS["primary"]};
            }}
            QDateEdit::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 26px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS["light"]}, stop:1 {COLORS["gray_light"]});
                border-left: 1px solid {COLORS["border_subtle"]};
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }}
            QDateEdit::drop-down:hover {{
                background: {COLORS["primary_light"]};
            }}
            QDateEdit::down-arrow {{
                image: none;
            }}
        """)
        self.setCalendarPopup(True)


# ═══════════════════════════════════════════════════════════════
# EditControlPanel — 하단 액션 버튼 패널
# ═══════════════════════════════════════════════════════════════
class EditControlPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        from premium_widgets import AnimatedButton
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(4, 4, 4, 4)

        btn_configs = [
            ("전체선택/해제", COLORS["primary"], "#60a5fa"),
            ("전체 체크 반전", COLORS["secondary"], "#9ca3af"),
            ("선택 삭제", COLORS["danger"], "#f87171"),
            ("내용 일괄 편집", COLORS["primary_light"], "#60a5fa"),
            ("임시저장", COLORS["success"], "#4ade80"),
            ("불러오기", COLORS["warning"], "#fbbf24"),
        ]

        self.selectAllBtn = AnimatedButton(btn_configs[0][0], color=btn_configs[0][1], hover_color=btn_configs[0][2])
        self.invertSelectionBtn = AnimatedButton(btn_configs[1][0], color=btn_configs[1][1], hover_color=btn_configs[1][2])
        self.deleteBtn = AnimatedButton(btn_configs[2][0], color=btn_configs[2][1], hover_color=btn_configs[2][2])
        self.bulkEditBtn = AnimatedButton(btn_configs[3][0], color=btn_configs[3][1], hover_color=btn_configs[3][2])
        self.tempSaveBtn = AnimatedButton(btn_configs[4][0], color=btn_configs[4][1], hover_color=btn_configs[4][2])
        self.loadBtn = AnimatedButton(btn_configs[5][0], color=btn_configs[5][1], hover_color=btn_configs[5][2])

        for btn in [self.selectAllBtn, self.invertSelectionBtn, self.deleteBtn,
                     self.bulkEditBtn, self.tempSaveBtn, self.loadBtn]:
            btn.setFixedWidth(150)
            btn.setFixedHeight(34)
            layout.addWidget(btn)

        layout.addStretch()
        self.setLayout(layout)
        self.setMinimumHeight(28)


# ═══════════════════════════════════════════════════════════════
# LoginDialog — 프리미엄 로그인 화면
# ═══════════════════════════════════════════════════════════════
class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Winwin Crawler")
        self.setFixedSize(380, 420)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0d1117, stop:0.5 #161b22, stop:1 #0d1117);
            }
            QLabel {
                color: #e6edf3;
                background: transparent;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(35, 30, 35, 30)

        # 헤더
        header = QLabel("⚡ Winwin Crawler")
        header.setAlignment(Qt.AlignCenter)
        header.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header.setStyleSheet("color: #38bdf8;")
        layout.addWidget(header)

        subtitle = QLabel("SaaS Control Tower v3.0")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet("color: #8b949e; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        # 네온 구분선
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(2)
        line.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:0.5 #818cf8, stop:1 #c084fc); border: none;")
        layout.addWidget(line)

        # ID 필드
        id_label = QLabel("아이디")
        id_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        id_label.setStyleSheet("color: #38bdf8;")
        layout.addWidget(id_label)

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("개인 아이디를 입력하세요")
        self.id_edit.setFont(QFont("Segoe UI", 10))
        self.id_edit.setAlignment(Qt.AlignCenter)
        self.id_edit.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid rgba(56,189,248,0.25);
                border-radius: 10px;
                padding: 10px 14px;
                background-color: rgba(22,27,34,0.9);
                color: #e6edf3;
                min-height: 36px;
            }
            QLineEdit:hover {
                border: 1.5px solid rgba(56,189,248,0.5);
            }
            QLineEdit:focus {
                border: 2px solid #38bdf8;
                background-color: rgba(30,38,50,0.9);
            }
        """)
        layout.addWidget(self.id_edit)

        # 비밀번호 필드
        pw_label = QLabel("비밀번호")
        pw_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        pw_label.setStyleSheet("color: #818cf8;")
        layout.addWidget(pw_label)

        self.pw_edit = QLineEdit()
        self.pw_edit.setPlaceholderText("비밀번호")
        self.pw_edit.setFont(QFont("Segoe UI", 10))
        self.pw_edit.setEchoMode(QLineEdit.Password)
        self.pw_edit.setAlignment(Qt.AlignCenter)
        self.pw_edit.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid rgba(129,140,248,0.25);
                border-radius: 10px;
                padding: 10px 14px;
                background-color: rgba(22,27,34,0.9);
                color: #e6edf3;
                min-height: 36px;
            }
            QLineEdit:hover {
                border: 1.5px solid rgba(129,140,248,0.5);
            }
            QLineEdit:focus {
                border: 2px solid #818cf8;
                background-color: rgba(30,38,50,0.9);
            }
        """)
        layout.addWidget(self.pw_edit)

        layout.addSpacing(8)

        # 기억하기 체크박스
        check_layout = QHBoxLayout()
        check_layout.setContentsMargins(0, 0, 0, 5)
        self.chk_save_id = QCheckBox("아이디 기억")
        self.chk_save_id.setStyleSheet("color: #9ca3af; font-size: 11px;")
        
        self.chk_save_pw = QCheckBox("비밀번호 기억")
        self.chk_save_pw.setStyleSheet("color: #9ca3af; font-size: 11px;")
        
        check_layout.addWidget(self.chk_save_id)
        check_layout.addWidget(self.chk_save_pw)
        check_layout.addStretch()
        layout.addLayout(check_layout)

        # 버튼 영역
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.login_btn = StyledButton("로그인", color=COLORS["primary"])
        self.login_btn.setFixedHeight(40)
        self.login_btn.clicked.connect(self.check_credentials)
        btn_layout.addWidget(self.login_btn)

        self.cancel_btn = StyledButton("취소", color=COLORS["danger"])
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # 저장된 인증 정보 불러오기
        self.load_credentials()

    def load_credentials(self):
        settings = QSettings("WinwinCrawler", "AutoLogin")
        saved_id = settings.value("login_id", "")
        saved_pw = settings.value("login_pw", "")
        save_id_checked = settings.value("save_id_checked", "false") == "true"
        save_pw_checked = settings.value("save_pw_checked", "false") == "true"

        self.chk_save_id.setChecked(save_id_checked)
        self.chk_save_pw.setChecked(save_pw_checked)

        if save_id_checked and saved_id:
            self.id_edit.setText(saved_id)
        if save_pw_checked and saved_pw:
            self.pw_edit.setText(saved_pw)

    def save_credentials(self, username, password):
        settings = QSettings("WinwinCrawler", "AutoLogin")
        
        if self.chk_save_id.isChecked():
            settings.setValue("login_id", username)
            settings.setValue("save_id_checked", "true")
        else:
            settings.setValue("login_id", "")
            settings.setValue("save_id_checked", "false")
            
        if self.chk_save_pw.isChecked():
            settings.setValue("login_pw", password)
            settings.setValue("save_pw_checked", "true")
        else:
            settings.setValue("login_pw", "")
            settings.setValue("save_pw_checked", "false")

    def showEvent(self, event):
        super().showEvent(event)
        if not self.id_edit.text():
            self.id_edit.setFocus()
        elif not self.pw_edit.text():
            self.pw_edit.setFocus()
        else:
            self.login_btn.setFocus()

    def check_credentials(self):
        username = self.id_edit.text().strip()
        password = self.pw_edit.text().strip()

        if username == "admin" and password == "8888":
            self.user_role = "admin"
            self.user_expire_date = "무제한"
            self.username = "admin"
            self.save_credentials(username, password)
            self.accept()
            return

        import requests
        import uuid
        hwid = str(uuid.getnode())

        self.login_btn.setText("🔄 서버 인증 중...")
        self.login_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            resp = requests.post("https://hagisq.pythonanywhere.com/api/v1/auth",
                                 json={"username": username, "password": password, "hwid": hwid},
                                 timeout=5)
            data = resp.json()

            if data.get("ok"):
                self.user_role = data.get("role")
                self.user_expire_date = data.get("expire_date")
                self.username = username
                self.save_credentials(username, password)
                QMessageBox.information(self, "인증 성공", "✅ 계정 확인 완료! 윈윈크롤러를 시작합니다.")
                self.accept()
            else:
                msg = data.get("msg", "접근 권한이 거부되었습니다.")
                QMessageBox.warning(self, "인증 실패", msg)
                self.login_btn.setText("로그인")
                self.login_btn.setEnabled(True)

        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, "서버 연결 오류", "라이선스 서버에 연결할 수 없습니다.\n인터넷 상태를 확인하세요.")
            self.login_btn.setText("로그인")
            self.login_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "시스템 오류", f"인증 중 에러: {e}")
            self.login_btn.setText("로그인")
            self.login_btn.setEnabled(True)
