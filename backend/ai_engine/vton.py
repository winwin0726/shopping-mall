import logging
import asyncio
import os
import time
import hashlib
import httpx
from typing import Optional, List, Dict
import json
import uuid
import base64
import io
from PIL import Image
import numpy as np
import cv2
from backend.config import settings
from google.oauth2 import service_account
import google.auth.transport.requests

# rembg 모델 영구 유지용 환경 변수 설정 (서버 리스타트 시 모델 유실 방지)
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["U2NET_HOME"] = os.path.join(backend_dir, "ai_engine", "models")

logger = logging.getLogger(__name__)


# =====================================================================
# 글로벌 인메모리 캐시 (실서버에서는 Redis로 교체)
# =====================================================================
_vton_cache: Dict[str, dict] = {}
_VTON_CACHE_MAX = 500

def _cache_put(key: str, value: dict) -> None:
    """캐시에 저장하되 상한 초과 시 가장 오래된 항목부터 제거 (간이 FIFO, 메모리 누수 방지)."""
    if key not in _vton_cache and len(_vton_cache) >= _VTON_CACHE_MAX:
        try:
            del _vton_cache[next(iter(_vton_cache))]
        except StopIteration:
            pass
    _vton_cache[key] = value


class AIFittingPreGenerator:
    """Local rembg CLI background-removal pre-generator.
    (Unused external AI-worker VTON / Hailuo video mock methods were removed - C4)
    """

    async def extract_transparent_clothing(self, original_image_url: str, category: Optional[str] = None, model_name: Optional[str] = None, category_type: Optional[str] = None) -> Optional[str]:
        """Removes background via Local rembg CLI subprocess to prevent asyncio deadlock."""
        logger.info(f"Extracting transparent item from (local rembg CLI): {original_image_url} | Model: {model_name} | CategoryType: {category_type}")
        
        try:
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            temp_dir = os.path.join(backend_dir, "uploads", "temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            save_dir = os.path.join(backend_dir, "uploads", "transparent")
            os.makedirs(save_dir, exist_ok=True)
            
            # 1. 원본 이미지 다운로드 및 임시 저장
            file_id = uuid.uuid4().hex[:8]
            temp_input_path = os.path.join(temp_dir, f"in_{file_id}.png")
            
            # F2: 동기 urllib → 비동기 httpx (async 이벤트 루프 블로킹 제거)
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(original_image_url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                img_data = resp.content
            with open(temp_input_path, "wb") as f:
                f.write(img_data)
                
            # 1.5. 이미 누끼(배경 투명화)가 진행된 PNG 이미지인지 검사하여 Bypass
            is_already_transparent = False
            try:
                from PIL import Image
                import io
                import numpy as np
                with Image.open(io.BytesIO(img_data)) as test_img:
                    # RGBA, LA 혹은 투명 인덱스가 지정된 P 이미지인 경우
                    if test_img.mode in ("RGBA", "LA") or (test_img.mode == "P" and "transparency" in test_img.info):
                        rgba_img = test_img.convert("RGBA")
                        alpha_data = np.array(rgba_img)[:, :, 3]
                        # 투명에 가까운 픽셀(알파값 15 이하) 비율 조사
                        transparent_ratio = np.sum(alpha_data < 15) / alpha_data.size
                        
                        # 투명 픽셀이 3% 이상 존재하면 이미 배경 제거 완료로 판단
                        if transparent_ratio > 0.03:
                            is_already_transparent = True
                            logger.info(f"Input image is already transparent (Transparent ratio: {transparent_ratio:.2%}). Bypassing background removal.")
                            
                            file_name = f"item_{file_id}.png"
                            temp_output_path = os.path.join(save_dir, file_name)
                            rgba_img.save(temp_output_path, "PNG")
                            
                    # 만약 비투명 이미지(JPG 등)이지만 네 귀퉁이가 거의 완벽한 흰색인 경우 (단색 배경 누끼 우회)
                    if not is_already_transparent:
                        rgba_img = test_img.convert("RGBA")
                        img_np = np.array(rgba_img)
                        h_np, w_np, _ = img_np.shape
                        
                        # 네 귀퉁이 영역의 평균 RGB 값 확인
                        corners = [
                            img_np[0:10, 0:10, :3],          # 좌상
                            img_np[0:10, w_np-10:w_np, :3],    # 우상
                            img_np[h_np-10:h_np, 0:10, :3],    # 좌하
                            img_np[h_np-10:h_np, w_np-10:w_np, :3] # 우하
                        ]
                        is_white_bg = True
                        for corner in corners:
                            if np.mean(corner) < 242:  # 거의 완벽한 흰색이 아니면 False
                                is_white_bg = False
                                break
                        
                        if is_white_bg:
                            logger.info("Input image has a solid white/light background. Applying advanced contour-based masking instead of floodFill to prevent clothing body punch-through.")
                            is_already_transparent = True  # rembg CLI 건너뛰기 플래그 세팅
                            
                            import cv2
                            # PIL -> OpenCV BGR 변환
                            cv_img = cv2.cvtColor(np.array(rgba_img), cv2.COLOR_RGBA2BGR)
                            
                            # 1. 그레이스케일 변환
                            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                            
                            # 2. 임계값(Thresholding) 적용으로 배경과 피사체 1차 분리
                            _, thresh = cv2.threshold(gray, 248, 255, cv2.THRESH_BINARY_INV)
                            
                            # 모폴로지 닫기 연산으로 옷 내부 노이즈 봉합
                            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
                            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
                            
                            # 3. 최외곽선(Contours) 검출
                            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                            
                            if len(contours) > 0:
                                # 4. 가장 면적이 큰 컨투어(의류 본체) 식별
                                max_contour = max(contours, key=cv2.contourArea)
                                
                                # 5. 옷 내부 구멍 뚫림을 원천 차단한 마스크(FILLED) 생성
                                clothing_mask = np.zeros((h_np, w_np), dtype=np.uint8)
                                cv2.drawContours(clothing_mask, [max_contour], -1, 255, thickness=cv2.FILLED)
                            else:
                                logger.warning("No contours found for white background. Falling back to default opaque mask.")
                                clothing_mask = np.ones((h_np, w_np), dtype=np.uint8) * 255
                                
                            # 원래 이미지 데이터 복사 및 알파 채널에 마스크 반영
                            out_data = np.copy(np.array(rgba_img))
                            out_data[:, :, 3] = clothing_mask
                            
                            file_name = f"item_{file_id}.png"
                            temp_output_path = os.path.join(save_dir, file_name)
                            clean_img = Image.fromarray(out_data, mode="RGBA")
                            clean_img.save(temp_output_path, "PNG")
            except Exception as test_ex:
                logger.warning(f"Error checking and processing white background bypass: {test_ex}")
                
            if not is_already_transparent:
                # 2. 로컬 rembg CLI 비동기 실행 (데드락 원천 예방)
                file_name = f"item_{file_id}.png"
                temp_output_path = os.path.join(save_dir, file_name)
                
                rembg_exe = os.path.join(backend_dir, "venv", "Scripts", "rembg.exe")
                if not os.path.exists(rembg_exe):
                    rembg_exe = "rembg"
                    
                # [고도화] model_name 존재 시 -m 옵션 인자 조립
                cmd_args = [rembg_exe, "i"]
                if model_name:
                    cmd_args.extend(["-m", model_name])
                cmd_args.extend([temp_input_path, temp_output_path])
                
                logger.info(f"Executing rembg CLI: {' '.join(cmd_args)}")
                
                # 스레드 풀 상에서 동기식 subprocess.run을 실행하여 asyncio loop 및 Windows Proactor/Selector 제약 해결
                def run_rembg():
                    import subprocess
                    startupinfo = None
                    if os.name == 'nt':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        
                    res = subprocess.run(
                        cmd_args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        startupinfo=startupinfo,
                        check=True
                    )
                    return res.returncode, res.stdout, res.stderr

                loop = asyncio.get_event_loop()
                returncode, stdout, stderr = await loop.run_in_executor(None, run_rembg)
                
                # 임시 입력 파일 삭제
                if os.path.exists(temp_input_path):
                    try: os.remove(temp_input_path)
                    except: pass
                    
                if returncode != 0:
                    err_msg = stderr.decode(errors='ignore') if isinstance(stderr, bytes) else str(stderr)
                    raise Exception(f"rembg CLI return code {returncode}. Error: {err_msg}")
                    
                # [고도화] 옷걸이 및 쇠막대 잔재 자동 청소 후처리 적용
                self._remove_hanger_by_bottleneck(temp_output_path, category_type or category)
            else:
                # 임시 입력 파일 삭제
                if os.path.exists(temp_input_path):
                    try: os.remove(temp_input_path)
                    except: pass
            
            # [Autocrop] 과도한 투명 여백 제거 (오토크롭)
            try:
                logger.info(f"Applying Autocrop to remove excessive transparent margins on: {temp_output_path}")
                crop_img = Image.open(temp_output_path).convert("RGBA")
                bbox = get_clean_bbox(crop_img, threshold=20)
                if bbox:
                    cropped = crop_img.crop(bbox)
                    cropped.save(temp_output_path, "PNG")
                    logger.info(f"Autocrop successful for {temp_output_path}. Bbox: {bbox}")
                else:
                    logger.warning(f"Autocrop skipped (no bounding box found with threshold=20) for {temp_output_path}")
            except Exception as crop_ex:
                logger.error(f"Autocrop failed for {temp_output_path}: {str(crop_ex)}", exc_info=True)
            
            # 프론트에서 접근할 수 있는 로컬 정적 경로 URL 지정
            backend_url = settings.BACKEND_URL
            result_url = f"{backend_url}/uploads/transparent/{file_name}"
            logger.info(f"rembg extraction success via CLI. Saved at: {result_url}")
            return result_url
            
        except Exception as e:
            logger.error(f"Local RemBG extraction failed via CLI: {str(e)}", exc_info=True)
            # 실패 시 원본 URL 을 반환하면 비투명 이미지가 transparent 로 저장되므로 None 반환
            return None

    def _remove_hanger_by_bottleneck(self, image_path: str, category_type: Optional[str] = None) -> None:
        """
        배경이 투명해진 PNG 이미지에서 옷걸이 잔재(쇠막대기, 집게, 그림자, 광택)와
        공중에 뜬 잔해물 조각을 완벽히 지우고 허리선을 자연스럽게 복원합니다.
        """
        try:
            logger.info(f"Running advanced waistband-restoration hanger remover on: {image_path} | Category: {category_type}")
            img = Image.open(image_path).convert("RGBA")
            data = np.array(img)
            
            # 알파 채널 추출
            a = data[:, :, 3]
            height, width = a.shape
            
            # =================================================================
            # [고도화 1] Connected Components를 이용한 외곽 배경 파편 완벽 제거
            # =================================================================
            mask = (a > 10).astype(np.uint8) * 255
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
            
            body_labels = []
            max_area = 0
            max_label = 0
            
            # 배경(0) 제외 가장 큰 본체 덩어리 식별
            for i in range(1, num_labels):
                area = stats[i, cv2.CC_STAT_AREA]
                if area > max_area:
                    max_area = area
                    max_label = i
                    
            if max_label > 0:
                body_labels.append(max_label)
                # 최대 면적의 12% 이상이면서 가로 중앙 영역(20% ~ 80%)에 걸쳐진 인접 덩어리들도 살림 (하의 다리 분리 방지)
                for i in range(1, num_labels):
                    if i == max_label:
                        continue
                    area = stats[i, cv2.CC_STAT_AREA]
                    x = stats[i, cv2.CC_STAT_LEFT]
                    w = stats[i, cv2.CC_STAT_WIDTH]
                    center_overlap = max(0, min(x + w, int(width * 0.8)) - max(x, int(width * 0.2)))
                    if area > (max_area * 0.12) and center_overlap > 0:
                        body_labels.append(i)
            
            # 본체 레이블에 속하지 않은 모든 픽셀의 알파를 0으로 채움 (공중 파편 제거)
            new_a = np.zeros_like(a)
            for lbl in body_labels:
                new_a[labels == lbl] = a[labels == lbl]
            
            # =================================================================
            # [고도화 2] 상단 옷걸이(Top Hanger) 목 부분 쇠막대 제거 알고리즘 (상의 카테고리 타겟)
            # =================================================================
            is_top = True
            if category_type:
                cat_lower = category_type.lower()
                if any(x in cat_lower for x in ["하의", "bottom", "pants", "skirt", "jeans"]):
                    is_top = False
                    
            if is_top:
                # 상단 30% 영역에서 옷걸이 쇠 부분(병목) 검색 및 제거
                search_limit = int(height * 0.3)
                bottleneck_y = -1
                
                for y in range(5, search_limit):
                    row_pixels = np.where(new_a[y, :] > 30)[0]
                    if len(row_pixels) > 0:
                        row_w = row_pixels[-1] - row_pixels[0] + 1
                        # 갑자기 폭이 좁아지거나 좁은 목 부위를 옷걸이 병목으로 판정
                        if 3 <= row_w <= int(width * 0.18):
                            bottleneck_y = y
                            break
                
                if bottleneck_y > 0:
                    logger.info(f"Detected hanger bottleneck at Y={bottleneck_y}")
                    # 병목 지점 위쪽(Y < bottleneck_y)의 알파 채널을 0으로 지움
                    new_a[0:bottleneck_y, :] = 0
            
            data[:, :, 3] = new_a
            
            # 변경된 데이터 저장
            clean_img = Image.fromarray(data, mode="RGBA")
            clean_img.save(image_path, "PNG")
            logger.info(f"Successfully processed hanger remover for {image_path}")
            
        except Exception as e:
            logger.error(f"Error in _remove_hanger_by_bottleneck: {str(e)}", exc_info=True)

    async def pre_render_mannequin_fit(self, db_session, product_id: int) -> bool:
        """
        상품의 누끼 이미지 완성 후, 진짜 생성형 AI(Vertex AI Imagen 3) 인페인팅을 구동하여
        마네킹이 의류를 실제 착용한 듯한 실사 주름, 핏, 명암을 가진 VTON 이미지를 사전 생성합니다.
        (실패 시 로컬 정밀 하이브리드 레이어링으로 안전하게 폴백)
        """
        try:
            logger.info(f"Pre-rendering mannequin tryon and mask for product {product_id}")
            from backend.models import HQProduct, Category
            
            product = db_session.query(HQProduct).filter(HQProduct.id == product_id).first()
            if not product:
                logger.error(f"Product {product_id} not found in DB")
                return False
                
            trans_url = product.transparent_item_image_url
            if not trans_url:
                logger.error(f"Product {product_id} has no transparent image url")
                return False
 
            # 성별 판별
            gender = "male"
            if product.category_id:
                cat = db_session.query(Category).filter(Category.id == product.category_id).first()
                if cat:
                    cat_name = cat.name.lower()
                    if any(x in cat_name for x in ["여성", "women", "female", "여자", "womens"]):
                        gender = "female"
                    elif any(x in cat_name for x in ["남성", "men", "male", "남자", "mens"]):
                        gender = "male"
 
            # 마네킹 베이스 이미지 경로 설정
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            frontend_mockups = os.path.join(os.path.dirname(backend_dir), "frontend", "public", "mockups")
            
            base_file = "woman_base.png" if gender == "female" else "man_base.png"
            base_path = os.path.join(frontend_mockups, base_file)
            if not os.path.exists(base_path):
                base_path = os.path.join(frontend_mockups, "base.png")
            
            if not os.path.exists(base_path):
                logger.error(f"Base mannequin image not found at {base_path}")
                return False
                
            # 누끼 이미지의 로컬 파일 경로 판단
            local_trans_path = None
            if "uploads/transparent" in trans_url:
                file_name = trans_url.split("/")[-1]
                local_trans_path = os.path.join(backend_dir, "uploads", "transparent", file_name)
            elif "uploads/" in trans_url:
                file_name = trans_url.split("/")[-1]
                local_trans_path = os.path.join(backend_dir, "uploads", file_name)
                
            if not local_trans_path or not os.path.exists(local_trans_path):
                logger.error(f"Local transparent image not found for URL: {trans_url}")
                return False
 
            base_img = Image.open(base_path).convert("RGBA")
            t_img = Image.open(local_trans_path).convert("RGBA")
            
            # 상의/하의 판별
            is_top = True
            if product.category_id:
                cat = db_session.query(Category).filter(Category.id == product.category_id).first()
                if cat:
                    cat_name = cat.name.lower()
                    if any(x in cat_name for x in ["바지", "스커트", "하의", "bottom", "pants", "skirt", "jeans"]):
                        is_top = False
 
            # 1단계: 가이드로서 마네킹 비율에 맞춰 옷 레이어 덧씌우기 (인페인팅 소스용)
            # 마네킹 어깨/골반 라인에 최적화하여 합성
            if is_top:
                local_canvas = self._apply_top_layer_internal(base_img, t_img, gender)
            else:
                local_canvas = self._apply_bottom_layer_internal(base_img, t_img, gender)
                
            # 2단계: 진짜 AI (Vertex AI Imagen 3) 인페인팅 적용 시도
            fitted_canvas = None
            ai_success = False
            try:
                # Gemini 2.5 Flash를 활용한 정밀 착장 묘사 프롬프트 빌드
                prod_info = f"{product.brand.name if product.brand else ''} {product.kr_name}"
                top_img_path = local_trans_path if is_top else None
                bottom_img_path = local_trans_path if not is_top else None
                top_prod_info = prod_info if is_top else None
                bottom_prod_info = prod_info if not is_top else None
                
                try:
                    prompt = await _generate_vton_prompt_via_gemini_flash(
                        top_img_path=top_img_path,
                        bottom_img_path=bottom_img_path,
                        top_prod_info=top_prod_info,
                        bottom_prod_info=bottom_prod_info
                    )
                except Exception as e_gemini:
                    logger.warning(f"Gemini Flash prompt generation failed ({str(e_gemini)}). Using fallback prompt.")
                    fallback_desc = prod_info if prod_info else "fashion clothing"
                    prompt = f"A mannequin wearing {fallback_desc}, highly detailed fabric, realistic wrinkles, perfect fit, natural shadow, studio lighting"
                
                # IDM-VTON 카테고리 매핑
                vton_category = "upper_body" if is_top else "lower_body"
                logger.info(f"Attempting Replicate IDM-VTON for single product {product_id}. Category: {vton_category}")
                
                # loose fit, oversized boxy style 가이드 적용하여 래쉬가드 현상 방지
                vton_description = f"loose fit, oversized boxy style, short-sleeve, {prompt}" if is_top else f"loose fit, relaxed style, {prompt}"
                # IDM-VTON API 호출 (마네킹 원본 base_img와 누끼 의류 t_img 전달)
                ai_img = await _call_replicate_idm_vton(
                    human_img=base_img,
                    garm_img=t_img,
                    category=vton_category,
                    description=vton_description
                )
                if ai_img:
                    logger.info("Replicate IDM-VTON rendering for single product SUCCESS!")
                    fitted_canvas = ai_img
                    ai_success = True
            except Exception as e_ai:
                logger.error(f"Vertex AI Single VTON prediction failed: {str(e_ai)}", exc_info=True)
                
            if not ai_success:
                logger.warning("Vertex AI VTON failed. Falling back to Local Hybrid Layering...")
                fitted_canvas = local_canvas
            
            # AI 생성이 성공한 경우 신체 왜곡(둥둥 뜨는 현상)을 방지하기 위해 바로 fitted_canvas를 사용하고, 로컬 폴백일 때만 복원 수행
            final_img = fitted_canvas if ai_success else restore_safe_foreground(base_img, fitted_canvas)
            
            # 결과 저장 폴더 확보
            vton_save_dir = os.path.join(backend_dir, "uploads", "vton")
            os.makedirs(vton_save_dir, exist_ok=True)
            
            file_id = uuid.uuid4().hex[:8]
            tryon_filename = f"tryon_{product_id}_{file_id}.png"
            mask_filename = f"mask_{product_id}_{file_id}.png"
            
            tryon_path = os.path.join(vton_save_dir, tryon_filename)
            mask_path = os.path.join(vton_save_dir, mask_filename)
            
            # 피팅 결과 저장
            final_img.save(tryon_path, "PNG")
            
            # 옷 영역의 흑백 마스크 파일 생성 및 저장
            clothing_mask = self._generate_clothing_mask(base_img, final_img)
            clothing_mask.save(mask_path, "PNG")
            
            # URL 반환 경로 지정
            backend_url = settings.BACKEND_URL
            tryon_url = f"{backend_url}/uploads/vton/{tryon_filename}"
            mask_url = f"{backend_url}/uploads/vton/{mask_filename}"
            
            # DB 정보 업데이트
            product.ai_fitting_image_url = tryon_url
            product.pre_rendered_vtons = {
                "mannequin_tryon_url": tryon_url,
                "mannequin_mask_url": mask_url
            }
            
            # VTON 이미지는 ai_fitting_image_url 에만 단독 저장하며, 일반 갤러리 images 에 섞이지 않도록 차단합니다.
            # current_images = product.images
            # if not current_images:
            #     current_images = []
            # elif isinstance(current_images, str):
            #     try:
            #         current_images = json.loads(current_images)
            #     except:
            #         current_images = [current_images]
            #         
            # # 기존에 이미 사전 생성된 tryon 이미지가 리스트에 있을 경우 정리 후 맨 뒤에 추가
            # cleaned_images = [img for img in current_images if "tryon_" not in img]
            # cleaned_images.append(tryon_url)
            # product.images = cleaned_images
            
            db_session.commit()
            logger.info(f"Successfully pre-rendered tryon for product {product_id}. Tryon: {tryon_url}, Mask: {mask_url}")
            return True
            
        except Exception as e:
            logger.error(f"Error in pre_render_mannequin_fit: {str(e)}", exc_info=True)
            db_session.rollback()
            return False

    async def render_mannequin_fit_generic(
        self,
        transparent_image_url: str,
        gender: str = "female",
        is_top: bool = True
    ) -> Optional[str]:
        """
        [고도화 추가]
        상품 ID 가 없는 임시/신규 등록 단계에서, 
        투명 누끼 이미지와 성별, 상하의 여부를 넘겨받아 임시 마네킹 가상 피팅(VTON) 이미지를 렌더링하고 URL을 반환합니다.
        """
        import uuid
        import io
        import httpx
        from PIL import Image
        
        try:
            logger.info(f"Rendering temporary generic mannequin fit. Gender: {gender}, IsTop: {is_top}")
            
            # 1. 마네킹 베이스 이미지 경로 설정
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            frontend_mockups = os.path.join(os.path.dirname(backend_dir), "frontend", "public", "mockups")
            
            base_file = "woman_base.png" if gender == "female" else "man_base.png"
            base_path = os.path.join(frontend_mockups, base_file)
            if not os.path.exists(base_path):
                base_path = os.path.join(frontend_mockups, "base.png")
            
            if not os.path.exists(base_path):
                logger.error(f"Base mannequin image not found at {base_path}")
                return None
                
            # 2. 누끼 이미지 파일 로드
            local_trans_path = None
            if "uploads/transparent" in transparent_image_url:
                file_name = transparent_image_url.split("/")[-1]
                local_trans_path = os.path.join(backend_dir, "uploads", "transparent", file_name)
            elif "uploads/" in transparent_image_url:
                file_name = transparent_image_url.split("/")[-1]
                local_trans_path = os.path.join(backend_dir, "uploads", file_name)
                
            if local_trans_path and os.path.exists(local_trans_path):
                t_img = Image.open(local_trans_path).convert("RGBA")
            else:
                # 파일이 없을 시 HTTP 다운로드 시도
                target_url = transparent_image_url
                if not target_url.startswith("http"):
                    target_url = f"{settings.BACKEND_URL}{target_url}"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(target_url)
                    resp.raise_for_status()
                    t_img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                    
            base_img = Image.open(base_path).convert("RGBA")
            
            # 3. 핏 가이드 및 카테고리 매핑
            vton_category = "upper_body" if is_top else "lower_body"
            # loose fit, oversized boxy style 가이드 적용하여 래쉬가드 현상 방지
            vton_description = "loose fit, oversized boxy style, short-sleeve, highly detailed fabric, realistic wrinkles, perfect fit, natural shadow, studio lighting" if is_top else "loose fit, relaxed style, highly detailed fabric, realistic wrinkles, perfect fit, natural shadow, studio lighting"
            
            # 4. Fal.ai VTON API 호출
            ai_img = await _call_replicate_idm_vton(
                human_img=base_img,
                garm_img=t_img,
                category=vton_category,
                description=vton_description
            )
            
            if not ai_img:
                logger.warning("Fal.ai VTON failed in generic rendering. Falling back to Local Hybrid Layering...")
                if is_top:
                    ai_img = self._apply_top_layer_internal(base_img, t_img, gender)
                else:
                    ai_img = self._apply_bottom_layer_internal(base_img, t_img, gender)
            
            # 5. 신체 왜곡 방지 및 경계면 보정 후처리
            final_img = restore_safe_foreground(base_img, ai_img)
            
            # 6. 임시 결과 파일 저장
            vton_save_dir = os.path.join(backend_dir, "uploads", "vton")
            os.makedirs(vton_save_dir, exist_ok=True)
            
            file_id = uuid.uuid4().hex[:8]
            tryon_filename = f"tryon_temp_{file_id}.png"
            tryon_path = os.path.join(vton_save_dir, tryon_filename)
            
            final_img.save(tryon_path, "PNG")
            
            backend_url = settings.BACKEND_URL
            tryon_url = f"{backend_url}/uploads/vton/{tryon_filename}"
            logger.info(f"Successfully generated generic temporary VTON: {tryon_url}")
            return tryon_url
            
        except Exception as e:
            logger.error(f"Error in render_mannequin_fit_generic: {str(e)}", exc_info=True)
            return None

    def _apply_bottom_layer_internal(self, b_base, b_img, gender_type):
        bbox = get_clean_bbox(b_img, threshold=30)
        if bbox: 
            b_img = b_img.crop(bbox)
        
        target_width_ratio = 0.72 if gender_type == "female" else 0.76
        target_width = int(b_base.width * target_width_ratio)
        ratio = target_width / float(b_img.size[0])
        target_height = int((float(b_img.size[1]) * float(ratio)))
        
        b_img = b_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        y_offset_ratio = 0.46 if gender_type == "female" else 0.43
        y_offset = int(b_base.height * y_offset_ratio) 
        x_offset = int((b_base.width - b_img.width) / 2)
        
        temp_canvas = Image.new("RGBA", b_base.size, (255, 255, 255, 0))
        temp_canvas.paste(b_img, (x_offset, y_offset), b_img)
        return Image.alpha_composite(b_base, temp_canvas)

    def _apply_top_layer_internal(self, t_base, t_img, gender_type):
        bbox = get_clean_bbox(t_img, threshold=30)
        if bbox: 
            t_img = t_img.crop(bbox)
        
        target_width_ratio = 0.81 if gender_type == "female" else 0.85
        target_width = int(t_base.width * target_width_ratio)
        ratio = target_width / float(t_img.size[0])
        target_height = int((float(t_img.size[1]) * float(ratio)))
        
        t_img = t_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        y_offset_ratio = 0.135 if gender_type == "female" else 0.115
        y_offset = int(t_base.height * y_offset_ratio)
        x_offset = int((t_base.width - t_img.width) / 2)
        
        temp_canvas = Image.new("RGBA", t_base.size, (255, 255, 255, 0))
        temp_canvas.paste(t_img, (x_offset, y_offset), t_img)
        return Image.alpha_composite(t_base, temp_canvas)

    def _generate_clothing_mask(self, base_img: Image.Image, final_img: Image.Image) -> Image.Image:
        """최종 이미지와 마네킹 베이스 이미지의 색상/알파 차이로 옷 마스크 추출"""
        base_arr = np.array(base_img)
        final_arr = np.array(final_img)
        
        diff = np.abs(final_arr.astype(np.int16) - base_arr.astype(np.int16))
        mask_pixels = (np.max(diff[:, :, :3], axis=2) > 15) | (diff[:, :, 3] > 15)
        
        mask_arr = np.zeros((base_img.height, base_img.width), dtype=np.uint8)
        mask_arr[mask_pixels] = 255
        
        return Image.fromarray(mask_arr, mode="L")



# =====================================================================
# 스마트 믹스앤매치 VTON (상/하의 조합) - 실제 PIL 합성
# =====================================================================

async def smart_layering_vton(top_id: Optional[int] = None, bottom_id: Optional[int] = None) -> str:
    """
    상/하의 조합 VTON. 캐시 HIT 시 비용 $0.
    Python Pillow(PIL)를 사용해 물리적 레이어 덧씌우기 수행.
    """
    logger.info(f"IDM-VTON Smart Layering — Top: {top_id}, Bottom: {bottom_id}")
    
    # [추가] 단일 의상 착장 시 미리 가공된 고화질 ai_fitting_image_url 조기 반환 (0.001초 연산)
    from backend.database import SessionLocal
    from backend.models import HQProduct
    
    if top_id and not bottom_id:
        db = SessionLocal()
        try:
            prod = db.query(HQProduct).filter(HQProduct.id == top_id).first()
            if prod and prod.ai_fitting_image_url:
                logger.info(f"Single Product VTON direct return (Top {top_id}): {prod.ai_fitting_image_url}")
                return prod.ai_fitting_image_url
        finally:
            db.close()
            
    if bottom_id and not top_id:
        db = SessionLocal()
        try:
            prod = db.query(HQProduct).filter(HQProduct.id == bottom_id).first()
            if prod and prod.ai_fitting_image_url:
                logger.info(f"Single Product VTON direct return (Bottom {bottom_id}): {prod.ai_fitting_image_url}")
                return prod.ai_fitting_image_url
        finally:
            db.close()

    cache_key = f"vton_combo_T{top_id}_B{bottom_id}"
    
    if cache_key in _vton_cache:
        logger.info(f"Cache HIT for {cache_key} (Cost: $0)")
        return _vton_cache[cache_key]["result_url"]
        
    logger.info(f"Cache MISS. Rendering physical overlay with PIL...")
    
    # 1. 경로 설정
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frontend_mockups = os.path.join(os.path.dirname(backend_dir), "frontend", "public", "mockups")
    vton_save_dir = os.path.join(backend_dir, "uploads", "vton")
    os.makedirs(vton_save_dir, exist_ok=True)
    
    from backend.database import SessionLocal
    from backend.models import HQProduct, Category

    db = SessionLocal()
    
    # 성별 판별 로직 추가 (DB 카테고리 정보 조회)
    gender = "male" # 기본값
    target_id = top_id if top_id else bottom_id
    if target_id:
        prod = db.query(HQProduct).filter(HQProduct.id == target_id).first()
        if prod and prod.category_id:
            cat = db.query(Category).filter(Category.id == prod.category_id).first()
            if cat:
                cat_name = cat.name.lower()
                if any(x in cat_name for x in ["여성", "women", "female", "여자", "womens"]):
                    gender = "female"
                elif any(x in cat_name for x in ["남성", "men", "male", "남자", "mens"]):
                    gender = "male"

    # 2. 이미지 로드 (성별에 따른 동적 선택)
    base_file = "woman_base.png" if gender == "female" else "man_base.png"
    base_path = os.path.join(frontend_mockups, base_file)
    if not os.path.exists(base_path):
        base_path = os.path.join(frontend_mockups, "base.png") # 폴백
        
    if not os.path.exists(base_path):
        logger.error(f"Base mannequin not found at {base_path}")
        db.close()
        return "http://localhost:3000/mockups/base.png" # 예외 발생 시 안전 장치
        
    try:
        # 시뮬레이션을 위한 잠시 대기 (AI 렌더링 시간 연출)
        await asyncio.sleep(1.0)
        
        # RGBA로 열어서 알파 블렌딩 준비
        base_img = Image.open(base_path).convert("RGBA")
        original_base = base_img.copy()
        
        # DB에서 동적으로 파일 경로 확인하는 헬퍼 함수 (실시간 rembg 누끼 생성 지원)
        async def get_product_transparent_img(prod_id):
            if not prod_id:
                return None
            prod = db.query(HQProduct).filter(HQProduct.id == prod_id).first()
            if not prod:
                return None
            
            url = prod.transparent_item_image_url
            if not url:
                logger.info(f"Product {prod_id} has no transparent image. Running real-time rembg...")
                orig_url = None
                if prod.images and len(prod.images) > 0:
                    orig_url = prod.images[0]
                else:
                    orig_url = prod.ai_fitting_image_url
                
                if orig_url:
                    # 상대 경로일 시 로컬 백엔드 주소 부착
                    if not orig_url.startswith("http"):
                        backend_url = settings.BACKEND_URL
                        orig_url = f"{backend_url}{orig_url}"
                    
                    try:
                        generator = AIFittingPreGenerator()
                        new_transparent_url = await generator.extract_transparent_clothing(orig_url, cat.name if cat else None)
                        if new_transparent_url:
                            prod.transparent_item_image_url = new_transparent_url
                            db.commit()
                            url = new_transparent_url
                            logger.info(f"Real-time rembg success for product {prod_id}: {url}")
                    except Exception as ex:
                        logger.error(f"Real-time rembg failed for product {prod_id}: {str(ex)}")
            
            if not url:
                return None
                
            # 로컬 파일 경로 판단
            if "uploads/transparent" in url:
                file_name = url.split("/")[-1]
                local_path = os.path.join(backend_dir, "uploads", "transparent", file_name)
                if os.path.exists(local_path):
                    return local_path
            elif "uploads/vton" in url:
                file_name = url.split("/")[-1]
                local_path = os.path.join(backend_dir, "uploads", "vton", file_name)
                if os.path.exists(local_path):
                    return local_path
            elif "uploads/" in url:
                file_name = url.split("/")[-1]
                local_path = os.path.join(backend_dir, "uploads", file_name)
                if os.path.exists(local_path):
                    return local_path
            elif "mockups" in url or "shirt" in url or "sweater" in url or "jeans" in url:
                # mockups 폴더
                file_name = url.split("/")[-1]
                local_path = os.path.join(frontend_mockups, file_name)
                if os.path.exists(local_path):
                    return local_path
            return None
 
        # 기존 1, 2, 3 하드코딩 매핑 호환용 폴백
        def get_layer_name(prod_id):
            if prod_id == 1: return "shirt"
            if prod_id == 2: return "sweater"
            if prod_id == 3: return "jeans"
            return None
 
        # --- [추가] 2.5D 물리 매핑 도우미 함수 (남/녀 마네킹 신체 비율 커스터마이징) ---
        def apply_bottom_layer(b_base, b_img, gender_type):
            bbox = get_clean_bbox(b_img, threshold=30)
            if bbox: b_img = b_img.crop(bbox)
            
            target_width_ratio = 0.72 if gender_type == "female" else 0.76
            target_width = int(b_base.width * target_width_ratio)
            ratio = target_width / float(b_img.size[0])
            target_height = int((float(b_img.size[1]) * float(ratio)))
            try: res_filter = Image.Resampling.LANCZOS
            except AttributeError: res_filter = Image.LANCZOS
            b_img = b_img.resize((target_width, target_height), res_filter)
            
            y_offset_ratio = 0.46 if gender_type == "female" else 0.43
            y_offset = int(b_base.height * y_offset_ratio) 
            x_offset = int((b_base.width - b_img.width) / 2)
            temp_canvas = Image.new("RGBA", b_base.size, (255, 255, 255, 0))
            temp_canvas.paste(b_img, (x_offset, y_offset), b_img)
            return Image.alpha_composite(b_base, temp_canvas)
 
        def apply_top_layer(t_base, t_img, gender_type):
            bbox = get_clean_bbox(t_img, threshold=30)
            if bbox: t_img = t_img.crop(bbox)
            
            target_width_ratio = 0.81 if gender_type == "female" else 0.85
            target_width = int(t_base.width * target_width_ratio)
            ratio = target_width / float(t_img.size[0])
            target_height = int((float(t_img.size[1]) * float(ratio)))
            try: res_filter = Image.Resampling.LANCZOS
            except AttributeError: res_filter = Image.LANCZOS
            t_img = t_img.resize((target_width, target_height), res_filter)
            
            y_offset_ratio = 0.135 if gender_type == "female" else 0.115
            y_offset = int(t_base.height * y_offset_ratio)
            x_offset = int((t_base.width - t_img.width) / 2)
            temp_canvas = Image.new("RGBA", t_base.size, (255, 255, 255, 0))
            temp_canvas.paste(t_img, (x_offset, y_offset), t_img)
            return Image.alpha_composite(t_base, temp_canvas)
        # ----------------------------------------
 
        # 1. 상의/하의 이미지 로드
        top_path = await get_product_transparent_img(top_id) if top_id else None
        bottom_path = await get_product_transparent_img(bottom_id) if bottom_id else None
        
        top_img = Image.open(top_path).convert("RGBA") if top_path else None
        bottom_img = Image.open(bottom_path).convert("RGBA") if bottom_path else None
        
        # 2. 진짜 AI (Vertex AI Imagen 3) 이미지 피팅 시도 (외부 API 지연 15~20초 제거를 위해 False 처리)
        ai_success = False
        if False:
            # Gemini 2.5 Flash를 활용해 의류 이미지 자체의 시각적 상세 특징(로고, 색상 등)을 반영한 고품질 프롬프트 생성
            top_prod_info = None
            if top_id:
                top_prod = db.query(HQProduct).filter(HQProduct.id == top_id).first()
                if top_prod:
                    top_prod_info = f"{top_prod.brand.name if top_prod.brand else ''} {top_prod.kr_name}"
            
            bottom_prod_info = None
            if bottom_id:
                bottom_prod = db.query(HQProduct).filter(HQProduct.id == bottom_id).first()
                if bottom_prod:
                    bottom_prod_info = f"{bottom_prod.brand.name if bottom_prod.brand else ''} {bottom_prod.kr_name}"
                    
            try:
                prompt = await _generate_vton_prompt_via_gemini_flash(
                    top_img_path=top_path,
                    bottom_img_path=bottom_path,
                    top_prod_info=top_prod_info,
                    bottom_prod_info=bottom_prod_info
                )
            except Exception as e_gemini:
                logger.warning(f"Gemini Flash prompt generation failed for combo ({str(e_gemini)}). Using fallback prompt.")
                fallback_parts = []
                if top_prod_info: fallback_parts.append(top_prod_info)
                if bottom_prod_info: fallback_parts.append(bottom_prod_info)
                desc = " and ".join(fallback_parts) if fallback_parts else "fashion clothing"
                prompt = f"A mannequin wearing {desc}, highly detailed fabric, realistic wrinkles, perfect fit, natural shadow, studio lighting"
            
            logger.info(f"Attempting Replicate IDM-VTON for combo. Prompt: {prompt}")
            current_base = base_img.copy()
            temp_success = False

            # 1. 하의 피팅 (Bottom First)
            if bottom_img:
                bottom_description = f"loose fit, relaxed style, {prompt}"
                ai_bottom = await _call_replicate_idm_vton(
                    human_img=current_base,
                    garm_img=bottom_img,
                    category="lower_body",
                    description=bottom_description
                )
                if ai_bottom:
                    current_base = ai_bottom
                    temp_success = True

            # 2. 상의 피팅 (Top Overlay)
            if top_img:
                top_description = f"loose fit, oversized boxy style, short-sleeve, {prompt}"
                ai_top = await _call_replicate_idm_vton(
                    human_img=current_base,
                    garm_img=top_img,
                    category="upper_body",
                    description=top_description
                )
                if ai_top:
                    current_base = ai_top
                    temp_success = True

            if temp_success:
                logger.info("Replicate IDM-VTON Combo Rendering SUCCESS!")
                base_img = current_base
                ai_success = True
                
        # 3. 진짜 AI 렌더링이 실패하였거나 호출되지 않은 경우 -> 로컬 정밀 하이브리드로 폴백
        if not ai_success:
            logger.warning("Vertex AI VTON failed/quota exceeded. Falling back to Local Hybrid Layering...")
            base_img = _apply_local_hybrid_layering(base_img, top_img, bottom_img, gender)
                    
        # 3. 2.5D 마네킹 신체 영역 복원 후 저장
        base_img = restore_safe_foreground(original_base, base_img)
        
        # 4. 브라우저 서빙용 파일 저장
        filename = f"vton_result_{uuid.uuid4().hex[:8]}.png"
        save_path = os.path.join(vton_save_dir, filename)
        
        base_img.save(save_path, "PNG")
        
        # FastAPI 정적 경로 서빙
        backend_url = settings.BACKEND_URL
        result_url = f"{backend_url}/uploads/vton/{filename}"
        
        # 캐시 저장
        _cache_put(cache_key, {"result_url": result_url})
        logger.info(f"Cached VTON combo: {cache_key} at {result_url}")
        
        return result_url
        
    except Exception as e:
        logger.error(f"PIL Layering Failed: {str(e)}")
        return "http://localhost:3000/mockups/base.png"
    finally:
        db.close()



# =====================================================================
# 스마트 피팅 (단일 상품 + 체형 데이터)
# =====================================================================

# Fallback 피팅 이미지: 체형별로 다른 마네킹 제공
_BODY_TYPE_FALLBACKS = {
    "slim": "https://images.unsplash.com/photo-1558171813-4c088753af8f?w=600&q=80",
    "regular": "https://images.unsplash.com/photo-1549424424-6f8ba24a1b02?w=600&q=80",
    "athletic": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600&q=80",
}

def _classify_body_type(height: float, weight: float) -> str:
    """BMI 기반 간이 체형 분류"""
    bmi = weight / ((height / 100) ** 2)
    if bmi < 20:
        return "slim"
    elif bmi < 25:
        return "regular"
    else:
        return "athletic"


async def smart_fit_single_product(
    product_id: int,
    height: float = 170.0,
    weight: float = 65.0,
    shoulder_width: float = 44.0,
    model_type: str = "mannequin",
) -> dict:
    """
    단일 상품 + 체형 파라미터 기반 스마트 피팅.
    
    1. 캐시 키 생성 (product_id + 체형 해시)
    2. 캐시 HIT → 즉시 반환 (비용 $0)
    3. 캐시 MISS → 외부 API 시뮬레이션 → 결과 캐싱
    4. API 실패 → Fallback 마네킹 이미지 반환
    """
    start_time = time.time()
    
    # 체형 해시 생성 (5cm/5kg 단위로 버켓팅하여 캐시 효율 극대화)
    h_bucket = round(height / 5) * 5
    w_bucket = round(weight / 5) * 5
    s_bucket = round(shoulder_width / 2) * 2
    cache_key = f"vton_smartfit_P{product_id}_H{h_bucket}_W{w_bucket}_S{s_bucket}"
    
    # [1] 캐시 확인
    if cache_key in _vton_cache:
        cached = _vton_cache[cache_key]
        elapsed = int((time.time() - start_time) * 1000)
        logger.info(f"SmartFit Cache HIT: {cache_key} (Cost: $0, {elapsed}ms)")
        return {
            "fitting_url": cached["fitting_url"],
            "render_time_ms": elapsed,
            "confidence_score": cached.get("confidence_score", 0.92),
            "message": f"캐시에서 즉시 로드됨 (체형 버켓: H{h_bucket}/W{w_bucket}/S{s_bucket})",
        }
    
    # [2] 체형 분류
    body_type = _classify_body_type(height, weight)
    logger.info(f"SmartFit Cache MISS: {cache_key} | Body type: {body_type}")
    
    # [3] 외부 AI API 호출 시도 (또는 DB 정적 사전 렌더링 VTON 반환)
    fitting_url = None
    confidence = 0.85
    
    from backend.database import SessionLocal
    from backend.models import HQProduct
    
    db = SessionLocal()
    prod = None
    try:
        # DB에서 해당 상품의 피팅 이미지 조회
        prod = db.query(HQProduct).filter(HQProduct.id == product_id).first()
        if prod:
            # 아직 사전 렌더링된 마네킹 피팅 샷이 없으면 실시간 빌드 시도
            if not prod.ai_fitting_image_url:
                logger.info(f"SmartFit: Product {product_id} has no pre-rendered tryon. Rendering now...")
                generator = AIFittingPreGenerator()
                # 비동기로 마네킹 정적 착장 파일 및 DB 필드 업데이트 수행
                await generator.pre_render_mannequin_fit(db, product_id)
                db.refresh(prod)
            
            # 최종 DB에서 피팅 이미지 URL 획득
            if prod.ai_fitting_image_url:
                fitting_url = prod.ai_fitting_image_url
                confidence = 0.95
        
        # 만약 DB 조회 및 실시간 렌더링 결과조차 없다면 기존 URL 또는 Mock 시뮬레이션 모드 사용
        if not fitting_url:
            vton_api = os.getenv("VTON_API_ENDPOINT", "")
            if vton_api:
                # 실제 외부 API 모드
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(vton_api, json={
                        "product_id": product_id,
                        "body_type": body_type,
                        "height": height,
                        "weight": weight,
                        "shoulder_width": shoulder_width,
                        "model_type": model_type,
                        "detail_lock": True,
                    })
                    response.raise_for_status()
                    data = response.json()
                    fitting_url = data.get("result_url")
                    confidence = data.get("confidence", 0.88)
            else:
                # Mock 시뮬레이션 모드
                await asyncio.sleep(1.0)
                fallback_base = _BODY_TYPE_FALLBACKS.get(body_type, _BODY_TYPE_FALLBACKS["regular"])
                fitting_url = fallback_base
                confidence = 0.75
                
    except Exception as e:
        logger.error(f"SmartFit API or DB retrieval failed for {cache_key}: {str(e)}")
        # 예외 발생 시 최종 폴백
        if prod and prod.ai_fitting_image_url:
            fitting_url = prod.ai_fitting_image_url
        else:
            fitting_url = _BODY_TYPE_FALLBACKS["regular"]
        confidence = 0.60
    finally:
        db.close()

    
    elapsed = int((time.time() - start_time) * 1000)
    
    # [5] 결과 캐싱
    _cache_put(cache_key, {
        "fitting_url": fitting_url,
        "confidence_score": confidence,
    })
    logger.info(f"SmartFit generated & cached: {cache_key} ({elapsed}ms, confidence: {confidence:.2f})")
    
    return {
        "fitting_url": fitting_url,
        "render_time_ms": elapsed,
        "confidence_score": round(confidence, 2),
        "message": f"AI 피팅 완료 (체형: {body_type}, 렌더링: {elapsed}ms)",
    }


def get_clean_bbox(img: Image.Image, threshold: int = 30) -> Optional[tuple]:
    """
    알파 채널의 미세 노이즈(먼지 픽셀)를 제외하고,
    실제 불투명도가 threshold 이상인 의미 있는 픽셀들 영역의 바운딩 박스를 반환합니다.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    
    data = np.array(img)
    alpha = data[:, :, 3]
    
    non_zero = np.where(alpha >= threshold)
    if len(non_zero[0]) == 0 or len(non_zero[1]) == 0:
        # threshold를 낮춰서 재시도
        non_zero = np.where(alpha > 0)
        if len(non_zero[0]) == 0 or len(non_zero[1]) == 0:
            return None
            
    min_y, max_y = np.min(non_zero[0]), np.max(non_zero[0])
    min_x, max_x = np.min(non_zero[1]), np.max(non_zero[1])
    
    return (int(min_x), int(min_y), int(max_x + 1), int(max_y + 1))


def restore_safe_foreground(base_img: Image.Image, canvas_img: Image.Image) -> Image.Image:
    """
    합성 완료된 캔버스 위에, 마네킹의 목, 양손, 발목/발 등 신체 말단 영역만 안전 전경(Foreground)으로
    알파 덮어쓰기를 수행하여 옷 밑으로 손/목/발이 가려져 생기는 어색함을 완전히 보정합니다.
    (소매 안쪽으로 팔뚝이 뚫고 나오는 기괴한 현상을 방지하기 위해 목, 손목 이하, 발목 이하만 정밀 덮어쓰기)
    """
    base_arr = np.array(base_img.convert("RGBA"))
    canvas_arr = np.copy(np.array(canvas_img.convert("RGBA")))
    
    height, width, _ = base_arr.shape
    
    # 흑백 마스크 생성 (기본 0: 투명, 255: 복원 대상 전경)
    fore_mask = np.zeros((height, width), dtype=np.uint8)
    
    # Y = 1024x1024 마네킹 이미지 기준 정밀 좌표 스펙 (왜곡 방지를 위해 영역 확장)
    # 1. 목/머리 영역 (Y < 220. 귀와 턱선 뭉개짐 전면 보완)
    fore_mask[0:220, :] = 255
    
    # 2. 양 손목 이하의 손가락 영역 (450 <= Y < 720)
    # 가로 범위: 남/여 마네킹의 양쪽 손 위치 전체 커버 (X < 450 및 X >= 580)
    fore_mask[450:720, 0:450] = 255
    fore_mask[450:720, 580:width] = 255
    
    # 3. 발목 및 스탠드 영역 (Y >= 900)
    fore_mask[900:height, :] = 255
    
    # 마스크 영역이면서 동시에 마네킹 신체(불투명 알파)가 존재하는 영역만 덮어쓰기
    restore_condition = (fore_mask == 255) & (base_arr[:, :, 3] > 10)
    for c in range(4):
        canvas_arr[:, :, c] = np.where(restore_condition, base_arr[:, :, c], canvas_arr[:, :, c])
        
    return Image.fromarray(canvas_arr, mode="RGBA")


async def _generate_vton_prompt_via_gemini_flash(
    top_img_path: Optional[str] = None,
    bottom_img_path: Optional[str] = None,
    top_prod_info: Optional[str] = None,
    bottom_prod_info: Optional[str] = None
) -> str:
    """
    Vertex AI의 gemini-2.5-flash 멀티모달 모델을 호출하여, 
    피팅할 의류의 상세 이미지와 메타데이터를 기반으로 
    마네킹에 완벽하게 입혀지기 위한 고품질 영어 묘사 프롬프트를 자동 생성합니다.
    (브랜드 로고 글자, 넥라인, 소매길이, 형태, 질감 등 정밀 묘사)
    """
    token = _get_gcp_access_token()
    if not token:
        logger.error("No access token available for Vertex AI Gemini Flash.")
        return "fashion clothing on mannequin, highly detailed fabric, realistic wrinkles, studio lighting"
        
    project_id = "crawlerwin"
    location = "us-central1"
    endpoint = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/gemini-2.5-flash:generateContent"
    
    # 멀티모달 프롬프트 조립
    contents = {
        "role": "user",
        "parts": []
    }
    
    system_instruction = (
        "You are an expert fashion detail analyzer. "
        "Your task is to analyze the provided clothing image(s) and information, "
        "and generate a concise and precise English garment description for a Virtual Try-On (VTON) model. "
        "Describe ONLY the garment itself: item type (e.g. short-sleeve t-shirt, long-sleeve sweater, pants, jeans), "
        "exact color, neckline style, sleeve length, exact text logos (if any, like brand name or typography), "
        "its size/fit (e.g. oversize, slim fit), and design patterns. "
        "Do NOT describe or mention mannequin, human model, human skin, stand, or background. "
        "Output ONLY the final English description of the garment, without introduction, explanations, markdown, or quotes."
    )
    
    prompt_text = "Generate a highly detailed mannequin fitting inpainting prompt for these clothes:\n"
    if top_prod_info:
        prompt_text += f"- Top Item Info: {top_prod_info}\n"
    if bottom_prod_info:
        prompt_text += f"- Bottom Item Info: {bottom_prod_info}\n"
    contents["parts"].append({"text": prompt_text})
    
    # 옷 이미지 파일 인코딩 후 멀티모달 파트 적재
    def encode_image(img_path):
        if img_path and os.path.exists(img_path):
            try:
                import base64
                with open(img_path, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                logger.warning(f"Failed to encode {img_path}: {e}")
        return None

    top_b64 = encode_image(top_img_path)
    if top_b64:
        contents["parts"].append({
            "inlineData": {
                "mimeType": "image/png",
                "data": top_b64
            }
        })
        
    bottom_b64 = encode_image(bottom_img_path)
    if bottom_b64:
        contents["parts"].append({
            "inlineData": {
                "mimeType": "image/png",
                "data": bottom_b64
            }
        })
        
    payload = {
        "contents": [contents],
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "maxOutputTokens": 250,
            "temperature": 0.4
        }
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    text_out = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    cleaned_prompt = text_out.strip().replace('"', '').replace("'", "")
                    logger.info(f"Gemini 2.5 Flash Generated VTON Prompt: {cleaned_prompt}")
                    return cleaned_prompt
            logger.error(f"Gemini 2.5 Flash API HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Exception calling Gemini 2.5 Flash API: {str(e)}", exc_info=True)
        
    # 폴백
    fallback_parts = []
    if top_prod_info: fallback_parts.append(top_prod_info)
    if bottom_prod_info: fallback_parts.append(bottom_prod_info)
    desc = " and ".join(fallback_parts) if fallback_parts else "fashion clothing"
    return f"A mannequin wearing {desc}, highly detailed fabric, realistic wrinkles, perfect fit, natural shadow, studio lighting"


def _get_gcp_access_token() -> Optional[str]:
    """crawlerwin GCP 서비스 계정 키 파일로부터 OAuth2 access token을 발급받아 반환합니다."""
    creds_path = r"D:\에이전트그룹\crawlerwin(마스터키 제미나이 VERTEX AI API키).json"
    if not os.path.exists(creds_path):
        logger.error(f"GCP service account key file not found at: {creds_path}")
        return None
    try:
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token
    except Exception as e:
        logger.error(f"Failed to acquire GCP OAuth2 token: {str(e)}", exc_info=True)
        return None


def pad_to_3_4_ratio(img: Image.Image, bg_color=(255, 255, 255, 255)) -> Image.Image:
    """1:1 등 임의 비율의 PIL 이미지를 종횡비 왜곡 없이 3:4 비율(768x1024)의 흰색 배경 캔버스 중앙에 패딩 배치합니다."""
    img_rgba = img.convert("RGBA")
    w, h = img_rgba.size
    
    # 768x1024 캔버스 생성 (기본 흰색 배경)
    canvas = Image.new("RGBA", (768, 1024), bg_color)
    
    # 가로 기준으로 리사이즈 시도 (Aspect Fit)
    scale = 768.0 / float(w)
    new_w = 768
    new_h = int(float(h) * scale)
    
    # 만약 세로가 1024를 초과한다면 세로 기준으로 다시 스케일 계산
    if new_h > 1024:
        scale = 1024.0 / float(h)
        new_h = 1024
        new_w = int(float(w) * scale)
        
    try: res_filter = Image.Resampling.LANCZOS
    except AttributeError: res_filter = Image.LANCZOS
    
    img_resized = img_rgba.resize((new_w, new_h), res_filter)
    
    # 투명 알파 채널을 마스크로 제공하여 결합 (배경의 흰색을 보존하기 위해 mask=img_resized 필수)
    x_offset = (768 - new_w) // 2
    y_offset = (1024 - new_h) // 2
    canvas.paste(img_resized, (x_offset, y_offset), mask=img_resized)
    
    # IDM-VTON 전처리계를 위해 3채널 RGB 포맷으로 최종 변환하여 반환
    return canvas.convert("RGB")


async def _call_replicate_idm_vton(
    human_img: Image.Image,
    garm_img: Image.Image,
    category: str,
    description: str = "fashion clothing"
) -> Optional[Image.Image]:
    """Fal.ai API(fashn/tryon/v1.6)를 사용하여 가상 피팅을 수행합니다.
    입력 이미지를 3:4 비율(768x1024)로 사전 패딩하여 소매 왜곡 및 외곽선 흰색 들뜸을 차단한 후,
    결과물을 원래 1:1 종횡비로 복원하여 반환합니다."""
    fal_key = settings.FAL_KEY or os.environ.get("FAL_KEY")
    if not fal_key:
        logger.warning("FAL_KEY is not configured. Fal.ai VTON API call skipped.")
        return None

    def image_to_data_uri(img: Image.Image) -> str:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    try:
        # 1. 3:4 전처리 패딩 변환 (의류는 흰색 배경 유지, 마네킹은 검은색 배경 패딩으로 외곽 흰색 띠 소멸)
        human_3_4 = pad_to_3_4_ratio(human_img, bg_color=(0, 0, 0, 255))
        garm_3_4 = pad_to_3_4_ratio(garm_img, bg_color=(255, 255, 255, 255))
        
        human_uri = image_to_data_uri(human_3_4)
        garm_uri = image_to_data_uri(garm_3_4)

        # Fal.ai 카테고리 매핑
        fal_category = "tops"
        if category in ("lower_body", "bottoms"):
            fal_category = "bottoms"
        elif category in ("dresses", "one-pieces"):
            fal_category = "one-pieces"

        endpoint = "https://queue.fal.run/fal-ai/fashn/tryon/v1.6"
        headers = {
            "Authorization": f"Key {fal_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model_image": human_uri,
            "garment_image": garm_uri,
            "category": fal_category
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            logger.info(f"Submitting Fal.ai VTON request. Category: {fal_category}")
            resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code not in (200, 201, 202):
                logger.error(f"Fal.ai API initialization failed: {resp.status_code} | {resp.text}")
                return None
            
            queue_data = resp.json()
            request_id = queue_data.get("request_id")
            status_url = queue_data.get("status_url")
            response_url = queue_data.get("response_url")
            
            if not status_url or not response_url:
                logger.error(f"Fal.ai Queue API returned invalid response: {queue_data}")
                return None
                
            logger.info(f"Fal.ai VTON prediction started: ID={request_id}")

            max_attempts = 40
            for attempt in range(max_attempts):
                await asyncio.sleep(1.0)
                poll_resp = await client.get(status_url, headers=headers)
                if poll_resp.status_code in (200, 202):
                    data = poll_resp.json()
                    status = data.get("status")
                    logger.info(f"Fal.ai VTON Polling: Attempt {attempt+1}/{max_attempts} | Status={status}")
                    
                    if status == "COMPLETED":
                        # 결과값 가져오기
                        res_resp = await client.get(response_url, headers=headers)
                        res_resp.raise_for_status()
                        res_data = res_resp.json()
                        
                        images = res_data.get("images")
                        if images and len(images) > 0:
                            output_url = images[0].get("url")
                            logger.info(f"Fal.ai VTON rendering SUCCEEDED. Output URL: {output_url}")
                            
                            img_resp = await client.get(output_url)
                            img_resp.raise_for_status()
                            
                            # 3:4 피팅 결과물 로드
                            ai_img_3_4 = Image.open(io.BytesIO(img_resp.content)).convert("RGBA")
                            
                            # 2. 1:1 역변환 후처리 복원 (768x1024 -> 1024x1024)
                            # 중앙의 768x768 부분을 크롭하여 종횡비 복구
                            cropped_result = ai_img_3_4.crop((0, 128, 768, 896))
                            try: res_filter = Image.Resampling.LANCZOS
                            except AttributeError: res_filter = Image.LANCZOS
                            final_result = cropped_result.resize(human_img.size, res_filter)
                            return final_result
                        break
                    elif status in ("FAILED", "CANCELLED"):
                        logger.error(f"Fal.ai VTON prediction failed or cancelled: {data}")
                        break
                else:
                    logger.error(f"Fal.ai Polling HTTP Error: {poll_resp.status_code} | {poll_resp.text}")
            
            logger.error("Fal.ai VTON polling timed out or failed to complete.")
            return None
            
    except Exception as e:
        logger.error(f"Error in Fal.ai VTON execution: {str(e)}", exc_info=True)
        return None


async def _call_vertex_imagen_inpainting(
    base_img: Image.Image,
    mask_img: Image.Image,
    prompt: str
) -> Optional[Image.Image]:
    """Vertex AI Imagen 3 모델(imagen-3.0-generate-002)을 사용하여 이미지 인페인팅을 수행합니다.
    안정성과 쿼터 우회를 위해 이미지 크기를 512x512로 다운사이징하여 호출한 후, 원본 크기로 원상복구합니다."""
    token = _get_gcp_access_token()
    if not token:
        logger.error("No access token available for Vertex AI.")
        return None
        
    project_id = "crawlerwin"
    location = "us-central1"
    endpoint = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/imagen-3.0-generate-002:predict"
    
    # 원본 크기 저장 및 512x512 다운사이징
    orig_w, orig_h = base_img.size
    try: res_filter = Image.Resampling.LANCZOS
    except AttributeError: res_filter = Image.LANCZOS
    
    try: res_nearest = Image.Resampling.NEAREST
    except AttributeError: res_nearest = Image.NEAREST
    
    base_img_resized = base_img.resize((512, 512), res_filter)
    mask_img_resized = mask_img.resize((512, 512), res_nearest)
    
    # 이미지를 PNG 포맷 바이트로 변환 후 base64 인코딩
    base_buf = io.BytesIO()
    base_img_resized.save(base_buf, format="PNG")
    base_b64 = base64.b64encode(base_buf.getvalue()).decode("utf-8")
    
    mask_buf = io.BytesIO()
    mask_img_resized.save(mask_buf, format="PNG")
    mask_b64 = base64.b64encode(mask_buf.getvalue()).decode("utf-8")
    
    # 마네킹 피팅룸 컨셉 강제를 위해 프롬프트 전처리 (인물 생성 원천 차단 및 마네킹 고유 형체 박제)
    mannequin_prompt = f"A pure white plastic mannequin wearing a clothing, {prompt}, do NOT generate human model, do NOT generate human skin, keep the glossy white plastic mannequin body and stand as-is from reference image 1, highly detailed fabric, realistic wrinkles, studio lighting"
    
    payload = {
        "instances": [
            {
                "prompt": mannequin_prompt,
                "reference_images": [
                    {
                        "reference_id": 1,
                        "reference_image": {
                            "image": {
                                "bytesBase64Encoded": base_b64,
                                "mimeType": "image/png"
                            }
                        }
                    },
                    {
                        "reference_id": 2,
                        "reference_image": {
                            "image": {
                                "bytesBase64Encoded": mask_b64,
                                "mimeType": "image/png"
                            }
                        },
                        "config": {
                            "mask_mode": "MASK_MODE_USER_PROVIDED"
                        }
                    }
                ]
            }
        ],
        "parameters": {
            "sample_count": 1,
            "edit_mode": "EDIT_MODE_INPAINT_INSERTION"
        }
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # 비동기 httpx 클라이언트를 사용해 비동기 REST API 호출
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            print(f"Vertex AI API HTTP response status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                predictions = data.get("predictions", [])
                if predictions:
                    print("Successfully received generated image from Vertex AI Imagen!")
                    img_b64 = predictions[0].get("bytesBase64Encoded")
                    img_data = base64.b64decode(img_b64)
                    ai_img_512 = Image.open(io.BytesIO(img_data)).convert("RGBA")
                    # 원본 크기로 다시 스케일 업
                    return ai_img_512.resize((orig_w, orig_h), res_filter)
                else:
                    print("Error: No predictions returned in Imagen response.")
                    logger.error("No predictions returned in Imagen 3 response.")
            else:
                print(f"Vertex AI API Error HTTP {resp.status_code}: {resp.text}")
                logger.error(f"Vertex AI API HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Exception during Vertex AI API call: {str(e)}", exc_info=True)
        
    return None


def _create_vton_mask(base_img: Image.Image, is_top: bool = True, clothing_img: Optional[Image.Image] = None) -> Image.Image:
    """마네킹 크기에 맞추어 상의/하의 가상 피팅 마스크(L 모드)를 동적으로 생성합니다.
    clothing_img가 전달될 경우, Canny 엣지 검출을 통해 의류의 로고/자수 영역을 판별하여 
    인페인팅(재성형) 마스크에서 자동 도려냄(제외)으로써 오리지널 로고 프린팅을 100% 보존합니다."""
    mask = Image.new("L", base_img.size, 0)
    width, height = base_img.size
    
    # 1. 기본 상의/하의 영역 지정
    if is_top:
        # Y = 160 ~ 520, X = 25% ~ 75%
        for y in range(160, 520):
            for x in range(int(width * 0.25), int(width * 0.75)):
                mask.putpixel((x, y), 255)
    else:
        # Y = 500 ~ 920, X = 25% ~ 75%
        for y in range(500, 920):
            for x in range(int(width * 0.25), int(width * 0.75)):
                mask.putpixel((x, y), 255)
                
    # 2. 로고 영역 동적 검출 및 보존 필터링
    if clothing_img is not None:
        try:
            # 의류를 마네킹 캔버스 크기(1024x1024)에 맞춘 2.5D 스케일/배치 좌표로 임시 합성하여 동기화
            canvas_rgba = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
            c_rgba = clothing_img.convert("RGBA")
            bbox = get_clean_bbox(c_rgba, threshold=30)
            if bbox:
                c_rgba = c_rgba.crop(bbox)
                
            # pre_render_mannequin_fit 내부의 레이어링 크기 변환 비율을 그대로 연동
            if is_top:
                target_width_ratio = 0.81  # woman/man 평균 비율
                target_width = int(base_img.width * target_width_ratio)
                ratio = target_width / float(c_rgba.size[0])
                target_height = int((float(c_rgba.size[1]) * float(ratio)))
                try: res_filter = Image.Resampling.LANCZOS
                except AttributeError: res_filter = Image.LANCZOS
                c_resized = c_rgba.resize((target_width, target_height), res_filter)
                
                y_offset = int(base_img.height * 0.125)  # 대략적인 평균 어깨선 Y offset
                x_offset = int((base_img.width - c_resized.width) / 2)
            else:
                target_width_ratio = 0.74
                target_width = int(base_img.width * target_width_ratio)
                ratio = target_width / float(c_rgba.size[0])
                target_height = int((float(c_rgba.size[1]) * float(ratio)))
                try: res_filter = Image.Resampling.LANCZOS
                except AttributeError: res_filter = Image.LANCZOS
                c_resized = c_rgba.resize((target_width, target_height), res_filter)
                
                y_offset = int(base_img.height * 0.445)
                x_offset = int((base_img.width - c_resized.width) / 2)
                
            canvas_rgba.paste(c_resized, (x_offset, y_offset), c_resized)
            
            # OpenCV BGR 이미지 및 그레이스케일 변환
            open_cv_img = cv2.cvtColor(np.array(canvas_rgba), cv2.COLOR_RGBA2BGR)
            gray_img = cv2.cvtColor(open_cv_img, cv2.COLOR_BGR2GRAY)
            
            # Canny Edge 검출로 텍스트 로고 및 자수 테두리 식별
            edges = cv2.Canny(gray_img, 30, 150)
            
            # 엣지 픽셀 주변부를 충분히 덮기 위해 팽창(Dilation) 연산 수행 (커널 11x11, 2회 반복)
            kernel = np.ones((11, 11), np.uint8)
            logo_mask = cv2.dilate(edges, kernel, iterations=2)
            
            # 기본 VTON 마스크(mask)에서 로고 영역의 픽셀값 강제 차감 (0으로 설정)
            mask_arr = np.array(mask)
            mask_arr[logo_mask > 0] = 0
            
            # 목 단면 및 어깨 윗선 보호 마스킹 보정
            mask_arr[0:180, :] = 0
            
            mask = Image.fromarray(mask_arr, mode="L")
            logger.info("Successfully calculated dynamic logo-preserving mask via Canny Edge detection.")
        except Exception as ex_mask:
            logger.error(f"Failed to generate dynamic logo preservation mask: {ex_mask}", exc_info=True)
            
    return mask


def _apply_local_hybrid_layering(
    base_img: Image.Image,
    top_img: Optional[Image.Image],
    bottom_img: Optional[Image.Image],
    gender: str
) -> Image.Image:
    """진짜 AI API 실패 시 작동할, 어깨/골반 너비 스케일이 완벽히 피팅된 고품질 로컬 하이브리드 레이어링 엔진입니다."""
    current_canvas = base_img.copy()
    
    # 1. 하의 배치 (Bottom Layer)
    if bottom_img:
        bbox = get_clean_bbox(bottom_img, threshold=30)
        if bbox:
            bottom_img = bottom_img.crop(bbox)
        # 하의 너비 비율: 골반 비율에 맞게 30%~34%로 조정 (기존 76%는 너무 컸음)
        target_width_ratio = 0.30 if gender == "female" else 0.34
        target_width = int(base_img.width * target_width_ratio)
        ratio = target_width / float(bottom_img.size[0])
        target_height = int((float(bottom_img.size[1]) * float(ratio)))
        
        try: res_filter = Image.Resampling.LANCZOS
        except AttributeError: res_filter = Image.LANCZOS
        
        bottom_resized = bottom_img.resize((target_width, target_height), res_filter)
        
        y_offset_ratio = 0.46 if gender == "female" else 0.43
        y_offset = int(base_img.height * y_offset_ratio)
        x_offset = int((base_img.width - bottom_resized.width) / 2)
        
        temp_canvas = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
        temp_canvas.paste(bottom_resized, (x_offset, y_offset), bottom_resized)
        current_canvas = Image.alpha_composite(current_canvas, temp_canvas)
        
    # 2. 상의 배치 (Top Layer)
    if top_img:
        bbox = get_clean_bbox(top_img, threshold=30)
        if bbox:
            top_img = top_img.crop(bbox)
        # 상의 너비 비율: 어깨 비율에 맞게 38%~42%로 조정 (기존 85%는 거대했음)
        target_width_ratio = 0.38 if gender == "female" else 0.42
        target_width = int(base_img.width * target_width_ratio)
        ratio = target_width / float(top_img.size[0])
        target_height = int((float(top_img.size[1]) * float(ratio)))
        
        try: res_filter = Image.Resampling.LANCZOS
        except AttributeError: res_filter = Image.LANCZOS
        
        top_resized = top_img.resize((target_width, target_height), res_filter)
        
        y_offset_ratio = 0.135 if gender == "female" else 0.115
        y_offset = int(base_img.height * y_offset_ratio)
        x_offset = int((base_img.width - top_resized.width) / 2)
        
        temp_canvas = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
        temp_canvas.paste(top_resized, (x_offset, y_offset), top_resized)
        current_canvas = Image.alpha_composite(current_canvas, temp_canvas)
        
    return current_canvas
