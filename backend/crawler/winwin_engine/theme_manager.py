import os
import json
import time
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QDialog, QColorDialog, QApplication, QMessageBox, QLineEdit, QTabWidget,
    QScrollArea, QGridLayout, QFileDialog, QCheckBox, QTimeEdit, QSpinBox,
    QSlider, QFrame, QToolButton, QSizePolicy, QListWidget, QListWidgetItem,
    QGraphicsDropShadowEffect, QStyle, QStyleFactory, QFontDialog, QGroupBox,
    QRadioButton, QToolTip, QSplitter, QStackedWidget
)
from PyQt5.QtCore import (
    Qt, QSettings, pyqtSignal, QTimer, QTime, QSize, QPropertyAnimation,
    QEasingCurve, QRect, QPoint, QThread, QEvent, QObject
)
from PyQt5.QtGui import (
    QColor, QPalette, QFont, QIcon, QPixmap, QPainter, QLinearGradient,
    QRadialGradient, QBrush, QPen, QFontMetrics, QCursor, QImage
)


COLORS = {
    "gray_light": "#E5E7EB",
    "gray_dark": "#374151",
    "blue": "#3B82F6",
    "green": "#10B981",
    "red": "#EF4444",
    "yellow": "#F59E0B",
    "purple": "#8B5CF6",
    "background": "#F9FAFB",
    "text": "#111827",
    "border": "#D1D5DB",
    # 추가할 키들
    "primary": "#3B82F6",  # blue와 같은 값 사용
    "secondary": "#8B5CF6",  # purple과 같은 값 사용
    "success": "#10B981",  # green과 같은 값 사용
    "danger": "#EF4444",  # red와 같은 값 사용
    "warning": "#F59E0B",  # yellow과 같은 값 사용
    "info": "#60A5FA",  # 밝은 파란색
    "light": "#F9FAFB",  # background와 같은 값 사용
    "dark": "#111827"  # text와 같은 값 사용
}

BORDER_RADIUS = "4px"
FONT_SIZE = "14px"
PADDING = "8px"
MARGIN = "10px"
BOX_SHADOW = "0 1px 3px rgba(0, 0, 0, 0.1)"
TRANSITION = "all 0.3s ease"

