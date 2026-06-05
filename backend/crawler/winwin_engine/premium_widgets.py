# ═══════════════════════════════════════════════════════════════
# premium_widgets.py — PyQt5 프리미엄 위젯 시스템
# 그림자 효과, 호버 애니메이션, 네온 발광 프로그레스 바
# ═══════════════════════════════════════════════════════════════

from PyQt5.QtWidgets import (
    QGroupBox, QPushButton, QProgressBar, QGraphicsDropShadowEffect,
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget, QSizePolicy
)
from PyQt5.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer,
    QSize, QRect, QPoint
)
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QLinearGradient, QFont,
    QPainterPath, QRadialGradient
)

# ═══════════════════════════════════════════════════════════════
# 색상 팔레트
# ═══════════════════════════════════════════════════════════════
NEON = {
    "bg_dark": "#0d1117",
    "bg_card": "#161b22",
    "bg_card_hover": "#1c2333",
    "border": "rgba(56,189,248,0.15)",
    "border_hover": "rgba(56,189,248,0.4)",
    "cyan": "#38bdf8",
    "blue": "#1d4ed8",
    "indigo": "#6366f1",
    "purple": "#9333ea",
    "violet": "#c084fc",
    "text": "#e6edf3",
    "text_dim": "#8b949e",
    "shadow_color": QColor(56, 189, 248, 60),
    "shadow_hover": QColor(99, 102, 241, 100),
}


# ═══════════════════════════════════════════════════════════════
# GlowCard — 그림자 + 호버 글로우 카드
# ═══════════════════════════════════════════════════════════════
class GlowCard(QGroupBox):
    """
    QGroupBox 대체. 실제 그림자 효과 + 호버 시 글로우 확대.
    """
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        
        # 그림자 효과 생성
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(20)
        self._shadow.setXOffset(0)
        self._shadow.setYOffset(4)
        self._shadow.setColor(NEON["shadow_color"])
        self.setGraphicsEffect(self._shadow)
        
        # 호버 애니메이션 (그림자 블러 반경)
        self._blur_anim = QPropertyAnimation(self._shadow, b"blurRadius")
        self._blur_anim.setDuration(200)
        self._blur_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        # 색상 애니메이션
        self._color_anim = QPropertyAnimation(self._shadow, b"color")
        self._color_anim.setDuration(200)
        self._color_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        self.setMouseTracking(True)

    def enterEvent(self, event):
        # 호버: 그림자 확대 + 색상 변경
        self._blur_anim.stop()
        self._blur_anim.setStartValue(self._shadow.blurRadius())
        self._blur_anim.setEndValue(35)
        self._blur_anim.start()
        
        self._color_anim.stop()
        self._color_anim.setStartValue(self._shadow.color())
        self._color_anim.setEndValue(NEON["shadow_hover"])
        self._color_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        # 떠남: 그림자 축소 + 원래 색상
        self._blur_anim.stop()
        self._blur_anim.setStartValue(self._shadow.blurRadius())
        self._blur_anim.setEndValue(20)
        self._blur_anim.start()
        
        self._color_anim.stop()
        self._color_anim.setStartValue(self._shadow.color())
        self._color_anim.setEndValue(NEON["shadow_color"])
        self._color_anim.start()
        super().leaveEvent(event)


