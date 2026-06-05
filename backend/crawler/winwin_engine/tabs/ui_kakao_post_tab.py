from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSizePolicy
from ui_styles import StyledButton

class KakaoPostTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.initUI()
        
    def initUI(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        self.main_window.kakao_start_post_btn = StyledButton("게시글 업로드", color="#facc15")
        self.main_window.kakao_start_post_btn.setMinimumHeight(40)
        self.main_window.kakao_start_post_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.main_window.kakao_start_post_btn.clicked.connect(self.main_window.start_kakao_posting)
        
        self.main_window.kakao_stop_post_btn = StyledButton("업로드 중지", color="#ef4444")
        self.main_window.kakao_stop_post_btn.setMinimumHeight(40)
        self.main_window.kakao_stop_post_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.main_window.kakao_stop_post_btn.clicked.connect(self.main_window.stop_kakao_posting)
        
        layout.addWidget(self.main_window.kakao_start_post_btn)
        layout.addWidget(self.main_window.kakao_stop_post_btn)