class ThemeManager(QObject):
    """
    테마 관리자 클래스 - 애플리케이션의 테마를 관리합니다.
    """
    
    # 테마 변경 시그널
    theme_changed = pyqtSignal(str)
    
    # 기본 테마 정의 (확장된 테마 컬렉션)
    DEFAULT_THEMES = {
        "기본 테마": {
            "primary": "#1e3a8a",       # 짙은 네이비
            "primary_light": "#2563eb",  # 약간 밝은 네이비
            "secondary": "#64748b",     # 회색
            "accent": "#3b82f6",        # 파란색 (강조색)
            "success": "#22c55e",       # 초록색
            "warning": "#f59e0b",       # 주황색
            "danger": "#ef4444",        # 빨간색
            "light": "#f8fafc",         # 매우 밝은 회색
            "dark": "#0f172a",          # 짙은 네이비
            "gray": "#94a3b8",          # 중간 회색
            "gray_light": "#e2e8f0",    # 밝은 회색
            "white": "#ffffff",         # 흰색
            "black": "#000000",         # 검정색
            "transparent": "transparent",  # 투명
            "border_radius": "3px",     # 테두리 둥글기
            "shadow": "0 2px 4px rgba(0, 0, 0, 0.1)",  # 그림자
            #"transition": "all 0.2s ease",  # 전환 효과
            "font_family": "Segoe UI",  # 기본 폰트
            "font_size": "9pt",         # 기본 폰트 크기
            "gradient": False,          # 그라데이션 사용 여부
            "gradient_start": "#1e3a8a", # 그라데이션 시작 색상
            "gradient_end": "#2563eb",  # 그라데이션 끝 색상
            "button_style": "flat",     # 버튼 스타일 (flat, rounded, outline)
            "icon_color": "#1e3a8a",    # 아이콘 색상
            "header_font_family": "Segoe UI", # 헤더 폰트
            "header_font_size": "10pt",  # 헤더 폰트 크기
            "header_font_weight": "bold", # 헤더 폰트 굵기
            "animation_speed": "normal", # 애니메이션 속도 (slow, normal, fast)
            "tooltip_style": "light",    # 툴팁 스타일 (light, dark)
            "scrollbar_style": "normal", # 스크롤바 스타일 (normal, thin, hidden)
            "focus_style": "outline",    # 포커스 스타일 (outline, glow, underline)
            "focus_color": "#3b82f6",    # 포커스 색상
        },
        "다크 테마": {
            "primary": "#3b82f6",       # 파란색
            "primary_light": "#60a5fa",  # 밝은 파란색
            "secondary": "#94a3b8",     # 회색
            "accent": "#818cf8",        # 보라색 (강조색)
            "success": "#4ade80",       # 초록색
            "warning": "#fbbf24",       # 주황색
            "danger": "#f87171",        # 빨간색
            "light": "#1e293b",         # 어두운 배경
            "dark": "#0f172a",          # 더 어두운 배경
            "gray": "#64748b",          # 중간 회색
            "gray_light": "#334155",    # 어두운 회색
            "white": "#f8fafc",         # 흰색 (텍스트용)
            "black": "#020617",         # 검정색
            "transparent": "transparent",  # 투명
            "border_radius": "3px",     # 테두리 둥글기
            "shadow": "0 2px 4px rgba(0, 0, 0, 0.3)",  # 그림자
            #"transition": "all 0.2s ease",  # 전환 효과
            "font_family": "Segoe UI",  # 기본 폰트
            "font_size": "9pt",         # 기본 폰트 크기
            "gradient": False,          # 그라데이션 사용 여부
            "gradient_start": "#1e293b", # 그라데이션 시작 색상
            "gradient_end": "#0f172a",  # 그라데이션 끝 색상
            "button_style": "flat",     # 버튼 스타일
            "icon_color": "#3b82f6",    # 아이콘 색상
            "header_font_family": "Segoe UI", # 헤더 폰트
            "header_font_size": "10pt",  # 헤더 폰트 크기
            "header_font_weight": "bold", # 헤더 폰트 굵기
            "animation_speed": "normal", # 애니메이션 속도
            "tooltip_style": "dark",     # 툴팁 스타일
            "scrollbar_style": "thin",   # 스크롤바 스타일
            "focus_style": "glow",       # 포커스 스타일
            "focus_color": "#60a5fa",    # 포커스 색상
        },
        "SNS 테마": {
            "primary": "#0ea5e9",       # 하늘색
            "primary_light": "#38bdf8",  # 밝은 하늘색
            "secondary": "#64748b",     # 회색
            "accent": "#06b6d4",        # 청록색 (강조색)
            "success": "#10b981",       # 초록색
            "warning": "#f59e0b",       # 주황색
            "danger": "#ef4444",        # 빨간색
            "light": "#f0f9ff",         # 매우 밝은 하늘색
            "dark": "#0c4a6e",          # 짙은 하늘색
            "gray": "#94a3b8",          # 중간 회색
            "gray_light": "#e2e8f0",    # 밝은 회색
            "white": "#ffffff",         # 흰색
            "black": "#000000",         # 검정색
            "transparent": "transparent",  # 투명
            "border_radius": "8px",     # 테두리 둥글기 (더 둥글게)
            "shadow": "0 4px 6px rgba(0, 0, 0, 0.1)",  # 그림자
            #"transition": "all 0.3s ease",  # 전환 효과
            "font_family": "Segoe UI",  # 기본 폰트
            "font_size": "9pt",         # 기본 폰트 크기
            "gradient": True,           # 그라데이션 사용 여부
            "gradient_start": "#0ea5e9", # 그라데이션 시작 색상
            "gradient_end": "#06b6d4",  # 그라데이션 끝 색상
            "button_style": "rounded",  # 버튼 스타일
            "icon_color": "#0ea5e9",    # 아이콘 색상
            "header_font_family": "Segoe UI", # 헤더 폰트
            "header_font_size": "11pt",  # 헤더 폰트 크기
            "header_font_weight": "bold", # 헤더 폰트 굵기
            "animation_speed": "fast",   # 애니메이션 속도
            "tooltip_style": "light",    # 툴팁 스타일
            "scrollbar_style": "normal", # 스크롤바 스타일
            "focus_style": "glow",       # 포커스 스타일
            "focus_color": "#38bdf8",    # 포커스 색상
        },
        "모던 테마": {
            "primary": "#8b5cf6",       # 보라색
            "primary_light": "#a78bfa",  # 밝은 보라색
            "secondary": "#64748b",     # 회색
            "accent": "#d946ef",        # 핑크색 (강조색)
            "success": "#22c55e",       # 초록색
            "warning": "#f59e0b",       # 주황색
            "danger": "#ef4444",        # 빨간색
            "light": "#f5f3ff",         # 매우 밝은 보라색
            "dark": "#4c1d95",          # 짙은 보라색
            "gray": "#94a3b8",          # 중간 회색
            "gray_light": "#e2e8f0",    # 밝은 회색
            "white": "#ffffff",         # 흰색
            "black": "#000000",         # 검정색
            "transparent": "transparent",  # 투명
            "border_radius": "6px",     # 테두리 둥글기
            "shadow": "0 10px 15px -3px rgba(0, 0, 0, 0.1)",  # 그림자
            #"transition": "all 0.2s ease",  # 전환 효과
            "font_family": "Segoe UI",  # 기본 폰트
            "font_size": "9pt",         # 기본 폰트 크기
            "gradient": True,           # 그라데이션 사용 여부
            "gradient_start": "#8b5cf6", # 그라데이션 시작 색상
            "gradient_end": "#d946ef",  # 그라데이션 끝 색상
            "button_style": "rounded",  # 버튼 스타일
            "icon_color": "#8b5cf6",    # 아이콘 색상
            "header_font_family": "Segoe UI", # 헤더 폰트
            "header_font_size": "11pt",  # 헤더 폰트 크기
            "header_font_weight": "bold", # 헤더 폰트 굵기
            "animation_speed": "normal", # 애니메이션 속도
            "tooltip_style": "light",    # 툴팁 스타일
            "scrollbar_style": "thin",   # 스크롤바 스타일
            "focus_style": "glow",       # 포커스 스타일
            "focus_color": "#a78bfa",    # 포커스 색상
        },
        "미니멀 테마": {
            "primary": "#000000",       # 검정색
            "primary_light": "#404040",  # 밝은 검정색
            "secondary": "#737373",     # 회색
            "accent": "#525252",        # 어두운 회색 (강조색)
            "success": "#16a34a",       # 초록색
            "warning": "#ca8a04",       # 주황색
            "danger": "#dc2626",        # 빨간색
            "light": "#fafafa",         # 매우 밝은 회색
            "dark": "#171717",          # 짙은 회색
            "gray": "#a3a3a3",          # 중간 회색
            "gray_light": "#e5e5e5",    # 밝은 회색
            "white": "#ffffff",         # 흰색
            "black": "#000000",         # 검정색
            "transparent": "transparent",  # 투명
            "border_radius": "0px",     # 테두리 둥글기 없음
            "shadow": "none",           # 그림자 없음
            #"transition": "all 0.2s ease",  # 전환 효과
            "font_family": "Segoe UI",  # 기본 폰트
            "font_size": "9pt",         # 기본 폰트 크기
            "gradient": False,          # 그라데이션 사용 여부
            "gradient_start": "#000000", # 그라데이션 시작 색상
            "gradient_end": "#404040",  # 그라데이션 끝 색상
            "button_style": "flat",     # 버튼 스타일
            "icon_color": "#000000",    # 아이콘 색상
            "header_font_family": "Segoe UI", # 헤더 폰트
            "header_font_size": "10pt",  # 헤더 폰트 크기
            "header_font_weight": "normal", # 헤더 폰트 굵기
            "animation_speed": "slow",   # 애니메이션 속도
            "tooltip_style": "light",    # 툴팁 스타일
            "scrollbar_style": "hidden", # 스크롤바 스타일
            "focus_style": "underline",  # 포커스 스타일
            "focus_color": "#000000",    # 포커스 색상
        },
        # 추가 테마
        "네온 테마": {
            "primary": "#ff00ff",       # 마젠타
            "primary_light": "#ff66ff",  # 밝은 마젠타
            "secondary": "#00ffff",     # 시안
            "accent": "#ffff00",        # 노랑 (강조색)
            "success": "#00ff00",       # 밝은 초록색
            "warning": "#ffaa00",       # 주황색
            "danger": "#ff0000",        # 빨간색
            "light": "#000000",         # 검정색 배경
            "dark": "#ffffff",          # 흰색 텍스트
            "gray": "#888888",          # 중간 회색
            "gray_light": "#333333",    # 어두운 회색
            "white": "#ffffff",         # 흰색
            "black": "#000000",         # 검정색
            "transparent": "transparent",  # 투명
            "border_radius": "10px",    # 테두리 둥글기
            "shadow": "0 0 10px rgba(255, 0, 255, 0.7)",  # 네온 그림자
            #"transition": "all 0.3s ease",  # 전환 효과
            "font_family": "Consolas",  # 기본 폰트
            "font_size": "9pt",         # 기본 폰트 크기
            "gradient": True,           # 그라데이션 사용 여부
            "gradient_start": "#ff00ff", # 그라데이션 시작 색상
            "gradient_end": "#00ffff",  # 그라데이션 끝 색상
            "button_style": "rounded",  # 버튼 스타일
            "icon_color": "#ff00ff",    # 아이콘 색상
            "header_font_family": "Consolas", # 헤더 폰트
            "header_font_size": "11pt",  # 헤더 폰트 크기
            "header_font_weight": "bold", # 헤더 폰트 굵기
            "animation_speed": "fast",   # 애니메이션 속도
            "tooltip_style": "dark",     # 툴팁 스타일
            "scrollbar_style": "thin",   # 스크롤바 스타일
            "focus_style": "glow",       # 포커스 스타일
            "focus_color": "#ff00ff",    # 포커스 색상
        },
        "자연 테마": {
            "primary": "#2e7d32",       # 초록색
            "primary_light": "#4caf50",  # 밝은 초록색
            "secondary": "#795548",     # 갈색
            "accent": "#8bc34a",        # 라임 (강조색)
            "success": "#43a047",       # 초록색
            "warning": "#ff9800",       # 주황색
            "danger": "#e53935",        # 빨간색
            "light": "#f1f8e9",         # 매우 밝은 초록색
            "dark": "#1b5e20",          # 짙은 초록색
            "gray": "#9e9e9e",          # 중간 회색
            "gray_light": "#e0e0e0",    # 밝은 회색
            "white": "#ffffff",         # 흰색
            "black": "#000000",         # 검정색
            "transparent": "transparent",  # 투명
            "border_radius": "4px",     # 테두리 둥글기
            "shadow": "0 2px 4px rgba(0, 0, 0, 0.1)",  # 그림자
            #"transition": "all 0.2s ease",  # 전환 효과
            "font_family": "Segoe UI",  # 기본 폰트
            "font_size": "9pt",         # 기본 폰트 크기
            "gradient": True,           # 그라데이션 사용 여부
            "gradient_start": "#2e7d32", # 그라데이션 시작 색상
            "gradient_end": "#4caf50",  # 그라데이션 끝 색상
            "button_style": "rounded",  # 버튼 스타일
            "icon_color": "#2e7d32",    # 아이콘 색상
            "header_font_family": "Segoe UI", # 헤더 폰트
            "header_font_size": "10pt",  # 헤더 폰트 크기
            "header_font_weight": "bold", # 헤더 폰트 굵기
            "animation_speed": "normal", # 애니메이션 속도
            "tooltip_style": "light",    # 툴팁 스타일
            "scrollbar_style": "normal", # 스크롤바 스타일
            "focus_style": "outline",    # 포커스 스타일
            "focus_color": "#4caf50",    # 포커스 색상
        },
        "레트로 테마": {
            "primary": "#ff6b6b",       # 빈티지 레드
            "primary_light": "#ff8787",  # 밝은 빈티지 레드
            "secondary": "#ffd166",     # 머스타드 옐로우
            "accent": "#06d6a0",        # 민트 (강조색)
            "success": "#06d6a0",       # 민트
            "warning": "#ffd166",       # 머스타드 옐로우
            "danger": "#ff6b6b",        # 빈티지 레드
            "light": "#fffcf9",         # 크림색 배경
            "dark": "#073b4c",          # 짙은 청록색
            "gray": "#adb5bd",          # 중간 회색
            "gray_light": "#e9ecef",    # 밝은 회색
            "white": "#ffffff",         # 흰색
            "black": "#000000",         # 검정색
            "transparent": "transparent",  # 투명
            "border_radius": "0px",     # 테두리 둥글기 없음
            "shadow": "3px 3px 0px rgba(0, 0, 0, 0.2)",  # 픽셀 그림자
            #"transition": "all 0.1s ease",  # 전환 효과
            "font_family": "Courier New",  # 기본 폰트
            "font_size": "9pt",         # 기본 폰트 크기
            "gradient": False,          # 그라데이션 사용 여부
            "gradient_start": "#ff6b6b", # 그라데이션 시작 색상
            "gradient_end": "#ffd166",  # 그라데이션 끝 색상
            "button_style": "flat",     # 버튼 스타일
            "icon_color": "#ff6b6b",    # 아이콘 색상
            "header_font_family": "Courier New", # 헤더 폰트
            "header_font_size": "10pt",  # 헤더 폰트 크기
            "header_font_weight": "bold", # 헤더 폰트 굵기
            "animation_speed": "slow",   # 애니메이션 속도
            "tooltip_style": "light",    # 툴팁 스타일
            "scrollbar_style": "normal", # 스크롤바 스타일
            "focus_style": "outline",    # 포커스 스타일
            "focus_color": "#ff6b6b",    # 포커스 색상
        },
        "코퍼레이트 테마": {
            "primary": "#0063b1",       # 비즈니스 블루
            "primary_light": "#0078d7",  # 밝은 비즈니스 블루
            "secondary": "#505050",     # 다크 그레이
            "accent": "#107c10",        # 그린 (강조색)
            "success": "#107c10",       # 그린
            "warning": "#ff8c00",       # 주황색
            "danger": "#e81123",        # 빨간색
            "light": "#f5f5f5",         # 매우 밝은 회색
            "dark": "#333333",          # 짙은 회색
            "gray": "#767676",          # 중간 회색
            "gray_light": "#e6e6e6",    # 밝은 회색
            "white": "#ffffff",         # 흰색
            "black": "#000000",         # 검정색
            "transparent": "transparent",  # 투명
            "border_radius": "2px",     # 테두리 둥글기
            "shadow": "0 2px 4px rgba(0, 0, 0, 0.1)",  # 그림자
            #"transition": "all 0.1s ease",  # 전환 효과
            "font_family": "Segoe UI",  # 기본 폰트
            "font_size": "9pt",         # 기본 폰트 크기
            "gradient": False,          # 그라데이션 사용 여부
            "gradient_start": "#0063b1", # 그라데이션 시작 색상
            "gradient_end": "#0078d7",  # 그라데이션 끝 색상
            "button_style": "flat",     # 버튼 스타일
            "icon_color": "#0063b1",    # 아이콘 색상
            "header_font_family": "Segoe UI", # 헤더 폰트
            "header_font_size": "10pt",  # 헤더 폰트 크기
            "header_font_weight": "semibold", # 헤더 폰트 굵기
            "animation_speed": "normal", # 애니메이션 속도
            "tooltip_style": "light",    # 툴팁 스타일
            "scrollbar_style": "normal", # 스크롤바 스타일
            "focus_style": "outline",    # 포커스 스타일
            "focus_color": "#0078d7",    # 포커스 색상
        },
        "소프트 테마": {
            "primary": "#6d5dfc",       # 소프트 퍼플
            "primary_light": "#897dec",  # 밝은 소프트 퍼플
            "secondary": "#8e94f2",     # 라벤더
            "accent": "#ff9fb2",        # 핑크 (강조색)
            "success": "#67e8b1",       # 민트
            "warning": "#ffcf86",       # 파스텔 주황색
            "danger": "#ff8080",        # 파스텔 빨간색
            "light": "#f8f9fc",         # 매우 밝은 회색
            "dark": "#4d4c7d",          # 짙은 퍼플
            "gray": "#b8b8d1",          # 중간 회색
            "gray_light": "#e6e6f2",    # 밝은 회색
            "white": "#ffffff",         # 흰색
            "black": "#000000",         # 검정색
            "transparent": "transparent",  # 투명
            "border_radius": "12px",    # 테두리 둥글기
            "shadow": "0 8px 16px rgba(109, 93, 252, 0.1)",  # 그림자
            #"transition": "all 0.3s ease",  # 전환 효과
            "font_family": "Segoe UI",  # 기본 폰트
            "font_size": "9pt",         # 기본 폰트 크기
            "gradient": True,           # 그라데이션 사용 여부
            "gradient_start": "#6d5dfc", # 그라데이션 시작 색상
            "gradient_end": "#8e94f2",  # 그라데이션 끝 색상
            "button_style": "rounded",  # 버튼 스타일
            "icon_color": "#6d5dfc",    # 아이콘 색상
            "header_font_family": "Segoe UI", # 헤더 폰트
            "header_font_size": "10pt",  # 헤더 폰트 크기
            "header_font_weight": "medium", # 헤더 폰트 굵기
            "animation_speed": "normal", # 애니메이션 속도
            "tooltip_style": "light",    # 툴팁 스타일
            "scrollbar_style": "thin",   # 스크롤바 스타일
            "focus_style": "glow",       # 포커스 스타일
            "focus_color": "#897dec",    # 포커스 색상
        },
    }
    
    def __init__(self, settings_path="themes"):
        """
        테마 관리자 초기화
        
        Args:
            settings_path (str): 테마 설정 파일이 저장될 경로
        """
        super().__init__()
        self.settings_path = settings_path
        self.themes = {}
        self.current_theme_name = "기본 테마"
        self.settings = QSettings("WINWIN", "ThemeManager")
        self.widget_specific_themes = {}  # 특정 위젯에 적용된 테마 저장
        self.auto_theme_timer = None      # 자동 테마 전환 타이머
        
        # 설정 디렉토리 생성
        os.makedirs(settings_path, exist_ok=True)
        
        # 테마 로드
        self.load_themes()
        
        # 마지막으로 사용한 테마 로드
        last_theme = self.settings.value("theme/current", "기본 테마")
        if last_theme in self.themes:
            self.current_theme_name = last_theme
            
        # 자동 테마 전환 설정 로드
        self.load_auto_theme_settings()
    
    def load_themes(self):
        """기본 테마와 저장된 사용자 테마를 로드합니다."""
        # 기본 테마 로드
        self.themes = self.DEFAULT_THEMES.copy()
        
        # 사용자 테마 로드
        theme_file = os.path.join(self.settings_path, "user_themes.json")
        if os.path.exists(theme_file):
            try:
                with open(theme_file, 'r', encoding='utf-8') as f:
                    user_themes = json.load(f)
                    
                # 사용자 테마 병합
                for name, theme in user_themes.items():
                    # 기본 테마에 없는 사용자 테마만 추가
                    if name not in self.DEFAULT_THEMES:
                        self.themes[name] = theme
            except Exception as e:
                print(f"테마 로드 오류: {e}")
                
        # 위젯별 테마 설정 로드
        widget_theme_file = os.path.join(self.settings_path, "widget_themes.json")
        if os.path.exists(widget_theme_file):
            try:
                with open(widget_theme_file, 'r', encoding='utf-8') as f:
                    self.widget_specific_themes = json.load(f)
            except Exception as e:
                print(f"위젯별 테마 로드 오류: {e}")
    
    def save_themes(self):
        """사용자 테마를 파일에 저장합니다."""
        # 기본 테마를 제외한 사용자 테마만 저장
        user_themes = {name: theme for name, theme in self.themes.items() 
                      if name not in self.DEFAULT_THEMES}
        
        theme_file = os.path.join(self.settings_path, "user_themes.json")
        try:
            with open(theme_file, 'w', encoding='utf-8') as f:
                json.dump(user_themes, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"테마 저장 오류: {e}")
            return False
    
    def save_widget_themes(self):
        """위젯별 테마 설정을 파일에 저장합니다."""
        widget_theme_file = os.path.join(self.settings_path, "widget_themes.json")
        try:
            with open(widget_theme_file, 'w', encoding='utf-8') as f:
                json.dump(self.widget_specific_themes, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"위젯별 테마 저장 오류: {e}")
            return False
    
    def get_current_theme(self):
        """현재 선택된 테마를 반환합니다."""
        return self.themes.get(self.current_theme_name, self.DEFAULT_THEMES["기본 테마"])
    
    def set_current_theme(self, theme_name):
        """
        현재 테마를 설정합니다.
        
        Args:
            theme_name (str): 테마 이름
            
        Returns:
            bool: 성공 여부
        """
        if theme_name in self.themes:
            self.current_theme_name = theme_name
            self.settings.setValue("theme/current", theme_name)
            self.theme_changed.emit(theme_name)
            return True
        return False
    
    def get_theme_names(self):
        """사용 가능한 모든 테마 이름을 반환합니다."""
        return list(self.themes.keys())
    
    def add_theme(self, name, theme_data):
        """
        새 테마를 추가합니다.
        
        Args:
            name (str): 테마 이름
            theme_data (dict): 테마 데이터
            
        Returns:
            bool: 성공 여부
        """
        if name in self.DEFAULT_THEMES:
            print(f"기본 테마 '{name}'은 수정할 수 없습니다.")
            return False
            
        self.themes[name] = theme_data
        self.save_themes()
        return True
    
    def remove_theme(self, name):
        """
        테마를 삭제합니다.
        
        Args:
            name (str): 테마 이름
            
        Returns:
            bool: 성공 여부
        """
        if name in self.DEFAULT_THEMES:
            print(f"기본 테마 '{name}'은 삭제할 수 없습니다.")
            return False
            
        if name in self.themes:
            del self.themes[name]
            self.save_themes()
            
            # 현재 테마가 삭제된 경우 기본 테마로 변경
            if self.current_theme_name == name:
                self.current_theme_name = "기본 테마"
                self.settings.setValue("theme/current", "기본 테마")
                self.theme_changed.emit("기본 테마")
                
            return True
        return False
    
    def apply_global_theme(self, app, theme_name=None):
        """
        기존 apply_global_theme 호출과 호환되는 래퍼.
        theme_name이 주어지면 해당 테마로 설정한 뒤 적용합니다.
        """
        if theme_name:
            self.set_current_theme(theme_name)
        self.apply_theme_to_app(app)
        
    def apply_theme_to_app(self, app):
        """
        애플리케이션에 현재 테마를 적용합니다.
        
        Args:
            app (QApplication): 적용할 QApplication 인스턴스
        """
        theme = self.get_current_theme()
        
        # 애플리케이션 팔레트 설정
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(theme["light"]))
        palette.setColor(QPalette.WindowText, QColor(theme["dark"]))
        palette.setColor(QPalette.Base, QColor(theme["white"]))
        palette.setColor(QPalette.AlternateBase, QColor(theme["gray_light"]))
        palette.setColor(QPalette.ToolTipBase, QColor(theme["white"]))
        palette.setColor(QPalette.ToolTipText, QColor(theme["dark"]))
        palette.setColor(QPalette.Text, QColor(theme["dark"]))
        palette.setColor(QPalette.Button, QColor(theme["light"]))
        palette.setColor(QPalette.ButtonText, QColor(theme["dark"]))
        palette.setColor(QPalette.BrightText, QColor(theme["white"]))
        palette.setColor(QPalette.Link, QColor(theme["primary"]))
        palette.setColor(QPalette.Highlight, QColor(theme["primary"]))
        palette.setColor(QPalette.HighlightedText, QColor(theme["white"]))
        
        app.setPalette(palette)
        
        # 애플리케이션 폰트 설정
        font = QFont(theme.get("font_family", "Segoe UI"))
        font.setPointSize(int(theme.get("font_size", "9").replace("pt", "")))
        app.setFont(font)
        
        # 애플리케이션 스타일시트 설정
        app.setStyleSheet(self.generate_app_stylesheet(theme))
    
    def apply_theme_to_widget(self, widget, theme_name=None):
        """
        특정 위젯에 테마를 적용합니다.
        
        Args:
            widget (QWidget): 테마를 적용할 위젯
            theme_name (str, optional): 적용할 테마 이름. None인 경우 현재 테마 사용
            
        Returns:
            bool: 성공 여부
        """
        # 위젯 ID 생성 (객체 주소 사용)
        widget_id = str(id(widget))
        
        # 테마 이름이 지정되지 않은 경우 현재 테마 사용
        if theme_name is None:
            theme_name = self.current_theme_name
        
        # 테마가 존재하는지 확인
        if theme_name not in self.themes:
            return False
        
        # 위젯별 테마 설정 저장
        self.widget_specific_themes[widget_id] = theme_name
        self.save_widget_themes()
        
        # 테마 적용
        theme = self.themes[theme_name]
        widget.setStyleSheet(self.generate_widget_stylesheet(theme))
        
        return True
    
    def reset_widget_theme(self, widget):
        """
        위젯의 테마를 앱 기본 테마로 재설정합니다.
        
        Args:
            widget (QWidget): 테마를 재설정할 위젯
            
        Returns:
            bool: 성공 여부
        """
        widget_id = str(id(widget))
        
        # 위젯별 테마 설정에서 제거
        if widget_id in self.widget_specific_themes:
            del self.widget_specific_themes[widget_id]
            self.save_widget_themes()
        
        # 앱 기본 테마 적용
        theme = self.get_current_theme()
        widget.setStyleSheet(self.generate_widget_stylesheet(theme))
        
        return True
    
    def get_widget_theme(self, widget):
        """
        위젯에 적용된 테마를 반환합니다.
        
        Args:
            widget (QWidget): 테마를 확인할 위젯
            
        Returns:
            dict: 테마 데이터
        """
        widget_id = str(id(widget))
        
        # 위젯별 테마가 설정되어 있는 경우
        if widget_id in self.widget_specific_themes:
            theme_name = self.widget_specific_themes[widget_id]
            return self.themes.get(theme_name, self.get_current_theme())
        
        # 기본 테마 반환
        return self.get_current_theme()
    
    def generate_app_stylesheet(self, theme):
        """
        테마에 맞는 애플리케이션 스타일시트를 생성합니다.
        
        Args:
            theme (dict): 테마 데이터
            
        Returns:
            str: 스타일시트 문자열
        """
        # 버튼 스타일 설정
        button_style = ""
        if theme.get("button_style") == "rounded":
            button_style = f"""
                border-radius: {theme["border_radius"]};
                padding: 6px 12px;
            """
        elif theme.get("button_style") == "outline":
            button_style = f"""
                border: 1px solid {theme["primary"]};
                border-radius: {theme["border_radius"]};
                padding: 6px 12px;
                background-color: transparent;
            """
        else:  # flat
            button_style = f"""
                border: none;
                border-radius: {theme["border_radius"]};
                padding: 6px 12px;
            """
        
        # 그라데이션 설정
        gradient_style = ""
        if theme.get("gradient", False):
            gradient_style = f"""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                           stop:0 {theme["gradient_start"]}, 
                                           stop:1 {theme["gradient_end"]});
            """
        
        # 포커스 스타일 설정
        focus_style = ""
        if theme.get("focus_style") == "glow":
            focus_style = f"""
                border: 1px solid {theme["focus_color"]};
                /* box-shadow는 Qt 스타일시트에서 지원되지 않으므로 제거 */
            """
        elif theme.get("focus_style") == "underline":
            focus_style = f"""
                border-bottom: 2px solid {theme["focus_color"]};
            """
        else:  # outline
            focus_style = f"""
                border: 1px solid {theme["focus_color"]};
            """
        
        # 스크롤바 스타일 설정
        scrollbar_style = ""
        if theme.get("scrollbar_style") == "thin":
            scrollbar_style = """
                width: 6px;
                height: 6px;
            """
        elif theme.get("scrollbar_style") == "hidden":
            scrollbar_style = """
                width: 0px;
                height: 0px;
            """
        else:  # normal
            scrollbar_style = """
                width: 10px;
                height: 10px;
            """
        
        # 애니메이션 속도 설정
        animation_speed = "0.2s"
        if theme.get("animation_speed") == "slow":
            animation_speed = "0.4s"
        elif theme.get("animation_speed") == "fast":
            animation_speed = "0.1s"

        return f"""
            QWidget {{
                background-color: {theme["light"]};
                color: {theme["dark"]};
                font-family: {theme.get("font_family", "Segoe UI")};
                font-size: {theme.get("font_size", "9pt")};
            }}
            
            QPushButton {{
                background-color: {theme["primary"]};
                color: {theme["white"]};
                {button_style}
                min-height: 30px;
                {gradient_style if theme.get("gradient", False) and theme.get("button_style") != "outline" else ""}
            }}
            
            QPushButton:hover {{
                background-color: {theme["primary_light"]};
                {gradient_style if theme.get("gradient", False) and theme.get("button_style") != "outline" else ""}
            }}
            
            QPushButton:pressed {{
                background-color: {self._darken_color(theme["primary"])};
            }}
            
            QPushButton:disabled {{
                background-color: {theme["gray_light"]};
                color: {theme["gray"]};
            }}
            
            QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit {{
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
                padding: 4px 8px;
                background-color: {theme["white"]};
                selection-background-color: {theme["primary"]};
                selection-color: {theme["white"]};
            }}
            
            QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QDateEdit:hover, QTimeEdit:hover, QDateTimeEdit:hover {{
                border: 1px solid {theme["primary_light"]};
            }}
            
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {{
                {focus_style}
            }}
            
            QComboBox {{
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
                padding: 4px 8px;
                background-color: {theme["white"]};
                min-height: 30px;
                selection-background-color: {theme["primary"]};
                selection-color: {theme["white"]};
            }}
            
            QComboBox:hover {{
                border: 1px solid {theme["primary_light"]};
            }}
            
            QComboBox:focus {{
                {focus_style}
            }}
            
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left-width: 0px;
                border-top-right-radius: {theme["border_radius"]};
                border-bottom-right-radius: {theme["border_radius"]};
            }}
            
            QComboBox QAbstractItemView {{
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
                background-color: {theme["white"]};
                selection-background-color: {theme["primary"]};
                selection-color: {theme["white"]};
            }}
            
            QTableView, QListView, QTreeView {{
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
                background-color: {theme["white"]};
                alternate-background-color: {theme["gray_light"]};
                selection-background-color: {theme["primary"]};
                selection-color: {theme["white"]};
            }}
            
            QHeaderView::section {{
                background-color: {theme["primary"]};
                color: {theme["white"]};
                padding: 4px;
                border: none;
                {gradient_style if theme.get("gradient", False) else ""}
            }}
            
            QTabWidget::pane {{
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
                background-color: {theme["white"]};
            }}
            
            QTabBar::tab {{
                background-color: {theme["gray_light"]};
                color: {theme["dark"]};
                border-top-left-radius: {theme["border_radius"]};
                border-top-right-radius: {theme["border_radius"]};
                padding: 6px 12px;
                margin-right: 2px;
            }}
            
            QTabBar::tab:selected {{
                background-color: {theme["primary"]};
                color: {theme["white"]};
                {gradient_style if theme.get("gradient", False) else ""}
            }}
            
            QTabBar::tab:hover:!selected {{
                background-color: {theme["secondary"]};
                color: {theme["white"]};
            }}
            
            QGroupBox {{
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
                margin-top: 1ex;
                font-weight: bold;
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {theme["primary"]};
                font-family: {theme.get("header_font_family", theme.get("font_family", "Segoe UI"))};
                font-size: {theme.get("header_font_size", "10pt")};
                font-weight: {theme.get("header_font_weight", "bold")};
            }}
            
            QProgressBar {{
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
                background-color: {theme["white"]};
                text-align: center;
                color: {theme["dark"]};
            }}
            
            QProgressBar::chunk {{
                background-color: {theme["primary"]};
                border-radius: {theme["border_radius"]};
                {gradient_style if theme.get("gradient", False) else ""}
            }}
            
            QCheckBox {{
                spacing: 5px;
            }}
            
            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
                border: 1px solid {theme["gray"]};
                border-radius: 2px;
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {theme["primary"]};
                border: 1px solid {theme["primary"]};
                {gradient_style if theme.get("gradient", False) else ""}
            }}
            
            QRadioButton {{
                spacing: 5px;
            }}
            
            QRadioButton::indicator {{
                width: 15px;
                height: 15px;
                border: 1px solid {theme["gray"]};
                border-radius: 7px;
            }}
            
            QRadioButton::indicator:checked {{
                background-color: {theme["primary"]};
                border: 1px solid {theme["primary"]};
                {gradient_style if theme.get("gradient", False) else ""}
            }}
            
            QScrollBar:vertical {{
                border: none;
                background: {theme["gray_light"]};
                {scrollbar_style}
                margin: 0px;
            }}
            
            QScrollBar::handle:vertical {{
                background: {theme["gray"]};
                min-height: 20px;
                border-radius: {int(scrollbar_style.split("width:")[1].split("px")[0].strip()) // 2}px;
            }}
            
            QScrollBar:horizontal {{
                border: none;
                background: {theme["gray_light"]};
                {scrollbar_style}
                margin: 0px;
            }}
            
            QScrollBar::handle:horizontal {{
                background: {theme["gray"]};
                min-width: 20px;
                border-radius: {int(scrollbar_style.split("height:")[1].split("px")[0].strip()) // 2}px;
            }}
            
            QMenu {{
                background-color: {theme["white"]};
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
            }}
            
            QMenu::item {{
                padding: 5px 20px 5px 20px;
            }}
            
            QMenu::item:selected {{
                background-color: {theme["primary"]};
                color: {theme["white"]};
                {gradient_style if theme.get("gradient", False) else ""}
            }}
            
            QMenuBar {{
                background-color: {theme["light"]};
                color: {theme["dark"]};
            }}
            
            QMenuBar::item:selected {{
                background-color: {theme["primary"]};
                color: {theme["white"]};
                {gradient_style if theme.get("gradient", False) else ""}
            }}
            
            QToolTip {{
                background-color: {theme["white"] if theme.get("tooltip_style") == "light" else theme["dark"]};
                color: {theme["dark"] if theme.get("tooltip_style") == "light" else theme["white"]};
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
                padding: 2px;
            }}
            
            QLabel[heading="true"] {{
                font-family: {theme.get("header_font_family", theme.get("font_family", "Segoe UI"))};
                font-size: {theme.get("header_font_size", "10pt")};
                font-weight: {theme.get("header_font_weight", "bold")};
                color: {theme["primary"]};
            }}
            
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: {theme["border_radius"]};
                padding: 3px;
            }}
            
            QToolButton:hover {{
                background-color: {theme["gray_light"]};
            }}
            
            QToolButton:pressed {{
                background-color: {theme["gray"]};
            }}
            
            QSlider::groove:horizontal {{
                border: 1px solid {theme["gray_light"]};
                height: 4px;
                background: {theme["gray_light"]};
                margin: 0px;
                border-radius: 2px;
            }}
            
            QSlider::handle:horizontal {{
                background: {theme["primary"]};
                border: none;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            
            QSlider::groove:vertical {{
                border: 1px solid {theme["gray_light"]};
                width: 4px;
                background: {theme["gray_light"]};
                margin: 0px;
                border-radius: 2px;
            }}
            
            QSlider::handle:vertical {{
                background: {theme["primary"]};
                border: none;
                width: 16px;
                height: 16px;
                margin: 0 -6px;
                border-radius: 8px;
            }}
        """
    
    def generate_widget_stylesheet(self, theme):
        """
        특정 위젯에 적용할 스타일시트를 생성합니다.
        
        Args:
            theme (dict): 테마 데이터
            
        Returns:
            str: 스타일시트 문자열
        """
        # 기본 스타일시트 생성
        return f"""
            QWidget {{
                background-color: {theme["light"]};
                color: {theme["dark"]};
                font-family: {theme.get("font_family", "Segoe UI")};
                font-size: {theme.get("font_size", "9pt")};
            }}
            
            QPushButton {{
                background-color: {theme["primary"]};
                color: {theme["white"]};
                border: none;
                border-radius: {theme["border_radius"]};
                padding: 6px 12px;
                min-height: 30px;
            }}
            
            QPushButton:hover {{
                background-color: {theme["primary_light"]};
            }}
            
            QPushButton:pressed {{
                background-color: {self._darken_color(theme["primary"])};
            }}
            
            QLineEdit, QTextEdit, QPlainTextEdit {{
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
                padding: 4px 8px;
                background-color: {theme["white"]};
                selection-background-color: {theme["primary"]};
                selection-color: {theme["white"]};
            }}
            
            QComboBox {{
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
                padding: 4px 8px;
                background-color: {theme["white"]};
                min-height: 30px;
            }}
            
            QLabel {{
                color: {theme["dark"]};
            }}
            
            QLabel[heading="true"] {{
                font-family: {theme.get("header_font_family", theme.get("font_family", "Segoe UI"))};
                font-size: {theme.get("header_font_size", "10pt")};
                font-weight: {theme.get("header_font_weight", "bold")};
                color: {theme["primary"]};
            }}
            
            QGroupBox {{
                border: 1px solid {theme["gray_light"]};
                border-radius: {theme["border_radius"]};
                margin-top: 1ex;
                font-weight: bold;
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {theme["primary"]};
            }}
        """
    
    def _lighten_color(self, color, factor=0.1):
        """색상을 밝게 만듭니다."""
        if color.startswith('#'):
            color = color[1:]
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _darken_color(self, color, factor=0.1):
        """색상을 어둡게 만듭니다."""
        if color.startswith('#'):
            color = color[1:]
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        r = max(0, int(r * (1 - factor)))
        g = max(0, int(g * (1 - factor)))
        b = max(0, int(b * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def export_theme(self, theme_name, file_path):
        """
        테마를 파일로 내보냅니다.
        
        Args:
            theme_name (str): 내보낼 테마 이름
            file_path (str): 저장할 파일 경로
            
        Returns:
            bool: 성공 여부
        """
        if theme_name not in self.themes:
            return False
        
        try:
            theme_data = {theme_name: self.themes[theme_name]}
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(theme_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"테마 내보내기 오류: {e}")
            return False
    
    def import_theme(self, file_path):
        """
        파일에서 테마를 가져옵니다.
        
        Args:
            file_path (str): 가져올 파일 경로
            
        Returns:
            bool: 성공 여부
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_themes = json.load(f)
            
            # 가져온 테마 추가
            for name, theme in imported_themes.items():
                if name in self.DEFAULT_THEMES:
                    # 기본 테마와 이름이 같은 경우 이름 변경
                    name = f"{name} (가져옴)"
                self.themes[name] = theme
            
            self.save_themes()
            return True
        except Exception as e:
            print(f"테마 가져오기 오류: {e}")
            return False
    
    def search_themes(self, keyword):
        """
        키워드로 테마를 검색합니다.
        
        Args:
            keyword (str): 검색 키워드
            
        Returns:
            list: 검색된 테마 이름 목록
        """
        if not keyword:
            return self.get_theme_names()
        
        keyword = keyword.lower()
        return [name for name in self.themes.keys() 
                if keyword in name.lower()]
    
    def load_auto_theme_settings(self):
        """자동 테마 전환 설정을 로드합니다."""
        enabled = self.settings.value("theme/auto_switch/enabled", False, type=bool)
        day_theme = self.settings.value("theme/auto_switch/day_theme", "기본 테마")
        night_theme = self.settings.value("theme/auto_switch/night_theme", "다크 테마")
        day_start = self.settings.value("theme/auto_switch/day_start", "08:00")
        night_start = self.settings.value("theme/auto_switch/night_start", "20:00")
        
        if enabled:
            self.enable_auto_theme_switch(day_theme, night_theme, day_start, night_start)
    
    def save_auto_theme_settings(self, enabled, day_theme, night_theme, day_start, night_start):
        """자동 테마 전환 설정을 저장합니다."""
        self.settings.setValue("theme/auto_switch/enabled", enabled)
        self.settings.setValue("theme/auto_switch/day_theme", day_theme)
        self.settings.setValue("theme/auto_switch/night_theme", night_theme)
        self.settings.setValue("theme/auto_switch/day_start", day_start)
        self.settings.setValue("theme/auto_switch/night_start", night_start)
    
    def enable_auto_theme_switch(self, day_theme, night_theme, day_start="08:00", night_start="20:00"):
        """
        시간에 따른 자동 테마 전환을 활성화합니다.
        
        Args:
            day_theme (str): 주간 테마 이름
            night_theme (str): 야간 테마 이름
            day_start (str): 주간 시작 시간 (HH:MM 형식)
            night_start (str): 야간 시작 시간 (HH:MM 형식)
            
        Returns:
            bool: 성공 여부
        """
        # 테마가 존재하는지 확인
        if day_theme not in self.themes or night_theme not in self.themes:
            return False
        
        # 기존 타이머가 있으면 중지
        if self.auto_theme_timer:
            self.auto_theme_timer.stop()
        
        # 설정 저장
        self.save_auto_theme_settings(True, day_theme, night_theme, day_start, night_start)
        
        # 타이머 생성 및 시작
        self.auto_theme_timer = QTimer()
        self.auto_theme_timer.timeout.connect(
            lambda: self._check_auto_theme_switch(day_theme, night_theme, day_start, night_start)
        )
        self.auto_theme_timer.start(60000)  # 1분마다 확인
        
        # 초기 테마 설정
        self._check_auto_theme_switch(day_theme, night_theme, day_start, night_start)
        
        return True
    
    def disable_auto_theme_switch(self):
        """자동 테마 전환을 비활성화합니다."""
        if self.auto_theme_timer:
            self.auto_theme_timer.stop()
            self.auto_theme_timer = None
        
        # 설정 저장
        self.settings.setValue("theme/auto_switch/enabled", False)
    
    def _check_auto_theme_switch(self, day_theme, night_theme, day_start, night_start):
        """현재 시간에 따라 테마를 전환합니다."""
        current_time = QTime.currentTime()
        day_time = QTime.fromString(day_start, "HH:mm")
        night_time = QTime.fromString(night_start, "HH:mm")
        
        # 현재 시간이 주간 시작과 야간 시작 사이인 경우 주간 테마 적용
        if (day_time <= current_time and current_time < night_time):
            if self.current_theme_name != day_theme:
                self.set_current_theme(day_theme)
        else:
            if self.current_theme_name != night_theme:
                self.set_current_theme(night_theme)


class ThemeEditorDialog(QDialog):
    """테마 편집 다이얼로그"""
    
    theme_updated = pyqtSignal(str, dict)
    
    def __init__(self, theme_manager, theme_name=None, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.theme_name = theme_name
        self.edited_theme = {}
        
        if theme_name:
            self.setWindowTitle(f"테마 편집 - {theme_name}")
            self.edited_theme = theme_manager.themes.get(theme_name, {}).copy()
        else:
            self.setWindowTitle("새 테마 만들기")
            self.edited_theme = theme_manager.themes.get("기본 테마", {}).copy()
        
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self.initUI()
    
    def initUI(self):
        main_layout = QVBoxLayout(self)
        
        # 탭 위젯 생성
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # 기본 설정 탭
        basic_tab = QWidget()
        tab_widget.addTab(basic_tab, "기본 설정")
        
        # 고급 설정 탭
        advanced_tab = QWidget()
        tab_widget.addTab(advanced_tab, "고급 설정")
        
        # 미리보기 탭
        preview_tab = QWidget()
        tab_widget.addTab(preview_tab, "미리보기")
        
        # 기본 설정 탭 UI
        self.setup_basic_tab(basic_tab)
        
        # 고급 설정 탭 UI
        self.setup_advanced_tab(advanced_tab)
        
        # 미리보기 탭 UI
        self.setup_preview_tab(preview_tab)
        
        # 버튼 영역
        button_layout = QHBoxLayout()
        
        # 저장 버튼
        save_btn = QPushButton("저장")
        save_btn.clicked.connect(self.save_theme)
        button_layout.addWidget(save_btn)
        
        # 취소 버튼
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        main_layout.addLayout(button_layout)
    
    def setup_basic_tab(self, tab):
        layout = QVBoxLayout(tab)
        
        # 스크롤 영역 생성
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(scroll)
        
        # 스크롤 내용 위젯
        content = QWidget()
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        
        # 테마 이름 입력
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("테마 이름:"))
        self.name_edit = QLineEdit(self.theme_name if self.theme_name else "")
        if self.theme_name in ThemeManager.DEFAULT_THEMES:
            self.name_edit.setReadOnly(True)
            self.name_edit.setPlaceholderText("기본 테마는 이름을 변경할 수 없습니다")
        name_layout.addWidget(self.name_edit)
        content_layout.addLayout(name_layout)
        
        # 색상 편집 영역
        color_group = QGroupBox("색상 설정")
        color_layout = QGridLayout(color_group)
        
        # 주요 색상들
        self.color_buttons = {}
        color_keys = [
            "primary", "primary_light", "secondary", "accent", 
            "success", "warning", "danger", "light", "dark",
            "gray", "gray_light", "white", "black"
        ]
        
        for i, color_key in enumerate(color_keys):
            row = i // 2
            col = i % 2 * 2
            
            color_layout.addWidget(QLabel(f"{color_key}:"), row, col)
            
            color_value = self.edited_theme.get(color_key, "#000000")
            color_btn = QPushButton()
            color_btn.setFixedSize(30, 20)
            color_btn.setStyleSheet(f"background-color: {color_value}; border: 1px solid #cccccc;")
            color_btn.clicked.connect(lambda checked, k=color_key: self.select_color(k))
            
            color_edit = QLineEdit(color_value)
            color_edit.textChanged.connect(lambda text, k=color_key, btn=color_btn: self.update_color(k, text, btn))
            
            color_layout.addWidget(color_btn, row, col + 1)
            color_layout.addWidget(color_edit, row, col + 1)
            
            self.color_buttons[color_key] = (color_btn, color_edit)
        
        content_layout.addWidget(color_group)
        
        # 폰트 설정 영역
        font_group = QGroupBox("폰트 설정")
        font_layout = QGridLayout(font_group)
        
        # 기본 폰트
        font_layout.addWidget(QLabel("기본 폰트:"), 0, 0)
        self.font_family_edit = QLineEdit(self.edited_theme.get("font_family", "Segoe UI"))
        font_layout.addWidget(self.font_family_edit, 0, 1)
        
        font_select_btn = QPushButton("폰트 선택...")
        font_select_btn.clicked.connect(self.select_font)
        font_layout.addWidget(font_select_btn, 0, 2)
        
        # 폰트 크기
        font_layout.addWidget(QLabel("폰트 크기:"), 1, 0)
        self.font_size_edit = QLineEdit(self.edited_theme.get("font_size", "9pt"))
        font_layout.addWidget(self.font_size_edit, 1, 1)
        
        # 헤더 폰트
        font_layout.addWidget(QLabel("헤더 폰트:"), 2, 0)
        self.header_font_family_edit = QLineEdit(self.edited_theme.get("header_font_family", "Segoe UI"))
        font_layout.addWidget(self.header_font_family_edit, 2, 1)
        
        header_font_select_btn = QPushButton("폰트 선택...")
        header_font_select_btn.clicked.connect(self.select_header_font)
        font_layout.addWidget(header_font_select_btn, 2, 2)
        
        # 헤더 폰트 크기
        font_layout.addWidget(QLabel("헤더 폰트 크기:"), 3, 0)
        self.header_font_size_edit = QLineEdit(self.edited_theme.get("header_font_size", "10pt"))
        font_layout.addWidget(self.header_font_size_edit, 3, 1)
        
        # 헤더 폰트 굵기
        font_layout.addWidget(QLabel("헤더 폰트 굵기:"), 4, 0)
        self.header_font_weight_combo = QComboBox()
        self.header_font_weight_combo.addItems(["normal", "bold", "light", "medium", "semibold"])
        self.header_font_weight_combo.setCurrentText(self.edited_theme.get("header_font_weight", "bold"))
        font_layout.addWidget(self.header_font_weight_combo, 4, 1)
        
        content_layout.addWidget(font_group)
        
        # 스타일 설정 영역
        style_group = QGroupBox("스타일 설정")
        style_layout = QGridLayout(style_group)
        
        # 테두리 둥글기
        style_layout.addWidget(QLabel("테두리 둥글기:"), 0, 0)
        self.border_radius_edit = QLineEdit(self.edited_theme.get("border_radius", "3px"))
        style_layout.addWidget(self.border_radius_edit, 0, 1)
        
        # 그림자
        style_layout.addWidget(QLabel("그림자:"), 1, 0)
        self.shadow_edit = QLineEdit(self.edited_theme.get("shadow", "0 2px 4px rgba(0, 0, 0, 0.1)"))
        style_layout.addWidget(self.shadow_edit, 1, 1)
        
        # 버튼 스타일
        style_layout.addWidget(QLabel("버튼 스타일:"), 2, 0)
        self.button_style_combo = QComboBox()
        self.button_style_combo.addItems(["flat", "rounded", "outline"])
        self.button_style_combo.setCurrentText(self.edited_theme.get("button_style", "flat"))
        style_layout.addWidget(self.button_style_combo, 2, 1)
        
        content_layout.addWidget(style_group)
    
    def setup_advanced_tab(self, tab):
        layout = QVBoxLayout(tab)
        
        # 스크롤 영역 생성
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(scroll)
        
        # 스크롤 내용 위젯
        content = QWidget()
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        
        # 그라데이션 설정
        gradient_group = QGroupBox("그라데이션 설정")
        gradient_layout = QGridLayout(gradient_group)
        
        # 그라데이션 사용 여부
        self.gradient_check = QCheckBox("그라데이션 사용")
        self.gradient_check.setChecked(self.edited_theme.get("gradient", False))
        gradient_layout.addWidget(self.gradient_check, 0, 0, 1, 2)
        
        # 그라데이션 시작 색상
        gradient_layout.addWidget(QLabel("시작 색상:"), 1, 0)
        gradient_start_value = self.edited_theme.get("gradient_start", self.edited_theme.get("primary", "#000000"))
        self.gradient_start_btn = QPushButton()
        self.gradient_start_btn.setFixedSize(30, 20)
        self.gradient_start_btn.setStyleSheet(f"background-color: {gradient_start_value}; border: 1px solid #cccccc;")
        self.gradient_start_btn.clicked.connect(lambda: self.select_gradient_color("start"))
        
        self.gradient_start_edit = QLineEdit(gradient_start_value)
        self.gradient_start_edit.textChanged.connect(lambda text: self.update_gradient_color("start", text))
        
        gradient_layout.addWidget(self.gradient_start_btn, 1, 1)
        gradient_layout.addWidget(self.gradient_start_edit, 1, 2)
        
        # 그라데이션 끝 색상
        gradient_layout.addWidget(QLabel("끝 색상:"), 2, 0)
        gradient_end_value = self.edited_theme.get("gradient_end", self.edited_theme.get("primary_light", "#000000"))
        self.gradient_end_btn = QPushButton()
        self.gradient_end_btn.setFixedSize(30, 20)
        self.gradient_end_btn.setStyleSheet(f"background-color: {gradient_end_value}; border: 1px solid #cccccc;")
        self.gradient_end_btn.clicked.connect(lambda: self.select_gradient_color("end"))
        
        self.gradient_end_edit = QLineEdit(gradient_end_value)
        self.gradient_end_edit.textChanged.connect(lambda text: self.update_gradient_color("end", text))
        
        gradient_layout.addWidget(self.gradient_end_btn, 2, 1)
        gradient_layout.addWidget(self.gradient_end_edit, 2, 2)
        
        content_layout.addWidget(gradient_group)
        
        # 애니메이션 설정
        animation_group = QGroupBox("애니메이션 설정")
        animation_layout = QGridLayout(animation_group)
        
        # 애니메이션 속도
        animation_layout.addWidget(QLabel("애니메이션 속도:"), 0, 0)
        self.animation_speed_combo = QComboBox()
        self.animation_speed_combo.addItems(["slow", "normal", "fast"])
        self.animation_speed_combo.setCurrentText(self.edited_theme.get("animation_speed", "normal"))
        animation_layout.addWidget(self.animation_speed_combo, 0, 1)
        
        # 전환 효과
        # animation_layout.addWidget(QLabel("전환 효과:"), 1, 0)
        # self.transition_edit = QLineEdit(self.edited_theme.get("transition", "all 0.2s ease"))
        # animation_layout.addWidget(self.transition_edit, 1, 1)
        
        content_layout.addWidget(animation_group)
        
        # UI 요소 설정
        ui_group = QGroupBox("UI 요소 설정")
        ui_layout = QGridLayout(ui_group)
        
        # 툴팁 스타일
        ui_layout.addWidget(QLabel("툴팁 스타일:"), 0, 0)
        self.tooltip_style_combo = QComboBox()
        self.tooltip_style_combo.addItems(["light", "dark"])
        self.tooltip_style_combo.setCurrentText(self.edited_theme.get("tooltip_style", "light"))
        ui_layout.addWidget(self.tooltip_style_combo, 0, 1)
        
        # 스크롤바 스타일
        ui_layout.addWidget(QLabel("스크롤바 스타일:"), 1, 0)
        self.scrollbar_style_combo = QComboBox()
        self.scrollbar_style_combo.addItems(["normal", "thin", "hidden"])
        self.scrollbar_style_combo.setCurrentText(self.edited_theme.get("scrollbar_style", "normal"))
        ui_layout.addWidget(self.scrollbar_style_combo, 1, 1)
        
        # 포커스 스타일
        ui_layout.addWidget(QLabel("포커스 스타일:"), 2, 0)
        self.focus_style_combo = QComboBox()
        self.focus_style_combo.addItems(["outline", "glow", "underline"])
        self.focus_style_combo.setCurrentText(self.edited_theme.get("focus_style", "outline"))
        ui_layout.addWidget(self.focus_style_combo, 2, 1)
        
        # 포커스 색상
        ui_layout.addWidget(QLabel("포커스 색상:"), 3, 0)
        focus_color_value = self.edited_theme.get("focus_color", self.edited_theme.get("primary", "#000000"))
        self.focus_color_btn = QPushButton()
        self.focus_color_btn.setFixedSize(30, 20)
        self.focus_color_btn.setStyleSheet(f"background-color: {focus_color_value}; border: 1px solid #cccccc;")
        self.focus_color_btn.clicked.connect(self.select_focus_color)
        
        self.focus_color_edit = QLineEdit(focus_color_value)
        self.focus_color_edit.textChanged.connect(self.update_focus_color)
        
        ui_layout.addWidget(self.focus_color_btn, 3, 1)
        ui_layout.addWidget(self.focus_color_edit, 3, 2)
        
        content_layout.addWidget(ui_group)
        
        # 아이콘 설정
        icon_group = QGroupBox("아이콘 설정")
        icon_layout = QGridLayout(icon_group)
        
        # 아이콘 색상
        icon_layout.addWidget(QLabel("아이콘 색상:"), 0, 0)
        icon_color_value = self.edited_theme.get("icon_color", self.edited_theme.get("primary", "#000000"))
        self.icon_color_btn = QPushButton()
        self.icon_color_btn.setFixedSize(30, 20)
        self.icon_color_btn.setStyleSheet(f"background-color: {icon_color_value}; border: 1px solid #cccccc;")
        self.icon_color_btn.clicked.connect(self.select_icon_color)
        
        self.icon_color_edit = QLineEdit(icon_color_value)
        self.icon_color_edit.textChanged.connect(self.update_icon_color)
        
        icon_layout.addWidget(self.icon_color_btn, 0, 1)
        icon_layout.addWidget(self.icon_color_edit, 0, 2)
        
        content_layout.addWidget(icon_group)
    
    def setup_preview_tab(self, tab):
        layout = QVBoxLayout(tab)
        
        # 미리보기 업데이트 버튼
        update_btn = QPushButton("미리보기 업데이트")
        update_btn.clicked.connect(self.update_preview)
        layout.addWidget(update_btn)
        
        # 미리보기 영역
        self.preview_widget = QWidget()
        self.preview_widget.setMinimumHeight(400)
        preview_layout = QVBoxLayout(self.preview_widget)
        
        # 미리보기 요소들
        preview_header = QLabel("테마 미리보기 헤더")
        preview_header.setProperty("heading", True)
        preview_header.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(preview_header)
        
        # 버튼 그룹
        button_group = QGroupBox("버튼")
        button_layout = QHBoxLayout(button_group)
        
        normal_btn = QPushButton("일반 버튼")
        button_layout.addWidget(normal_btn)
        
        primary_btn = QPushButton("주요 버튼")
        primary_btn.setProperty("primary", True)
        button_layout.addWidget(primary_btn)
        
        disabled_btn = QPushButton("비활성화 버튼")
        disabled_btn.setEnabled(False)
        button_layout.addWidget(disabled_btn)
        
        preview_layout.addWidget(button_group)
        
        # 입력 요소 그룹
        input_group = QGroupBox("입력 요소")
        input_layout = QGridLayout(input_group)
        
        input_layout.addWidget(QLabel("텍스트 입력:"), 0, 0)
        input_layout.addWidget(QLineEdit("텍스트 입력 예시"), 0, 1)
        
        input_layout.addWidget(QLabel("콤보박스:"), 1, 0)
        combo = QComboBox()
        combo.addItems(["항목 1", "항목 2", "항목 3"])
        input_layout.addWidget(combo, 1, 1)
        
        input_layout.addWidget(QLabel("체크박스:"), 2, 0)
        check_layout = QHBoxLayout()
        check1 = QCheckBox("옵션 1")
        check1.setChecked(True)
        check_layout.addWidget(check1)
        check_layout.addWidget(QCheckBox("옵션 2"))
        input_layout.addLayout(check_layout, 2, 1)
        
        input_layout.addWidget(QLabel("라디오 버튼:"), 3, 0)
        radio_layout = QHBoxLayout()
        radio1 = QRadioButton("선택 1")
        radio1.setChecked(True)
        radio_layout.addWidget(radio1)
        radio_layout.addWidget(QRadioButton("선택 2"))
        input_layout.addLayout(radio_layout, 3, 1)
        
        preview_layout.addWidget(input_group)
        
        # 그라데이션 미리보기
        gradient_group = QGroupBox("그라데이션 미리보기")
        gradient_layout = QVBoxLayout(gradient_group)
        
        self.gradient_preview = QLabel()
        self.gradient_preview.setMinimumHeight(40)
        self.gradient_preview.setStyleSheet("border: 1px solid #cccccc;")
        gradient_layout.addWidget(self.gradient_preview)
        
        preview_layout.addWidget(gradient_group)
        
        layout.addWidget(self.preview_widget)
        
        # 초기 미리보기 업데이트
        self.update_preview()
    
    def select_color(self, color_key):
        """색상 선택 다이얼로그 표시"""
        current_color = QColor(self.edited_theme.get(color_key, "#000000"))
        color = QColorDialog.getColor(current_color, self, f"{color_key} 색상 선택")
        
        if color.isValid():
            hex_color = color.name()
            self.edited_theme[color_key] = hex_color
            
            # UI 업데이트
            btn, edit = self.color_buttons[color_key]
            btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #cccccc;")
            edit.setText(hex_color)
            
            # 미리보기 업데이트
            self.update_preview()
    
    def update_color(self, color_key, text, btn):
        """색상 텍스트 변경 시 업데이트"""
        if text.startswith('#') and len(text) in [4, 7]:  # #RGB 또는 #RRGGBB 형식
            self.edited_theme[color_key] = text
            btn.setStyleSheet(f"background-color: {text}; border: 1px solid #cccccc;")
    
    def select_font(self):
        """폰트 선택 다이얼로그 표시"""
        current_font = QFont(self.edited_theme.get("font_family", "Segoe UI"))
        font, ok = QFontDialog.getFont(current_font, self, "기본 폰트 선택")
        
        if ok:
            self.edited_theme["font_family"] = font.family()
            self.font_family_edit.setText(font.family())
            
            # 미리보기 업데이트
            self.update_preview()
    
    def select_header_font(self):
        """헤더 폰트 선택 다이얼로그 표시"""
        current_font = QFont(self.edited_theme.get("header_font_family", "Segoe UI"))
        font, ok = QFontDialog.getFont(current_font, self, "헤더 폰트 선택")
        
        if ok:
            self.edited_theme["header_font_family"] = font.family()
            self.header_font_family_edit.setText(font.family())
            
            # 미리보기 업데이트
            self.update_preview()
    
    def select_gradient_color(self, position):
        """그라데이션 색상 선택 다이얼로그 표시"""
        key = f"gradient_{position}"
        current_color = QColor(self.edited_theme.get(key, "#000000"))
        color = QColorDialog.getColor(current_color, self, f"그라데이션 {position} 색상 선택")
        
        if color.isValid():
            hex_color = color.name()
            self.edited_theme[key] = hex_color
            
            # UI 업데이트
            if position == "start":
                self.gradient_start_btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #cccccc;")
                self.gradient_start_edit.setText(hex_color)
            else:
                self.gradient_end_btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #cccccc;")
                self.gradient_end_edit.setText(hex_color)
            
            # 미리보기 업데이트
            self.update_preview()
    
    def update_gradient_color(self, position, text):
        """그라데이션 색상 텍스트 변경 시 업데이트"""
        if text.startswith('#') and len(text) in [4, 7]:  # #RGB 또는 #RRGGBB 형식
            key = f"gradient_{position}"
            self.edited_theme[key] = text
            
            # UI 업데이트
            if position == "start":
                self.gradient_start_btn.setStyleSheet(f"background-color: {text}; border: 1px solid #cccccc;")
            else:
                self.gradient_end_btn.setStyleSheet(f"background-color: {text}; border: 1px solid #cccccc;")
    
    def select_focus_color(self):
        """포커스 색상 선택 다이얼로그 표시"""
        current_color = QColor(self.edited_theme.get("focus_color", "#000000"))
        color = QColorDialog.getColor(current_color, self, "포커스 색상 선택")
        
        if color.isValid():
            hex_color = color.name()
            self.edited_theme["focus_color"] = hex_color
            
            # UI 업데이트
            self.focus_color_btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #cccccc;")
            self.focus_color_edit.setText(hex_color)
            
            # 미리보기 업데이트
            self.update_preview()
    
    def update_focus_color(self, text):
        """포커스 색상 텍스트 변경 시 업데이트"""
        if text.startswith('#') and len(text) in [4, 7]:  # #RGB 또는 #RRGGBB 형식
            self.edited_theme["focus_color"] = text
            self.focus_color_btn.setStyleSheet(f"background-color: {text}; border: 1px solid #cccccc;")
    
    def select_icon_color(self):
        """아이콘 색상 선택 다이얼로그 표시"""
        current_color = QColor(self.edited_theme.get("icon_color", "#000000"))
        color = QColorDialog.getColor(current_color, self, "아이콘 색상 선택")
        
        if color.isValid():
            hex_color = color.name()
            self.edited_theme["icon_color"] = hex_color
            
            # UI 업데이트
            self.icon_color_btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #cccccc;")
            self.icon_color_edit.setText(hex_color)
            
            # 미리보기 업데이트
            self.update_preview()
    
    def update_icon_color(self, text):
        """아이콘 색상 텍스트 변경 시 업데이트"""
        if text.startswith('#') and len(text) in [4, 7]:  # #RGB 또는 #RRGGBB 형식
            self.edited_theme["icon_color"] = text
            self.icon_color_btn.setStyleSheet(f"background-color: {text}; border: 1px solid #cccccc;")
    
    def update_preview(self):
        """미리보기 업데이트"""
        # 현재 편집 중인 테마 데이터 수집
        self.edited_theme["font_family"] = self.font_family_edit.text()
        self.edited_theme["font_size"] = self.font_size_edit.text()
        self.edited_theme["header_font_family"] = self.header_font_family_edit.text()
        self.edited_theme["header_font_size"] = self.header_font_size_edit.text()
        self.edited_theme["header_font_weight"] = self.header_font_weight_combo.currentText()
        self.edited_theme["border_radius"] = self.border_radius_edit.text()
        self.edited_theme["shadow"] = self.shadow_edit.text()
        self.edited_theme["button_style"] = self.button_style_combo.currentText()
        self.edited_theme["gradient"] = self.gradient_check.isChecked()
        self.edited_theme["animation_speed"] = self.animation_speed_combo.currentText()
        # self.edited_theme["transition"] = self.transition_edit.text()
        self.edited_theme["tooltip_style"] = self.tooltip_style_combo.currentText()
        self.edited_theme["scrollbar_style"] = self.scrollbar_style_combo.currentText()
        self.edited_theme["focus_style"] = self.focus_style_combo.currentText()
        
        # 미리보기 스타일시트 생성
        style = self.theme_manager.generate_widget_stylesheet(self.edited_theme)
        self.preview_widget.setStyleSheet(style)
        
        # 그라데이션 미리보기 업데이트
        if self.edited_theme.get("gradient", False):
            gradient_style = f"""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                           stop:0 {self.edited_theme["gradient_start"]}, 
                                           stop:1 {self.edited_theme["gradient_end"]});
                border: 1px solid #cccccc;
            """
            self.gradient_preview.setStyleSheet(gradient_style)
        else:
            self.gradient_preview.setStyleSheet("background-color: #f0f0f0; border: 1px solid #cccccc;")
    
    def save_theme(self):
        """테마 저장"""
        # 테마 이름 가져오기
        theme_name = self.name_edit.text().strip()
        
        if not theme_name:
            QMessageBox.warning(self, "경고", "테마 이름을 입력해주세요.")
            return
        
        # 기본 테마 이름 변경 방지
        if self.theme_name in ThemeManager.DEFAULT_THEMES and theme_name != self.theme_name:
            QMessageBox.warning(self, "경고", "기본 테마의 이름은 변경할 수 없습니다.")
            return
        
        # 현재 편집 중인 테마 데이터 수집
        self.edited_theme["font_family"] = self.font_family_edit.text()
        self.edited_theme["font_size"] = self.font_size_edit.text()
        self.edited_theme["header_font_family"] = self.header_font_family_edit.text()
        self.edited_theme["header_font_size"] = self.header_font_size_edit.text()
        self.edited_theme["header_font_weight"] = self.header_font_weight_combo.currentText()
        self.edited_theme["border_radius"] = self.border_radius_edit.text()
        self.edited_theme["shadow"] = self.shadow_edit.text()
        self.edited_theme["button_style"] = self.button_style_combo.currentText()
        self.edited_theme["gradient"] = self.gradient_check.isChecked()
        self.edited_theme["animation_speed"] = self.animation_speed_combo.currentText()
        #self.edited_theme["transition"] = self.transition_edit.text()
        self.edited_theme["tooltip_style"] = self.tooltip_style_combo.currentText()
        self.edited_theme["scrollbar_style"] = self.scrollbar_style_combo.currentText()
        self.edited_theme["focus_style"] = self.focus_style_combo.currentText()
        
        # 테마 업데이트 시그널 발생
        self.theme_updated.emit(theme_name, self.edited_theme)
        self.accept()


class ThemeManagerDialog(QDialog):
    """테마 관리 다이얼로그"""
    
    theme_changed = pyqtSignal(str)
    
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.setWindowTitle("테마 관리")
        self.setMinimumSize(800, 600)
        self.initUI()
    
    def initUI(self):
        main_layout = QVBoxLayout(self)
        
        # 탭 위젯 생성
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)
        
        # 테마 선택 탭
        select_tab = QWidget()
        tab_widget.addTab(select_tab, "테마 선택")
        
        # 테마 관리 탭
        manage_tab = QWidget()
        tab_widget.addTab(manage_tab, "테마 관리")
        
        # 위젯별 테마 탭
        widget_tab = QWidget()
        tab_widget.addTab(widget_tab, "위젯별 테마")
        
        # 자동 테마 전환 탭
        auto_tab = QWidget()
        tab_widget.addTab(auto_tab, "자동 테마 전환")
        
        # 테마 선택 탭 UI
        self.setup_select_tab(select_tab)
        
        # 테마 관리 탭 UI
        self.setup_manage_tab(manage_tab)
        
        # 위젯별 테마 탭 UI
        self.setup_widget_tab(widget_tab)
        
        # 자동 테마 전환 탭 UI
        self.setup_auto_tab(auto_tab)
        
        # 닫기 버튼
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        main_layout.addWidget(close_btn, alignment=Qt.AlignRight)
    
    def setup_select_tab(self, tab):
        layout = QVBoxLayout(tab)
        
        # 테마 검색
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("테마 검색:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("테마 이름 검색...")
        self.search_edit.textChanged.connect(self.filter_themes)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)
        
        # 테마 목록
        self.theme_list = QListWidget()
        self.theme_list.setMinimumHeight(200)
        self.update_theme_list()
        self.theme_list.currentItemChanged.connect(self.on_theme_selected)
        layout.addWidget(self.theme_list)
        
        # 테마 미리보기 영역
        preview_label = QLabel("테마 미리보기:")
        layout.addWidget(preview_label)
        
        self.preview_widget = QWidget()
        self.preview_widget.setMinimumHeight(200)
        self.preview_widget.setStyleSheet("border: 1px solid #cccccc;")
        
        preview_layout = QVBoxLayout(self.preview_widget)
        
        # 미리보기 요소들
        preview_header = QLabel("테마 미리보기 헤더")
        preview_header.setProperty("heading", True)
        preview_header.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(preview_header)
        
        # 버튼 그룹
        button_layout = QHBoxLayout()
        button_layout.addWidget(QPushButton("일반 버튼"))
        
        primary_btn = QPushButton("주요 버튼")
        primary_btn.setProperty("primary", True)
        button_layout.addWidget(primary_btn)
        
        preview_layout.addLayout(button_layout)
        
        # 입력 요소
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("텍스트 입력:"))
        input_layout.addWidget(QLineEdit("텍스트 입력 예시"))
        preview_layout.addLayout(input_layout)
        
        # 콤보박스
        combo_layout = QHBoxLayout()
        combo_layout.addWidget(QLabel("콤보박스:"))
        combo = QComboBox()
        combo.addItems(["항목 1", "항목 2", "항목 3"])
        combo_layout.addWidget(combo)
        preview_layout.addLayout(combo_layout)
        
        layout.addWidget(self.preview_widget)
        
        # 테마 적용 버튼
        apply_btn = QPushButton("이 테마 적용")
        apply_btn.clicked.connect(self.apply_theme)
        layout.addWidget(apply_btn)
        
        # 초기 미리보기 업데이트
        self.update_preview(self.theme_manager.current_theme_name)
    
    def setup_manage_tab(self, tab):
        layout = QVBoxLayout(tab)
        
        # 테마 관리 버튼들
        button_layout = QHBoxLayout()
        
        # 새 테마 버튼
        new_btn = QPushButton("새 테마")
        new_btn.clicked.connect(self.create_new_theme)
        button_layout.addWidget(new_btn)
        
        # 테마 편집 버튼
        edit_btn = QPushButton("테마 편집")
        edit_btn.clicked.connect(self.edit_theme)
        button_layout.addWidget(edit_btn)
        
        # 테마 삭제 버튼
        delete_btn = QPushButton("테마 삭제")
        delete_btn.clicked.connect(self.delete_theme)
        button_layout.addWidget(delete_btn)
        
        layout.addLayout(button_layout)
        
        # 테마 가져오기/내보내기 버튼들
        io_layout = QHBoxLayout()
        
        # 테마 가져오기 버튼
        import_btn = QPushButton("테마 가져오기")
        import_btn.clicked.connect(self.import_theme)
        io_layout.addWidget(import_btn)
        
        # 테마 내보내기 버튼
        export_btn = QPushButton("테마 내보내기")
        export_btn.clicked.connect(self.export_theme)
        io_layout.addWidget(export_btn)
        
        layout.addLayout(io_layout)
        
        # 테마 목록
        self.manage_theme_list = QListWidget()
        self.manage_theme_list.setMinimumHeight(300)
        self.update_manage_theme_list()
        layout.addWidget(self.manage_theme_list)
    
    def setup_widget_tab(self, tab):
        layout = QVBoxLayout(tab)
        
        # 설명 레이블
        layout.addWidget(QLabel("특정 위젯에 테마를 적용하려면 위젯 ID를 입력하세요."))
        layout.addWidget(QLabel("위젯 ID는 위젯 객체의 고유 식별자입니다."))
        
        # 위젯 ID 입력
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("위젯 ID:"))
        self.widget_id_edit = QLineEdit()
        id_layout.addWidget(self.widget_id_edit)
        layout.addLayout(id_layout)
        
        # 테마 선택
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("적용할 테마:"))
        self.widget_theme_combo = QComboBox()
        self.widget_theme_combo.addItems(self.theme_manager.get_theme_names())
        theme_layout.addWidget(self.widget_theme_combo)
        layout.addLayout(theme_layout)
        
        # 적용 버튼
        apply_btn = QPushButton("위젯에 테마 적용")
        apply_btn.clicked.connect(self.apply_widget_theme)
        layout.addWidget(apply_btn)
        
        # 위젯별 테마 목록
        layout.addWidget(QLabel("현재 적용된 위젯별 테마:"))
        self.widget_theme_list = QListWidget()
        self.update_widget_theme_list()
        layout.addWidget(self.widget_theme_list)
        
        # 위젯 테마 초기화 버튼
        reset_btn = QPushButton("선택한 위젯 테마 초기화")
        reset_btn.clicked.connect(self.reset_widget_theme)
        layout.addWidget(reset_btn)
    
    def setup_auto_tab(self, tab):
        layout = QVBoxLayout(tab)
        
        # 자동 테마 전환 활성화
        self.auto_switch_check = QCheckBox("시간에 따른 자동 테마 전환 활성화")
        self.auto_switch_check.setChecked(self.theme_manager.settings.value("theme/auto_switch/enabled", False, type=bool))
        layout.addWidget(self.auto_switch_check)
        
        # 주간 테마 설정
        day_layout = QHBoxLayout()
        day_layout.addWidget(QLabel("주간 테마:"))
        self.day_theme_combo = QComboBox()
        self.day_theme_combo.addItems(self.theme_manager.get_theme_names())
        day_theme = self.theme_manager.settings.value("theme/auto_switch/day_theme", "기본 테마")
        index = self.day_theme_combo.findText(day_theme)
        if index >= 0:
            self.day_theme_combo.setCurrentIndex(index)
        day_layout.addWidget(self.day_theme_combo)
        layout.addLayout(day_layout)
        
        # 야간 테마 설정
        night_layout = QHBoxLayout()
        night_layout.addWidget(QLabel("야간 테마:"))
        self.night_theme_combo = QComboBox()
        self.night_theme_combo.addItems(self.theme_manager.get_theme_names())
        night_theme = self.theme_manager.settings.value("theme/auto_switch/night_theme", "다크 테마")
        index = self.night_theme_combo.findText(night_theme)
        if index >= 0:
            self.night_theme_combo.setCurrentIndex(index)
        night_layout.addWidget(self.night_theme_combo)
        layout.addLayout(night_layout)
        
        # 주간 시작 시간
        day_start_layout = QHBoxLayout()
        day_start_layout.addWidget(QLabel("주간 시작 시간:"))
        self.day_start_edit = QTimeEdit()
        self.day_start_edit.setDisplayFormat("HH:mm")
        day_start = self.theme_manager.settings.value("theme/auto_switch/day_start", "08:00")
        self.day_start_edit.setTime(QTime.fromString(day_start, "HH:mm"))
        day_start_layout.addWidget(self.day_start_edit)
        layout.addLayout(day_start_layout)
        
        # 야간 시작 시간
        night_start_layout = QHBoxLayout()
        night_start_layout.addWidget(QLabel("야간 시작 시간:"))
        self.night_start_edit = QTimeEdit()
        self.night_start_edit.setDisplayFormat("HH:mm")
        night_start = self.theme_manager.settings.value("theme/auto_switch/night_start", "20:00")
        self.night_start_edit.setTime(QTime.fromString(night_start, "HH:mm"))
        night_start_layout.addWidget(self.night_start_edit)
        layout.addLayout(night_start_layout)
        
        # 적용 버튼
        apply_btn = QPushButton("자동 테마 전환 설정 적용")
        apply_btn.clicked.connect(self.apply_auto_theme_settings)
        layout.addWidget(apply_btn)
        
        # 현재 시간 표시
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("현재 시간:"))
        self.current_time_label = QLabel(QTime.currentTime().toString("HH:mm:ss"))
        time_layout.addWidget(self.current_time_label)
        layout.addLayout(time_layout)
        
        # 현재 시간 업데이트 타이머
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_current_time)
        self.time_timer.start(1000)  # 1초마다 업데이트
    
    def update_theme_list(self):
        """테마 목록 업데이트"""
        current_theme = self.theme_manager.current_theme_name
        
        self.theme_list.clear()
        for theme_name in self.theme_manager.get_theme_names():
            item = QListWidgetItem(theme_name)
            if theme_name == current_theme:
                item.setBackground(QColor("#e0e0e0"))
            self.theme_list.addItem(item)
        
        # 현재 테마 선택
        for i in range(self.theme_list.count()):
            if self.theme_list.item(i).text() == current_theme:
                self.theme_list.setCurrentRow(i)
                break
    
    def update_manage_theme_list(self):
        """테마 관리 목록 업데이트"""
        self.manage_theme_list.clear()
        for theme_name in self.theme_manager.get_theme_names():
            item = QListWidgetItem(theme_name)
            if theme_name in ThemeManager.DEFAULT_THEMES:
                item.setBackground(QColor("#e0e0e0"))
                item.setToolTip("기본 테마")
            self.manage_theme_list.addItem(item)
    
    def update_widget_theme_list(self):
        """위젯별 테마 목록 업데이트"""
        self.widget_theme_list.clear()
        for widget_id, theme_name in self.theme_manager.widget_specific_themes.items():
            self.widget_theme_list.addItem(f"위젯 ID: {widget_id} - 테마: {theme_name}")
    
    def update_preview(self, theme_name):
        """테마 미리보기 업데이트"""
        if not theme_name or theme_name not in self.theme_manager.themes:
            return
            
        theme = self.theme_manager.themes[theme_name]
        
        # 미리보기 스타일시트 생성
        style = self.theme_manager.generate_widget_stylesheet(theme)
        self.preview_widget.setStyleSheet(style)
    
    def on_theme_selected(self, current, previous):
        """테마 선택 시 미리보기 업데이트"""
        if current:
            self.update_preview(current.text())
    
    def apply_theme(self):
        """선택한 테마 적용"""
        current_item = self.theme_list.currentItem()
        if current_item:
            theme_name = current_item.text()
            if theme_name and self.theme_manager.set_current_theme(theme_name):
                self.theme_changed.emit(theme_name)
                self.update_theme_list()
    
    def filter_themes(self, keyword):
        """테마 검색 필터링"""
        filtered_themes = self.theme_manager.search_themes(keyword)
        
        self.theme_list.clear()
        for theme_name in filtered_themes:
            item = QListWidgetItem(theme_name)
            if theme_name == self.theme_manager.current_theme_name:
                item.setBackground(QColor("#e0e0e0"))
            self.theme_list.addItem(item)
    
    def create_new_theme(self):
        """새 테마 생성"""
        editor = ThemeEditorDialog(self.theme_manager, None, self)
        editor.theme_updated.connect(self.on_theme_updated)
        editor.exec_()
    
    def edit_theme(self):
        """테마 편집"""
        current_item = self.manage_theme_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "경고", "편집할 테마를 선택해주세요.")
            return
            
        theme_name = current_item.text()
        editor = ThemeEditorDialog(self.theme_manager, theme_name, self)
        editor.theme_updated.connect(self.on_theme_updated)
        editor.exec_()
    
    def delete_theme(self):
        """테마 삭제"""
        current_item = self.manage_theme_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "경고", "삭제할 테마를 선택해주세요.")
            return
            
        theme_name = current_item.text()
        
        # 기본 테마는 삭제 불가
        if theme_name in ThemeManager.DEFAULT_THEMES:
            QMessageBox.warning(self, "경고", "기본 테마는 삭제할 수 없습니다.")
            return
            
        reply = QMessageBox.question(
            self, "테마 삭제 확인", 
            f"테마 '{theme_name}'을(를) 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.theme_manager.remove_theme(theme_name):
                self.update_theme_list()
                self.update_manage_theme_list()
                self.update_preview(self.theme_list.currentItem().text() if self.theme_list.currentItem() else None)
    
    def import_theme(self):
        """테마 가져오기"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "테마 파일 가져오기", "", "JSON 파일 (*.json)"
        )
        
        if file_path:
            if self.theme_manager.import_theme(file_path):
                QMessageBox.information(self, "성공", "테마를 성공적으로 가져왔습니다.")
                self.update_theme_list()
                self.update_manage_theme_list()
            else:
                QMessageBox.warning(self, "오류", "테마 가져오기에 실패했습니다.")
    
    def export_theme(self):
        """테마 내보내기"""
        current_item = self.manage_theme_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "경고", "내보낼 테마를 선택해주세요.")
            return
            
        theme_name = current_item.text()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "테마 파일 저장", f"{theme_name}.json", "JSON 파일 (*.json)"
        )
        
        if file_path:
            if self.theme_manager.export_theme(theme_name, file_path):
                QMessageBox.information(self, "성공", "테마를 성공적으로 내보냈습니다.")
            else:
                QMessageBox.warning(self, "오류", "테마 내보내기에 실패했습니다.")
    
    def apply_widget_theme(self):
        """위젯에 테마 적용"""
        widget_id = self.widget_id_edit.text().strip()
        theme_name = self.widget_theme_combo.currentText()
        
        if not widget_id:
            QMessageBox.warning(self, "경고", "위젯 ID를 입력해주세요.")
            return
        
        # 위젯 ID를 위젯별 테마 설정에 추가
        self.theme_manager.widget_specific_themes[widget_id] = theme_name
        self.theme_manager.save_widget_themes()
        
        # 위젯별 테마 목록 업데이트
        self.update_widget_theme_list()
        
        QMessageBox.information(self, "성공", f"위젯 ID '{widget_id}'에 '{theme_name}' 테마를 적용했습니다.")
    
    def reset_widget_theme(self):
        """위젯 테마 초기화"""
        current_item = self.widget_theme_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "경고", "초기화할 위젯을 선택해주세요.")
            return
        
        # 위젯 ID 추출
        item_text = current_item.text()
        widget_id = item_text.split(" - ")[0].replace("위젯 ID: ", "")
        
        # 위젯별 테마 설정에서 제거
        if widget_id in self.theme_manager.widget_specific_themes:
            del self.theme_manager.widget_specific_themes[widget_id]
            self.theme_manager.save_widget_themes()
            
            # 위젯별 테마 목록 업데이트
            self.update_widget_theme_list()
            
            QMessageBox.information(self, "성공", f"위젯 ID '{widget_id}'의 테마를 초기화했습니다.")
    
    def apply_auto_theme_settings(self):
        """자동 테마 전환 설정 적용"""
        enabled = self.auto_switch_check.isChecked()
        day_theme = self.day_theme_combo.currentText()
        night_theme = self.night_theme_combo.currentText()
        day_start = self.day_start_edit.time().toString("HH:mm")
        night_start = self.night_start_edit.time().toString("HH:mm")
        
        # 설정 저장
        self.theme_manager.save_auto_theme_settings(enabled, day_theme, night_theme, day_start, night_start)
        
        # 자동 테마 전환 활성화/비활성화
        if enabled:
            self.theme_manager.enable_auto_theme_switch(day_theme, night_theme, day_start, night_start)
        else:
            self.theme_manager.disable_auto_theme_switch()
        
        QMessageBox.information(self, "성공", "자동 테마 전환 설정이 적용되었습니다.")
    
    def update_current_time(self):
        """현재 시간 업데이트"""
        self.current_time_label.setText(QTime.currentTime().toString("HH:mm:ss"))
    
    def on_theme_updated(self, theme_name, theme_data):
        """테마 업데이트 처리"""
        # 기존 테마 이름과 다른 경우 (새 테마 또는 이름 변경)
        if self.manage_theme_list.currentItem() is None or self.manage_theme_list.currentItem().text() != theme_name:
            self.theme_manager.add_theme(theme_name, theme_data)
        else:
            # 기존 테마 업데이트
            if theme_name in ThemeManager.DEFAULT_THEMES:
                # 기본 테마는 이름 변경 불가, 내용만 임시 변경
                self.theme_manager.themes[theme_name] = theme_data
            else:
                # 사용자 테마는 완전히 업데이트
                self.theme_manager.add_theme(theme_name, theme_data)
        
        # UI 업데이트
        self.update_theme_list()
        self.update_manage_theme_list()
        
        # 현재 테마가 업데이트된 경우 애플리케이션에 적용
        if self.theme_manager.current_theme_name == theme_name:
            self.theme_changed.emit(theme_name)