# ═══════════════════════════════════════════════════════════════
# AnimatedButton — 호버 애니메이션 버튼
# ═══════════════════════════════════════════════════════════════
class AnimatedButton(QPushButton):
    """
    호버 시 배경색이 부드럽게 전환되고 살짝 확대되는 버튼.
    """
    def __init__(self, text="", color="#1d4ed8", hover_color="#38bdf8", parent=None):
        super().__init__(text, parent)
        self._color = QColor(color)
        self._hover_color = QColor(hover_color)
        self._current_color = QColor(color)
        self._scale = 1.0
        
        # 그림자 효과
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(12)
        self._shadow.setXOffset(0)
        self._shadow.setYOffset(3)
        self._shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(self._shadow)
        
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._apply_style()
        
        self.setMouseTracking(True)

    def _apply_style(self):
        r, g, b = self._current_color.red(), self._current_color.green(), self._current_color.blue()
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgb({r},{g},{b});
                color: #f3f4f6;
                border: 1px solid #4b5563;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 12px;
                min-height: 34px;
            }}
            QPushButton:pressed {{
                background-color: rgb({max(r-20,0)},{max(g-20,0)},{max(b-20,0)});
            }}
        """)

    def enterEvent(self, event):
        # 색상 전환 애니메이션
        anim = QPropertyAnimation(self, b"btn_color")
        anim.setDuration(200)
        anim.setStartValue(self._current_color)
        anim.setEndValue(self._hover_color)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._anim = anim  # prevent GC
        
        # 그림자 확대
        shadow_anim = QPropertyAnimation(self._shadow, b"blurRadius")
        shadow_anim.setDuration(200)
        shadow_anim.setStartValue(12)
        shadow_anim.setEndValue(25)
        shadow_anim.start()
        self._shadow_anim = shadow_anim
        
        super().enterEvent(event)

    def leaveEvent(self, event):
        anim = QPropertyAnimation(self, b"btn_color")
        anim.setDuration(300)
        anim.setStartValue(self._current_color)
        anim.setEndValue(self._color)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._anim = anim
        
        shadow_anim = QPropertyAnimation(self._shadow, b"blurRadius")
        shadow_anim.setDuration(300)
        shadow_anim.setStartValue(25)
        shadow_anim.setEndValue(12)
        shadow_anim.start()
        self._shadow_anim = shadow_anim
        
        super().leaveEvent(event)

    def get_btn_color(self):
        return self._current_color

    def set_btn_color(self, color):
        self._current_color = color
        self._apply_style()

    btn_color = pyqtProperty(QColor, get_btn_color, set_btn_color)


# ═══════════════════════════════════════════════════════════════
# NeonProgressBar — 커스텀 페인팅 프로그레스 바
# ═══════════════════════════════════════════════════════════════
class NeonProgressBar(QProgressBar):
    """
    paintEvent 오버라이드로 네온 발광 효과 프로그레스 바.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setFixedHeight(26)
        self.setStyleSheet("background: transparent; border: none;")
        
        # 글로우 애니메이션용 오프셋
        self._glow_offset = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate_glow)
        self._timer.start(30)

    def _animate_glow(self):
        self._glow_offset = (self._glow_offset + 2) % 400
        if self.value() > 0:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        radius = h / 2
        
        # 배경 트랙
        track_path = QPainterPath()
        track_path.addRoundedRect(0, 0, w, h, radius, radius)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 38, 50, 200))
        painter.drawPath(track_path)
        
        # 진행 바
        if self.maximum() > self.minimum():
            progress = (self.value() - self.minimum()) / (self.maximum() - self.minimum())
        else:
            progress = 0
            
        if progress > 0:
            bar_width = max(w * progress, h)  # 최소 폭 = 높이(원형)
            
            bar_path = QPainterPath()
            bar_path.addRoundedRect(0, 0, bar_width, h, radius, radius)
            
            # 플랫 그라디언트 
            gradient = QLinearGradient(0, 0, bar_width, 0)
            gradient.setColorAt(0.0, QColor(37, 99, 235))      # blue #2563eb
            gradient.setColorAt(1.0, QColor(59, 130, 246))     # light blue #3b82f6
            
            painter.setBrush(QBrush(gradient))
            painter.drawPath(bar_path)
            
            # 은은한 스팟 글로우 하나만 남김 (부드러운 애니메이션용)
            glow_x = (self._glow_offset / 400.0) * bar_width
            if glow_x < bar_width:
                glow_gradient = QRadialGradient(glow_x, h / 2, 20)
                glow_gradient.setColorAt(0.0, QColor(255, 255, 255, 30))
                glow_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
                painter.setBrush(QBrush(glow_gradient))
                painter.drawPath(bar_path)
        
        # 퍼센트 텍스트
        painter.setPen(QPen(QColor(255, 255, 255, 220)))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        pct = int(progress * 100) if progress > 0 else 0
        painter.drawText(QRect(0, 0, w, h), Qt.AlignCenter, f"{pct}%")
        
        painter.end()


# ═══════════════════════════════════════════════════════════════
# ShadowFrame — 그림자가 있는 프레임
# ═══════════════════════════════════════════════════════════════
class ShadowFrame(QFrame):
    """
    실제 그림자 효과가 있는 일반 프레임.
    """
    def __init__(self, parent=None, shadow_color=None, blur=15):
        super().__init__(parent)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(blur)
        shadow.setXOffset(0)
        shadow.setYOffset(3)
        shadow.setColor(shadow_color or NEON["shadow_color"])
        self.setGraphicsEffect(shadow)
