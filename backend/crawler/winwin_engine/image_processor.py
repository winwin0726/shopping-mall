from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageOps
import os
import io
import json
import requests
import numpy as np

def save_image_processor_settings(settings, file_name="image_processor_settings.json"):
    """이미지 프로세서 설정을 JSON 파일에 저장"""
    try:
        settings_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings')
        os.makedirs(settings_dir, exist_ok=True)
        full_path = os.path.join(settings_dir, file_name)
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        print(f"[OK] 설정 저장 완료: {full_path}")
        return True
    except Exception as e:
        print(f"[ERR] 설정 저장 오류: {e}")
        return False


def load_image_processor_settings(file_name="image_processor_settings.json"):
    """저장된 이미지 프로세서 설정을 불러옴"""
    try:
        settings_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings')
        full_path = os.path.join(settings_dir, file_name)
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            print(f"[OK] 설정 로드 완료: {full_path}")
            return settings
        else:
            print(f"[!] 설정 파일 없음: {full_path}")
            return None
    except Exception as e:
        print(f"[ERR] 설정 로드 오류: {e}")
        return None

class ImageProcessor:
    def __init__(self, watermark_text="LUXBOOM", font_path=None, font_size=80, opacity=0.3, 
                     text_color=(255, 255, 255), shadow_color=(0, 0, 0)):
            """
            이미지 처리 클래스 초기화
            
            Args:
                watermark_text (str): 워터마크로 사용할 텍스트
                font_path (str): 폰트 파일 경로 (None이면 기본 폰트 사용)
                font_size (int): 폰트 크기
                opacity (float): 워터마크 투명도 (0.0 ~ 1.0)
                text_color (tuple): 워터마크 텍스트 색상 (R, G, B)
                shadow_color (tuple): 워터마크 그림자 색상 (R, G, B)
            """
            self.watermark_text = watermark_text
            self.font_path = font_path
            self.font_size = font_size
            self.opacity = opacity
            self.watermark_style = "diagonal_repeat"  # 기본 스타일: 대각선 반복
            self.watermark_angle = 45  # 기본 각도: 45도
            self.text_color = text_color  # 워터마크 텍스트 색상
            self.shadow_color = shadow_color  # 워터마크 그림자 색상
            self.use_shadow = True  # 그림자 사용 여부
            
            # 기본 설정값
            self.brightness_factor = 1.0  # 밝기 조정 (1.0이 원본)
            self.contrast_factor = 1.0    # 대비 조정 (1.0이 원본)
            self.color_factor = 1.0       # 색상 조정 (1.0이 원본)0
            self.sharpness_factor = 1.0   # 선명도 조정 (1.0이 원본)
        
    def download_and_process_image(self, url, output_path, apply_watermark=True, 
                                  make_square=True, enhance_image=True):
        """
        이미지를 다운로드하고 처리한 후 저장
        
        Args:
            url (str): 이미지 URL
            output_path (str): 저장할 파일 경로
            apply_watermark (bool): 워터마크 적용 여부
            make_square (bool): 정사각형으로 크롭 여부
            enhance_image (bool): 이미지 화질 개선 여부
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 이미지 다운로드
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return False
                
            # 이미지 객체 생성
            img = Image.open(io.BytesIO(response.content))
            
            # 이미지 처리 적용
            if enhance_image:
                img = self.enhance_image(img)
                
            if make_square:
                img = self.crop_to_square(img)
                
            if apply_watermark:
                img = self.add_watermark(img)
            
            # 이미지 저장
            img.save(output_path, quality=95)
            return True
            
        except Exception as e:
            print(f"이미지 처리 오류: {str(e)}")
            return False
            
    def process_existing_image(self, input_path, output_path=None, apply_watermark=True, 
                              make_square=True, enhance_image=True):
        """
        기존 이미지 파일을 처리
        
        Args:
            input_path (str): 입력 이미지 경로
            output_path (str): 출력 이미지 경로 (None이면 입력 경로에 덮어씀)
            apply_watermark (bool): 워터마크 적용 여부
            make_square (bool): 정사각형으로 크롭 여부
            enhance_image (bool): 이미지 화질 개선 여부
            
        Returns:
            bool: 성공 여부
        """
        if output_path is None:
            output_path = input_path
            
        try:
            # 이미지 열기
            img = Image.open(input_path)
            
            # 이미지 처리 적용
            if enhance_image:
                img = self.enhance_image(img)
                
            if make_square:
                img = self.crop_to_square(img)
                
            if apply_watermark:
                img = self.add_watermark(img)
            
            # 이미지 저장
            img.save(output_path, quality=95)
            return True
            
        except Exception as e:
            print(f"이미지 처리 오류: {str(e)}")
            return False
    
    def enhance_image(self, img):
        """
        이미지 화질 개선
        
        Args:
            img (PIL.Image): 입력 이미지
            
        Returns:
            PIL.Image: 개선된 이미지
        """
        # 밝기 조정
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(self.brightness_factor)
        
        # 대비 조정
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(self.contrast_factor)
        
        # 색상 조정
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(self.color_factor)
        
        # 선명도 조정
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(self.sharpness_factor)
        
        return img
    
    def crop_to_square(self, img):
        """
        이미지를 정사각형으로 크롭
        
        Args:
            img (PIL.Image): 입력 이미지
            
        Returns:
            PIL.Image: 정사각형으로 크롭된 이미지
        """
        width, height = img.size
        
        # 이미 정사각형이면 그대로 반환
        if width == height:
            return img
            
        # 짧은 쪽을 기준으로 정사각형 크롭
        size = min(width, height)
        
        # 중앙에서 크롭
        left = (width - size) // 2
        top = (height - size) // 2
        right = left + size
        bottom = top + size
        
        return img.crop((left, top, right, bottom))
    
    # 워터마크 옵션 설정 메서드 수정
    def set_watermark_options(self, text=None, font_path=None, font_size=None, opacity=None, 
                                 style=None, text_color=None, shadow_color=None, use_shadow=None):
            """
            워터마크 옵션 설정
            
            Args:
                text (str, optional): 워터마크 텍스트
                font_path (str, optional): 폰트 파일 경로
                font_size (int, optional): 폰트 크기
                opacity (float, optional): 투명도 (0.0 ~ 1.0)
                style (str, optional): 워터마크 스타일 ('diagonal_repeat', 'grid', 'corner', 'center', 'custom_angle')
                text_color (tuple, optional): 워터마크 텍스트 색상 (R, G, B)
                shadow_color (tuple, optional): 워터마크 그림자 색상 (R, G, B)
                use_shadow (bool, optional): 그림자 사용 여부
            """
            if text is not None:
                self.watermark_text = text
            if font_path is not None:
                self.font_path = font_path
            if font_size is not None:
                self.font_size = font_size
            if opacity is not None:
                self.opacity = opacity
            if style is not None:
                self.watermark_style = style
            if text_color is not None:
                self.text_color = text_color
            if shadow_color is not None:
                self.shadow_color = shadow_color
            if use_shadow is not None:
                self.use_shadow = use_shadow
    
    # 워터마크 각도 설정 메서드 추가
    def set_watermark_angle(self, angle):
        """
        워터마크 각도 설정 (custom_angle 스타일에서 사용)
        
        Args:
            angle (float): 각도 (도 단위)
        """
        self.watermark_angle = angle
    
    def add_watermark(self, img):
        """
        이미지에 워터마크 추가
        
        Args:
            img (PIL.Image): 입력 이미지
            
        Returns:
            PIL.Image: 워터마크가 추가된 이미지
        """
        # RGBA 모드로 변환 (투명도 지원)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
            
        # 워터마크용 투명 레이어 생성
        watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark)
        
        # 폰트 설정
        try:
            # 폰트 크기 디버깅 정보 출력
            print(f"워터마크 적용 시 폰트 크기: {self.font_size}")
            
            if self.font_path and os.path.exists(self.font_path):
                # 사용자 지정 폰트 사용
                font = ImageFont.truetype(self.font_path, self.font_size)
                print(f"사용자 지정 폰트 로드: {self.font_path}, 크기: {self.font_size}")
            else:
                # 기본 폰트 사용 - 시스템에 있는 폰트 중 하나를 사용
                try:
                    # Windows 시스템 폰트 시도
                    font = ImageFont.truetype("arial.ttf", self.font_size)
                    print(f"Windows 폰트 로드: arial.ttf, 크기: {self.font_size}")
                except:
                    try:
                        # macOS/Linux 시스템 폰트 시도
                        font = ImageFont.truetype("DejaVuSans.ttf", self.font_size)
                        print(f"Linux 폰트 로드: DejaVuSans.ttf, 크기: {self.font_size}")
                    except:
                        # 마지막 대안으로 기본 폰트 사용
                        default_font = ImageFont.load_default()
                        print("기본 폰트 로드 (크기 조정 불가)")
                        font = default_font
        except Exception as e:
            print(f"폰트 로딩 오류: {e}")
            # 기본 폰트 사용
            font = ImageFont.load_default()
        
        # 텍스트 크기 계산
        try:
            # Pillow 9.0.0 이상 버전용
            left, top, right, bottom = draw.textbbox((0, 0), self.watermark_text, font=font)
            text_width = right - left
            text_height = bottom - top
        except AttributeError:
            # Pillow 9.0.0 이전 버전용
            text_width, text_height = draw.textsize(self.watermark_text, font=font)
        
        # 텍스트 색상 설정 - 수정된 부분
        text_color_rgb = getattr(self, 'text_color', (255, 255, 255))
        # 투명도 적용
        text_color_rgba = (*text_color_rgb, int(255 * self.opacity))
        
        # 그림자 색상 설정 - 수정된 부분
        shadow_color_rgb = getattr(self, 'shadow_color', (0, 0, 0))
        shadow_color_rgba = (*shadow_color_rgb, int(255 * self.opacity * 0.5))
        
        # 디버깅 정보 출력
        print(f"워터마크 텍스트 색상: {text_color_rgb} -> RGBA: {text_color_rgba}")
        print(f"워터마크 그림자 색상: {shadow_color_rgb} -> RGBA: {shadow_color_rgba}")
        
        # 워터마크 스타일에 따라 다른 방식으로 적용
        if self.watermark_style == "diagonal_repeat":
            # 대각선 반복 패턴 (이미지 전체에 반복)
            spacing = max(text_width, text_height) * 2  # 텍스트 간격
            angle = 45  # 대각선 각도
            
            # 이미지 전체를 덮을 만큼 반복
            for y in range(-img.height, img.height * 2, spacing):
                for x in range(-img.width, img.width * 2, spacing):
                    # 회전된 텍스트 그리기
                    txt = Image.new('RGBA', (text_width + 20, text_height + 20), (0, 0, 0, 0))
                    d = ImageDraw.Draw(txt)
                    
                    # 그림자 추가 (선택적)
                    if self.use_shadow:
                        d.text((12, 12), self.watermark_text, font=font, fill=shadow_color_rgba)
                    
                    # 텍스트 그리기
                    d.text((10, 10), self.watermark_text, font=font, fill=text_color_rgba)
                    
                    # 텍스트 회전
                    rotated = txt.rotate(angle, expand=True)
                    
                    # 회전된 텍스트 붙이기
                    watermark.paste(rotated, (x, y), rotated)
        
        elif self.watermark_style == "grid":
            # 격자 패턴 (수평/수직 반복)
            spacing_x = text_width * 2
            spacing_y = text_height * 2
            
            for y in range(0, img.height, spacing_y):
                for x in range(0, img.width, spacing_x):
                    # 그림자 추가 (선택적)
                    if self.use_shadow:
                        draw.text((x+2, y+2), self.watermark_text, font=font, fill=shadow_color_rgba)
                    
                    # 텍스트 그리기
                    draw.text((x, y), self.watermark_text, font=font, fill=text_color_rgba)
        
        elif self.watermark_style == "corner":
            # 모서리에 워터마크 (오른쪽 하단)
            padding = 20
            position = (img.width - text_width - padding, img.height - text_height - padding)
            
            # 그림자 추가 (선택적)
            if self.use_shadow:
                draw.text((position[0]+2, position[1]+2), self.watermark_text, font=font, fill=shadow_color_rgba)
            
            # 텍스트 그리기
            draw.text(position, self.watermark_text, font=font, fill=text_color_rgba)
        
        elif self.watermark_style == "center":
            # 중앙에 큰 워터마크
            position = ((img.width - text_width) // 2, (img.height - text_height) // 2)
            
            # 그림자 추가 (선택적)
            if self.use_shadow:
                draw.text((position[0]+2, position[1]+2), self.watermark_text, font=font, fill=shadow_color_rgba)
            
            # 텍스트 그리기
            draw.text(position, self.watermark_text, font=font, fill=text_color_rgba)
        
        elif self.watermark_style == "custom_angle":
            # 사용자 지정 각도로 중앙에 워터마크
            angle = self.watermark_angle  # 사용자 지정 각도
            
            # 중앙에 텍스트 생성
            txt = Image.new('RGBA', (text_width + 40, text_height + 40), (0, 0, 0, 0))
            d = ImageDraw.Draw(txt)
            
            # 그림자 추가 (선택적)
            if self.use_shadow:
                d.text((22, 22), self.watermark_text, font=font, fill=shadow_color_rgba)
            
            # 텍스트 그리기
            d.text((20, 20), self.watermark_text, font=font, fill=text_color_rgba)
            
            # 텍스트 회전
            rotated = txt.rotate(angle, expand=True)
            
            # 회전된 텍스트를 중앙에 배치
            position = ((img.width - rotated.width) // 2, (img.height - rotated.height) // 2)
            watermark.paste(rotated, position, rotated)
        
        else:
            # 기본 워터마크 스타일 (원래 코드와 유사한 대각선 패턴)
            spacing_x = text_width + 50  # 텍스트 사이 가로 간격
            spacing_y = text_height + 30  # 텍스트 사이 세로 간격
            
            # 대각선 패턴으로 워터마크 그리기
            angle = 30  # 대각선 각도 (조절 가능)
            
            # 이미지 크기에 따라 필요한 줄 수 계산
            num_lines = max(5, min(10, int(img.height / spacing_y)))  # 5~10줄 사이
            
            # 각 줄마다 워터마크 그리기
            for line in range(num_lines):
                # 시작 위치 계산 (대각선 패턴을 위해 각 줄마다 시작점 조정)
                start_y = -text_height + (img.height / num_lines) * line
                
                # 각 줄에 여러 개의 워터마크 배치
                x_offset = 0
                if line % 2 == 1:  # 홀수 줄은 약간 오프셋 적용
                    x_offset = spacing_x / 2
                
                # 한 줄에 여러 개의 워터마크 배치
                x_pos = -text_width + x_offset
                while x_pos < img.width + text_width:
                    y_pos = start_y + (x_pos + text_width) * np.tan(np.radians(angle))
                    
                    # 워터마크가 이미지 영역 내에 있는지 확인
                    if -text_height <= y_pos <= img.height:
                        # 그림자 추가 (선택적)
                        if self.use_shadow:
                            draw.text((x_pos+2, y_pos+2), self.watermark_text, font=font, 
                                     fill=shadow_color_rgba)
                        
                        # 텍스트 그리기
                        draw.text((x_pos, y_pos), self.watermark_text, font=font, 
                                 fill=text_color_rgba)
                    
                    x_pos += spacing_x
        
        # 원본 이미지와 워터마크 합성
        return Image.alpha_composite(img, watermark).convert('RGB')
        
    def list_available_fonts(self):
        """
        시스템에서 사용 가능한 폰트 목록을 반환합니다.
        """
        import os
        
        font_dirs = []
        fonts = []
        
        try:
            # Windows 폰트 디렉토리
            if os.name == 'nt':
                font_dirs.append(os.path.join(os.environ['WINDIR'], 'Fonts'))
                
                # 추가 Windows 폰트 디렉토리
                user_fonts = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Windows', 'Fonts')
                if os.path.exists(user_fonts):
                    font_dirs.append(user_fonts)
            
            # macOS 폰트 디렉토리
            elif os.name == 'posix' and hasattr(os, 'uname') and os.uname().sysname == 'Darwin':
                font_dirs.extend([
                    '/Library/Fonts',
                    '/System/Library/Fonts',
                    os.path.expanduser('~/Library/Fonts')
                ])
            
            # Linux 폰트 디렉토리
            elif os.name == 'posix':
                font_dirs.extend([
                    '/usr/share/fonts',
                    '/usr/local/share/fonts',
                    os.path.expanduser('~/.fonts')
                ])
            
            # 폰트 파일 찾기
            for font_dir in font_dirs:
                if os.path.exists(font_dir):
                    print(f"폰트 디렉토리 검색: {font_dir}")
                    for file in os.listdir(font_dir):
                        if file.lower().endswith(('.ttf', '.otf')):
                            font_path = os.path.join(font_dir, file)
                            fonts.append(font_path)
                            print(f"폰트 발견: {file}")
            
            print(f"총 {len(fonts)}개의 폰트를 찾았습니다.")
            return fonts
        
        except Exception as e:
            print(f"폰트 검색 중 오류 발생: {e}")
            return []

    def set_system_font(self, font_name):
        """
        시스템에 설치된 폰트를 이름으로 설정합니다.
        
        Args:
            font_name (str): 폰트 이름 (예: 'Arial', 'Times New Roman')
        
        Returns:
            bool: 성공 여부
        """
        try:
            fonts = self.list_available_fonts()
            font_name_lower = font_name.lower()
            
            # 폰트 이름으로 검색
            for font_path in fonts:
                font_file = os.path.basename(font_path).lower()
                if font_name_lower in font_file:
                    self.font_path = font_path
                    print(f"폰트 설정 성공: {font_path}")
                    return True
            
            print(f"'{font_name}' 폰트를 찾을 수 없습니다.")
            return False
        except Exception as e:
            print(f"폰트 설정 중 오류 발생: {e}")
            return False       
    
    def set_enhancement_factors(self, brightness=None, contrast=None, color=None, sharpness=None):
        """
        이미지 개선 인자 설정
        
        Args:
            brightness (float): 밝기 인자 (None이면 변경 없음)
            contrast (float): 대비 인자 (None이면 변경 없음)
            color (float): 색상 인자 (None이면 변경 없음)
            sharpness (float): 선명도 인자 (None이면 변경 없음)
        """
        if brightness is not None:
            self.brightness_factor = brightness
        if contrast is not None:
            self.contrast_factor = contrast
        if color is not None:
            self.color_factor = color
        if sharpness is not None:
            self.sharpness_factor = sharpness