# 테마 적용 예시
def apply_theme_to_widget(widget, theme):
    """
    위젯에 테마를 적용합니다.
    
    Args:
        widget (QWidget): 테마를 적용할 위젯
        theme (dict): 테마 데이터
    """
    # 위젯 스타일시트 설정
    widget.setStyleSheet(f"""
        QWidget {{
            background-color: {theme["light"]};
            color: {theme["dark"]};
            font-family: {theme.get("font_family", "Segoe UI")};
        }}
        
        QPushButton {{
            background-color: {theme["primary"]};
            color: {theme["white"]};
            border: none;
            border-radius: {theme["border_radius"]};
            padding: 6px 12px;
            min-height: 30px;
        }}
        
        QPushButton:hover {{
            background-color: {theme["primary_light"]};
        }}
        
        QLineEdit, QTextEdit {{
            border: 1px solid {theme["gray_light"]};
            border-radius: {theme["border_radius"]};
            padding: 4px 8px;
            background-color: {theme["white"]};
        }}
        
        QComboBox {{
            border: 1px solid {theme["gray_light"]};
            border-radius: {theme["border_radius"]};
            padding: 4px 8px;
            background-color: {theme["white"]};
            min-height: 30px;
        }}
        
        QGroupBox {{
            border: 1px solid {theme["gray_light"]};
            border-radius: {theme["border_radius"]};
            margin-top: 1ex;
            font-weight: bold;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: {theme["primary"]};
        }}
    """)


# 사용 예시
if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    # 테마 관리자 생성
    theme_manager = ThemeManager()
    
    # 테마 관리 다이얼로그 표시
    dialog = ThemeManagerDialog(theme_manager)
    
    # 테마 변경 시 애플리케이션에 적용
    def on_theme_changed(theme_name):
        theme_manager.apply_theme_to_app(app)
        print(f"테마 '{theme_name}'이(가) 적용되었습니다.")
    
    dialog.theme_changed.connect(on_theme_changed)
    
    # 현재 테마 적용
    theme_manager.apply_theme_to_app(app)
    
    dialog.exec_()
    
    sys.exit(app.exec_())