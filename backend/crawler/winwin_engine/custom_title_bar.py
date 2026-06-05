# ═══════════════════════════════════════════════════════════════
# custom_title_bar.py — 커스텀 프레임리스 타이틀 바
# Windows 기본 프레임 제거 → 자체 네온 타이틀 바
# ═══════════════════════════════════════════════════════════════

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QSizePolicy,
    QGraphicsDropShadowEffect, QApplication
)
from PyQt5.QtCore import Qt, QPoint, QSize, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QColor, QIcon, QPainter, QPainterPath, QLinearGradient


class TitleBarButton(QPushButton):
    """타이틀 바 버튼 (최소화/최대화/닫기)"""
    def __init__(self, text, btn_type="normal", parent=None):
        super().__init__(text, parent)
        self.btn_type = btn_type
        self.setFixedSize(40, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 10))
        
        if btn_type == "close":
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #8b949e;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: #e81123;
                    color: white;
                }
                QPushButton:pressed {
                    background: #c50f1f;
                }
            """)
        elif btn_type == "maximize":
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #8b949e;
                    border: none;
                    border-radius: 6px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: rgba(56,189,248,0.2);
                    color: #38bdf8;
                }
                QPushButton:pressed {
                    background: rgba(56,189,248,0.3);
                }
            """)
        else:  # minimize
            self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #8b949e;
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: rgba(56,189,248,0.2);
                    color: #38bdf8;
                }
                QPushButton:pressed {
                    background: rgba(56,189,248,0.3);
                }
            """)


class CustomTitleBar(QWidget):
    """
    커스텀 타이틀 바 — 네온 그라디언트 + 로고 + 사용자 정보 + 윈도우 컨트롤
    """
    def __init__(self, parent_window, username="", role_label="", parent=None):
        super().__init__(parent)
        self.parent_window = parent_window
        self._drag_pos = None
        self._is_maximized = False
        
        self.setFixedHeight(48)
        self.setStyleSheet("""
            QWidget {
                background: transparent;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(8)
        
        # ── 앱 아이콘 + 로고 ──
        logo = QLabel("⚡")
        logo.setFont(QFont("Segoe UI", 16))
        logo.setStyleSheet("color: #38bdf8; background: transparent;")
        logo.setFixedWidth(30)
        layout.addWidget(logo)
        
        title = QLabel("Winwin Auto Crawler")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #e6edf3; background: transparent; letter-spacing: 1px;")
        layout.addWidget(title)
        
        # ── 버전 뱃지 ──
        ver_badge = QLabel("v3.0")
        ver_badge.setFont(QFont("Segoe UI", 8, QFont.Bold))
        ver_badge.setStyleSheet("""
            color: #38bdf8;
            background: rgba(56,189,248,0.1);
            border: 1px solid rgba(56,189,248,0.3);
            border-radius: 8px;
            padding: 2px 8px;
        """)
        layout.addWidget(ver_badge)
        
        layout.addStretch()
        
        # ── 사용자 정보 ──
        if username:
            user_info = QLabel(f"👤 {username}  ·  {role_label}")
            user_info.setFont(QFont("Segoe UI", 9))
            user_info.setStyleSheet("""
                color: rgba(255,255,255,0.65);
                background: rgba(56,189,248,0.08);
                border: 1px solid rgba(56,189,248,0.15);
                border-radius: 14px;
                padding: 4px 14px;
            """)
            layout.addWidget(user_info)
        
        layout.addSpacing(12)
        
        # ── 윈도우 컨트롤 버튼 ──
        self.min_btn = TitleBarButton("─", "minimize")
        self.min_btn.clicked.connect(self._minimize)
        layout.addWidget(self.min_btn)
        
        self.max_btn = TitleBarButton("□", "maximize")
        self.max_btn.clicked.connect(self._maximize_restore)
        layout.addWidget(self.max_btn)
        
        self.close_btn = TitleBarButton("✕", "close")
        self.close_btn.clicked.connect(self._close)
        layout.addWidget(self.close_btn)

    def paintEvent(self, event):
        """플랫 다크 배경 그리기"""
        painter = QPainter(self)
        
        # 완전 단색 다크 배경
        painter.fillRect(self.rect(), QColor("#111827"))
        
        # 하단 1px 구분선 (매우 은은하게)
        from PyQt5.QtGui import QPen
        painter.setPen(QPen(QColor("#374151"), 1))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        
        painter.end()

    # ── 윈도우 드래그 ──
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            if self._is_maximized:
                self._maximize_restore()
            self.parent_window.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._maximize_restore()

    def _minimize(self):
        self.parent_window.showMinimized()

    def _maximize_restore(self):
        if self._is_maximized:
            self.parent_window.showNormal()
            self.max_btn.setText("□")
            self._is_maximized = False
        else:
            self.parent_window.showMaximized()
            self.max_btn.setText("❐")
            self._is_maximized = True

    def _close(self):
        self.parent_window.close()
