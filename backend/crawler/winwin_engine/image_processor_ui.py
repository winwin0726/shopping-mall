import json
import os

from image_processor import save_image_processor_settings

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QLineEdit, 
    QCheckBox, QGroupBox, QFileDialog, QPushButton, QColorDialog, QSpinBox,
    QComboBox, QMessageBox, QDialog, QListWidget, QSplitter, QScrollArea,
    QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QFont, QPixmap, QImage, QPainter, QFontDatabase

class ImageProcessorSettingsUI(QWidget):
    # 설정 변경 시 발생하는 시그널
    settings_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text_color = (255, 255, 255)  # 기본 텍스트 색상: 흰색
        self.shadow_color = (0, 0, 0)      # 기본 그림자 색상: 검정색
        self.initUI()
        
        # 🚨 여기서 설정 자동 로드
        self.load_settings_from_json()
        
    def initUI(self):
        main_layout = QVBoxLayout()
        
        # 이미지 개선 설정 그룹
        enhance_group = QGroupBox("이미지 개선 설정")
        enhance_layout = QVBoxLayout()
        
        # 밝기 슬라이더
        brightness_layout = QHBoxLayout()
        brightness_layout.addWidget(QLabel("밝기:"))
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(50, 150)
        self.brightness_slider.setValue(110)  # 기본값 1.1
        self.brightness_slider.setTickPosition(QSlider.TicksBelow)
        self.brightness_slider.setTickInterval(10)
        self.brightness_slider.valueChanged.connect(self.update_settings)
        brightness_layout.addWidget(self.brightness_slider)
        self.brightness_value = QLabel("1.1")
        brightness_layout.addWidget(self.brightness_value)
        enhance_layout.addLayout(brightness_layout)
        
        # 대비 슬라이더
        contrast_layout = QHBoxLayout()
        contrast_layout.addWidget(QLabel("대비:"))
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(50, 150)
        self.contrast_slider.setValue(120)  # 기본값 1.2
        self.contrast_slider.setTickPosition(QSlider.TicksBelow)
        self.contrast_slider.setTickInterval(10)
        self.contrast_slider.valueChanged.connect(self.update_settings)
        contrast_layout.addWidget(self.contrast_slider)
        self.contrast_value = QLabel("1.2")
        contrast_layout.addWidget(self.contrast_value)
        enhance_layout.addLayout(contrast_layout)
        
        # 색상 슬라이더
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("색상:"))
        self.color_slider = QSlider(Qt.Horizontal)
        self.color_slider.setRange(50, 150)
        self.color_slider.setValue(110)  # 기본값 1.1
        self.color_slider.setTickPosition(QSlider.TicksBelow)
        self.color_slider.setTickInterval(10)
        self.color_slider.valueChanged.connect(self.update_settings)
        color_layout.addWidget(self.color_slider)
        self.color_value = QLabel("1.1")
        color_layout.addWidget(self.color_value)
        enhance_layout.addLayout(color_layout)
        
        # 선명도 슬라이더
        sharpness_layout = QHBoxLayout()
        sharpness_layout.addWidget(QLabel("선명도:"))
        self.sharpness_slider = QSlider(Qt.Horizontal)
        self.sharpness_slider.setRange(50, 150)
        self.sharpness_slider.setValue(130)  # 기본값 1.3
        self.sharpness_slider.setTickPosition(QSlider.TicksBelow)
        self.sharpness_slider.setTickInterval(10)
        self.sharpness_slider.valueChanged.connect(self.update_settings)
        sharpness_layout.addWidget(self.sharpness_slider)
        self.sharpness_value = QLabel("1.3")
        sharpness_layout.addWidget(self.sharpness_value)
        enhance_layout.addLayout(sharpness_layout)
        
        enhance_group.setLayout(enhance_layout)
        main_layout.addWidget(enhance_group)
        
        # 워터마크 설정 그룹
        watermark_group = QGroupBox("워터마크 설정")
        watermark_layout = QVBoxLayout()
        
        # 워터마크 설정 그룹에 색상 선택 버튼 추가
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("텍스트 색상:"))
        self.text_color_preview = QLabel()
        self.text_color_preview.setFixedSize(30, 20)
        self.text_color_preview.setStyleSheet("background-color: rgb(255, 255, 255); border: 1px solid #cccccc;")
        color_layout.addWidget(self.text_color_preview)
        self.select_text_color_btn = QPushButton("색상 선택...")
        self.select_text_color_btn.clicked.connect(self.select_text_color)
        color_layout.addWidget(self.select_text_color_btn)
        watermark_layout.addLayout(color_layout)
        
        # 그림자 색상 선택
        shadow_layout = QHBoxLayout()
        shadow_layout.addWidget(QLabel("그림자 색상:"))
        self.shadow_color_preview = QLabel()
        self.shadow_color_preview.setFixedSize(30, 20)
        self.shadow_color_preview.setStyleSheet("background-color: rgb(0, 0, 0); border: 1px solid #cccccc;")
        shadow_layout.addWidget(self.shadow_color_preview)
        self.select_shadow_color_btn = QPushButton("색상 선택...")
        self.select_shadow_color_btn.clicked.connect(self.select_shadow_color)
        shadow_layout.addWidget(self.select_shadow_color_btn)
        self.use_shadow_check = QCheckBox("그림자 사용")
        self.use_shadow_check.setChecked(True)
        self.use_shadow_check.stateChanged.connect(self.update_settings)
        shadow_layout.addWidget(self.use_shadow_check)
        watermark_layout.addLayout(shadow_layout)        
        
        # 워터마크 텍스트
        text_layout = QHBoxLayout()
        text_layout.addWidget(QLabel("텍스트:"))
        self.watermark_text = QLineEdit("LUXBOOM")
        self.watermark_text.textChanged.connect(self.update_settings)
        text_layout.addWidget(self.watermark_text)
        watermark_layout.addLayout(text_layout)
        
        # 폰트 크기
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("폰트 크기:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(10, 150)
        self.font_size_spin.setValue(40)
        self.font_size_spin.valueChanged.connect(self.update_settings)
        font_size_layout.addWidget(self.font_size_spin)
        watermark_layout.addLayout(font_size_layout)
        
        # 투명도 슬라이더
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(QLabel("투명도:"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(50)  # 기본값 0.5
        self.opacity_slider.setTickPosition(QSlider.TicksBelow)
        self.opacity_slider.setTickInterval(10)
        self.opacity_slider.valueChanged.connect(self.update_settings)
        opacity_layout.addWidget(self.opacity_slider)
        self.opacity_value = QLabel("0.5")
        opacity_layout.addWidget(self.opacity_value)
        watermark_layout.addLayout(opacity_layout)
        
        # 워터마크 스타일 선택 추가
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("스타일:"))
        self.watermark_style_combo = QComboBox()
        self.watermark_style_combo.addItems([
            "대각선 반복 패턴",
            "격자 패턴",
            "모서리 워터마크",
            "중앙 워터마크",
            "사용자 지정 각도"
        ])
        self.watermark_style_combo.currentIndexChanged.connect(self.update_settings)
        style_layout.addWidget(self.watermark_style_combo)
        
        # 스타일 미리보기 버튼 추가
        style_preview_btn = QPushButton("스타일 미리보기")
        style_preview_btn.clicked.connect(self.show_watermark_style_preview)
        style_layout.addWidget(style_preview_btn)
        
        watermark_layout.addLayout(style_layout)
        
        # 워터마크 각도 설정 (사용자 지정 각도 스타일용)
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("각도:"))
        self.angle_slider = QSlider(Qt.Horizontal)
        self.angle_slider.setRange(0, 360)
        self.angle_slider.setValue(45)
        self.angle_slider.setTickPosition(QSlider.TicksBelow)
        self.angle_slider.setTickInterval(45)
        self.angle_slider.valueChanged.connect(self.update_settings)
        angle_layout.addWidget(self.angle_slider)
        self.angle_value = QLabel("45°")
        angle_layout.addWidget(self.angle_value)
        watermark_layout.addLayout(angle_layout)
        
        # 폰트 선택 버튼
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("폰트:"))
        self.font_path_label = QLabel("기본 폰트")
        self.font_path_label.setStyleSheet("color: gray;")
        font_layout.addWidget(self.font_path_label)
        self.select_font_btn = QPushButton("폰트 선택...")
        self.select_font_btn.clicked.connect(self.select_font)
        font_layout.addWidget(self.select_font_btn)
        watermark_layout.addLayout(font_layout)
        
        watermark_group.setLayout(watermark_layout)
        main_layout.addWidget(watermark_group)
        
        # 옵션 체크박스
        options_group = QGroupBox("처리 옵션")
        options_layout = QVBoxLayout()
        
        self.apply_enhance = QCheckBox("이미지 화질 개선 적용")
        self.apply_enhance.setChecked(True)
        self.apply_enhance.stateChanged.connect(self.update_settings)
        options_layout.addWidget(self.apply_enhance)
        
        self.apply_square = QCheckBox("정사각형으로 자동 크롭")
        self.apply_square.setChecked(True)
        self.apply_square.stateChanged.connect(self.update_settings)
        options_layout.addWidget(self.apply_square)
        
        self.apply_watermark = QCheckBox("워터마크 적용")
        self.apply_watermark.setChecked(True)
        self.apply_watermark.stateChanged.connect(self.update_settings)
        options_layout.addWidget(self.apply_watermark)
        
        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)
        
        # 테스트 버튼
        test_layout = QHBoxLayout()
        self.test_image_btn = QPushButton("테스트 이미지 선택 및 미리보기")
        self.test_image_btn.clicked.connect(self.test_image_processing)
        test_layout.addWidget(self.test_image_btn)
        main_layout.addLayout(test_layout)
        
        self.setLayout(main_layout)
        
    def load_settings_from_json(self):
        """JSON 파일에서 설정을 로드합니다."""
        from image_processor import load_image_processor_settings
        settings = load_image_processor_settings()
        if settings:
            self.apply_settings(settings)
            print("설정을 성공적으로 로드했습니다.")
        else:
            print("설정 파일을 찾을 수 없거나 로드할 수 없습니다.")

    # 색상 선택 메서드 추가
    def select_text_color(self):
        """텍스트 색상 선택 다이얼로그"""
        color = QColorDialog.getColor(QColor(255, 255, 255), self, "워터마크 텍스트 색상 선택")
        if color.isValid():
            self.text_color = (color.red(), color.green(), color.blue())
            self.text_color_preview.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); border: 1px solid #cccccc;")
            self.update_settings()

    def select_shadow_color(self):
        """그림자 색상 선택 다이얼로그"""
        color = QColorDialog.getColor(QColor(0, 0, 0), self, "워터마크 그림자 색상 선택")
        if color.isValid():
            self.shadow_color = (color.red(), color.green(), color.blue())
            self.shadow_color_preview.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); border: 1px solid #cccccc;")
            self.update_settings()
        
    def update_settings(self):
        """설정 값이 변경될 때 호출되는 함수"""
        # 슬라이더 값 업데이트
        brightness = self.brightness_slider.value() / 100
        contrast = self.contrast_slider.value() / 100
        color = self.color_slider.value() / 100
        sharpness = self.sharpness_slider.value() / 100
        opacity = self.opacity_slider.value() / 100
        font_size = self.font_size_spin.value()
        
        # 워터마크 스타일 및 각도 값 가져오기
        style_index = self.watermark_style_combo.currentIndex()
        style_map = {
            0: "diagonal_repeat",
            1: "grid",
            2: "corner",
            3: "center",
            4: "custom_angle"
        }
        watermark_style = style_map.get(style_index, "diagonal_repeat")
        
        angle = self.angle_slider.value()
        self.angle_value.setText(f"{angle}°")
        
        # 라벨 업데이트
        self.brightness_value.setText(f"{brightness:.1f}")
        self.contrast_value.setText(f"{contrast:.1f}")
        self.color_value.setText(f"{color:.1f}")
        self.sharpness_value.setText(f"{sharpness:.1f}")
        self.opacity_value.setText(f"{opacity:.1f}")

        # 텍스트 색상 가져오기 - 수정된 부분
        text_color_value = getattr(self, 'text_color', '#FFFFFF')
        
        # 텍스트 색상이 튜플인 경우 HEX 문자열로 변환
        if isinstance(text_color_value, tuple) and len(text_color_value) == 3:
            # RGB 튜플을 HEX 문자열로 변환
            text_color_value = f"#{text_color_value[0]:02x}{text_color_value[1]:02x}{text_color_value[2]:02x}"
        
        # 텍스트 색상이 문자열이 아니거나 '#'으로 시작하지 않으면 기본값 사용
        if not isinstance(text_color_value, str) or not text_color_value.startswith('#'):
            text_color_value = '#FFFFFF'
        
        # 설정 딕셔너리 생성
        settings = {
            'brightness': brightness,
            'contrast': contrast,
            'color': color,
            'sharpness': sharpness,
            'watermark_text': self.watermark_text.text(),
            'font_path': getattr(self, 'font_path', None),
            'font_size': font_size,
            'opacity': opacity,
            'watermark_style': watermark_style,
            'watermark_angle': angle,
            'text_color': text_color_value,  # 텍스트 색상 추가 (HEX 문자열 형식)
            'apply_enhance': self.apply_enhance.isChecked(),
            'apply_square': self.apply_square.isChecked(),
            'apply_watermark': self.apply_watermark.isChecked(),
            'use_shadow': self.use_shadow_check.isChecked()
        }
        
        # 폰트 경로가 있으면 추가
        if hasattr(self, 'font_path') and self.font_path:
            settings['font_path'] = self.font_path
        
        # 시그널 발생
        self.settings_changed.emit(settings)
        return settings
        
    def select_font(self):
        """폰트 파일 선택 다이얼로그"""
        from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QListWidget, QPushButton, 
                                    QHBoxLayout, QLabel, QSplitter)
        from PyQt5.QtGui import QFont, QPixmap, QPainter, QColor, QFontDatabase
        from PyQt5.QtCore import Qt, QSize
        
        # 이미지 처리기 인스턴스 생성
        from image_processor import ImageProcessor
        processor = ImageProcessor()
        
        # 시스템 폰트 목록 가져오기
        fonts = processor.list_available_fonts()
        
        if not fonts:
            QMessageBox.warning(self, "경고", "시스템에서 사용 가능한 폰트를 찾을 수 없습니다.")
            
            # 기존 파일 선택 다이얼로그 표시
            font_path, _ = QFileDialog.getOpenFileName(
                self, "폰트 파일 선택", "", "폰트 파일 (*.ttf *.otf)"
            )
            if font_path:
                self.font_path = font_path
                self.font_path_label.setText(os.path.basename(font_path))
                self.font_path_label.setStyleSheet("color: black;")
                self.update_settings()
            return
        
        # 폰트 선택 대화상자 생성
        dialog = QDialog(self)
        dialog.setWindowTitle("시스템 폰트 선택")
        dialog.resize(700, 500)  # 대화상자 크기 증가
        
        layout = QVBoxLayout()
        
        # 스플리터 추가 (목록과 미리보기 영역 분리)
        splitter = QSplitter(Qt.Horizontal)
        
        # 폰트 목록 위젯
        font_list = QListWidget()
        for font_path in fonts:
            font_list.addItem(os.path.basename(font_path))
        
        # 미리보기 영역
        preview_widget = QLabel()
        preview_widget.setFixedSize(300, 300)  # 300x300 픽셀 크기
        preview_widget.setAlignment(Qt.AlignCenter)
        preview_widget.setStyleSheet("background-color: white; border: 1px solid #cccccc;")
        
        # 미리보기 텍스트 (워터마크 텍스트 사용)
        preview_text = self.watermark_text.text() or "LUXBOOM"
        
        # 스플리터에 위젯 추가
        splitter.addWidget(font_list)
        splitter.addWidget(preview_widget)
        
        # 스플리터 비율 설정
        splitter.setSizes([300, 300])
        
        layout.addWidget(splitter)
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        select_btn = QPushButton("선택")
        cancel_btn = QPushButton("취소")
        button_layout.addWidget(select_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        # 폰트 미리보기 함수
        def update_preview(font_path):
            try:
                # 폰트 ID 등록
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id < 0:
                    preview_widget.setText(f"폰트 미리보기 불가\n{os.path.basename(font_path)}")
                    return
                    
                # 등록된 폰트 패밀리 가져오기
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if not font_families:
                    preview_widget.setText(f"폰트 패밀리 없음\n{os.path.basename(font_path)}")
                    return
                    
                font_family = font_families[0]
                
                # 미리보기 이미지 생성
                pixmap = QPixmap(300, 300)
                pixmap.fill(Qt.white)
                
                painter = QPainter(pixmap)
                
                # 폰트 설정
                font = QFont(font_family)
                font.setPointSize(24)  # 큰 글자 크기
                painter.setFont(font)
                
                # 텍스트 그리기
                painter.setPen(QColor(0, 0, 0))
                painter.drawText(pixmap.rect(), Qt.AlignCenter, f"{preview_text}\n\nAaBbCcDd\n1234567890")
                
                # 폰트 이름 표시
                small_font = QFont()
                small_font.setPointSize(10)
                painter.setFont(small_font)
                painter.drawText(10, 290, os.path.basename(font_path))
                
                painter.end()
                
                # 미리보기 표시
                preview_widget.setPixmap(pixmap)
                
            except Exception as e:
                preview_widget.setText(f"미리보기 오류: {str(e)}")
        
        # 목록 선택 변경 시 미리보기 업데이트
        def on_selection_changed():
            selected_items = font_list.selectedItems()
            if selected_items:
                selected_index = font_list.currentRow()
                if 0 <= selected_index < len(fonts):
                    font_path = fonts[selected_index]
                    update_preview(font_path)
        
        # 시그널 연결
        font_list.itemSelectionChanged.connect(on_selection_changed)
        select_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        # 초기 선택 설정 (첫 번째 항목)
        if font_list.count() > 0:
            font_list.setCurrentRow(0)
        
        # 대화상자 표시
        result = dialog.exec_()
        
        if result == QDialog.Accepted and font_list.currentItem():
            selected_font_name = font_list.currentItem().text()
            selected_index = font_list.currentRow()
            
            if 0 <= selected_index < len(fonts):
                font_path = fonts[selected_index]
                self.font_path = font_path
                self.font_path_label.setText(selected_font_name)
                self.font_path_label.setStyleSheet("color: black;")
                self.update_settings()
                print(f"선택된 폰트: {font_path}")
                
    def save_settings_to_json(self):
        """현재 설정을 JSON 파일로 저장합니다."""

        # 현재 설정 불러오기
        settings = self.update_settings()  # 설정값 딕셔너리로 리턴
        
        # 설정 저장
        if save_image_processor_settings(settings):
            QMessageBox.information(self, "저장 완료", "설정이 성공적으로 저장되었습니다.")
        else:
            QMessageBox.critical(self, "저장 실패", "설정 저장 중 오류가 발생했습니다.")
                
    
    def show_watermark_style_preview(self):
        """워터마크 스타일 미리보기 대화상자 표시"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QGridLayout, QPushButton, QScrollArea
        from PyQt5.QtGui import QPixmap, QImage
        from PyQt5.QtCore import Qt
        import numpy as np
        
        # 미리보기 대화상자 생성
        dialog = QDialog(self)
        dialog.setWindowTitle("워터마크 스타일 미리보기")
        dialog.resize(800, 600)
        
        layout = QVBoxLayout()
        
        # 스크롤 영역 추가
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        # 미리보기 그리드 컨테이너
        container = QWidget()
        grid_layout = QGridLayout(container)
        
        # 테스트 이미지 생성 (컬러 그라데이션)
        width, height = 300, 200
        image = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 그라데이션 생성
        for y in range(height):
            for x in range(width):
                image[y, x, 0] = int(255 * x / width)  # R
                image[y, x, 1] = int(255 * y / height)  # G
                image[y, x, 2] = 128  # B
        
        # PIL 이미지로 변환
        from PIL import Image
        pil_image = Image.fromarray(image)
        
        # 이미지 처리기 생성
        from image_processor import ImageProcessor
        processor = ImageProcessor(
            watermark_text=self.watermark_text.text(),
            font_path=getattr(self, 'font_path', None),
            font_size=self.font_size_spin.value(),
            opacity=self.opacity_slider.value() / 100
        )
        
        # 각 스타일별 미리보기 생성
        styles = [
            ("diagonal_repeat", "대각선 반복 패턴"),
            ("grid", "격자 패턴"),
            ("corner", "모서리 워터마크"),
            ("center", "중앙 워터마크"),
            ("custom_angle", "사용자 지정 각도")
        ]
        
        for i, (style_id, style_name) in enumerate(styles):
            # 워터마크 스타일 설정
            processor.set_watermark_options(style=style_id)
            
            # 사용자 지정 각도인 경우 각도 설정
            if style_id == "custom_angle":
                processor.set_watermark_angle(self.angle_slider.value())
            
            # 워터마크 적용
            processed_image = processor.add_watermark(pil_image.copy().convert('RGBA'))
            
            # PIL 이미지를 QPixmap으로 변환
            qimage = QImage(processed_image.tobytes(), 
                           processed_image.width, 
                           processed_image.height, 
                           QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)
            
            # 미리보기 라벨 생성
            preview_label = QLabel()
            preview_label.setPixmap(pixmap)
            preview_label.setAlignment(Qt.AlignCenter)
            
            # 스타일 이름 라벨
            style_label = QLabel(style_name)
            style_label.setAlignment(Qt.AlignCenter)
            
            # 그리드에 추가
            row, col = i // 2, i % 2
            grid_layout.addWidget(style_label, row * 2, col)
            grid_layout.addWidget(preview_label, row * 2 + 1, col)
        
        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)
        
        # 닫기 버튼
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.setLayout(layout)
        dialog.exec_()
        
    def apply_settings(self, settings):
        """
        저장된 설정을 UI에 적용합니다.
        
        Args:
            settings (dict): 적용할 설정 딕셔너리
        """
        try:
            # 밝기, 대비, 색상, 선명도 설정
            self.brightness_slider.setValue(int(settings.get('brightness', 1.0) * 100))
            self.contrast_slider.setValue(int(settings.get('contrast', 1.0) * 100))
            self.color_slider.setValue(int(settings.get('color', 1.0) * 100))
            self.sharpness_slider.setValue(int(settings.get('sharpness', 1.0) * 100))
            
            # 워터마크 텍스트 설정
            self.watermark_text.setText(settings.get('watermark_text', 'LUXBOOM'))
            
            # 폰트 크기 설정
            self.font_size_spin.setValue(settings.get('font_size', 80))
            
            # 투명도 설정
            self.opacity_slider.setValue(int(settings.get('opacity', 0.3) * 100))
            
            # 체크박스 설정
            self.apply_enhance.setChecked(settings.get('apply_enhance', True))
            self.apply_square.setChecked(settings.get('apply_square', False))
            self.apply_watermark.setChecked(settings.get('apply_watermark', False))
            self.use_shadow_check.setChecked(settings.get('use_shadow', False))
            
            # 폰트 경로 설정 (UI에 표시 가능한 컨트롤이 있다면)
            if hasattr(self, 'font_path_label') and settings.get('font_path'):
                self.font_path = settings.get('font_path')
                self.font_path_label.setText(os.path.basename(settings.get('font_path')))
                self.font_path_label.setStyleSheet("color: black;")
                
            # 텍스트 색상 설정
            if 'text_color' in settings:
                text_color = settings.get('text_color')
                if isinstance(text_color, str) and text_color.startswith('#'):
                    # HEX 문자열을 RGB 튜플로 변환
                    r = int(text_color[1:3], 16)
                    g = int(text_color[3:5], 16)
                    b = int(text_color[5:7], 16)
                    self.text_color = (r, g, b)
                    self.text_color_preview.setStyleSheet(f"background-color: {text_color}; border: 1px solid #cccccc;")
                
        except Exception as e:
            print(f"설정 적용 중 오류 발생: {e}")
            
    def test_image_processing(self):
        """테스트 이미지 선택 및 처리 미리보기"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import Qt
        import os
        import tempfile

        # 이미지 파일 선택
        image_path, _ = QFileDialog.getOpenFileName(
            self, "테스트 이미지 선택", "", "이미지 파일 (*.jpg *.jpeg *.png *.webp *.bmp)"
        )
        if not image_path:
            return

        # 현재 설정으로 이미지 처리기 생성
        from image_processor import ImageProcessor

        font_size = self.font_size_spin.value()
        print(f"현재 설정된 폰트 크기: {font_size}")

        processor = ImageProcessor(
            watermark_text=self.watermark_text.text(),
            font_path=getattr(self, 'font_path', None),
            font_size=font_size,
            opacity=self.opacity_slider.value() / 100
        )

        processor.set_enhancement_factors(
            brightness=self.brightness_slider.value() / 100,
            contrast=self.contrast_slider.value() / 100,
            color=self.color_slider.value() / 100,
            sharpness=self.sharpness_slider.value() / 100
        )

        # 워터마크 스타일 및 각도 설정
        style_index = self.watermark_style_combo.currentIndex()
        style_map = {
            0: "diagonal_repeat",
            1: "grid",
            2: "corner",
            3: "center",
            4: "custom_angle"
        }
        watermark_style = style_map.get(style_index, "diagonal_repeat")

        processor.set_watermark_options(
            text=self.watermark_text.text(),
            font_size=font_size,
            opacity=self.opacity_slider.value() / 100,
            style=watermark_style
        )

        if watermark_style == "custom_angle":
            processor.set_watermark_angle(self.angle_slider.value())

        # 임시 경로
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, "processed_preview.jpg")

        # 이미지 처리
        success = processor.process_existing_image(
            image_path,
            output_path,
            apply_watermark=self.apply_watermark.isChecked(),
            make_square=self.apply_square.isChecked(),
            enhance_image=self.apply_enhance.isChecked()
        )

        if success:
            # 미리보기 다이얼로그
            preview_dialog = QDialog(self)
            preview_dialog.setWindowTitle("처리된 이미지 미리보기")
            preview_dialog.resize(1200, 600)

            layout = QVBoxLayout()
            image_row = QHBoxLayout()

            # 원본 이미지
            original_label = QLabel("원본 이미지:")
            original_pixmap = QPixmap(image_path)
            original_img = QLabel()
            original_img.setAlignment(Qt.AlignCenter)
            if not original_pixmap.isNull():
                original_img.setPixmap(original_pixmap.scaled(550, 550, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            # 처리된 이미지
            processed_label = QLabel("처리된 이미지:")
            processed_pixmap = QPixmap(output_path)
            processed_img = QLabel()
            processed_img.setAlignment(Qt.AlignCenter)
            if not processed_pixmap.isNull():
                processed_img.setPixmap(processed_pixmap.scaled(550, 550, Qt.KeepAspectRatio, Qt.SmoothTransformation))

            # 각 이미지와 라벨을 세로로 묶기
            original_layout = QVBoxLayout()
            original_layout.addWidget(original_label)
            original_layout.addWidget(original_img)

            processed_layout = QVBoxLayout()
            processed_layout.addWidget(processed_label)
            processed_layout.addWidget(processed_img)

            image_row.addLayout(original_layout)
            image_row.addLayout(processed_layout)
            layout.addLayout(image_row)

            preview_dialog.setLayout(layout)
            preview_dialog.exec_()
