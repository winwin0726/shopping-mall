from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSizePolicy
from ui_styles import StyledButton

class KakaoCrawlTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.initUI()
        
    def initUI(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        self.main_window.kakao_login_btn = StyledButton("카카오스토리 열기/로그인", color="#facc15")
        self.main_window.kakao_login_btn.clicked.connect(self.main_window.start_login)
        self.main_window.kakao_crawl_btn = StyledButton("가져오기", color="#4ade80")
        self.main_window.kakao_crawl_btn.setMinimumHeight(40)
        self.main_window.kakao_crawl_btn.clicked.connect(lambda: self.main_window.start_crawling(target="kakao"))
        self.main_window.kakao_stop_crawl_btn = StyledButton("중지", color="#ef4444")
        self.main_window.kakao_stop_crawl_btn.clicked.connect(self.main_window.stop_crawling_action)
        
        for btn in [self.main_window.kakao_login_btn, self.main_window.kakao_crawl_btn, self.main_window.kakao_stop_crawl_btn]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout.addWidget(self.main_window.kakao_login_btn)
        layout.addWidget(self.main_window.kakao_crawl_btn)
        layout.addWidget(self.main_window.kakao_stop_crawl_btn)
