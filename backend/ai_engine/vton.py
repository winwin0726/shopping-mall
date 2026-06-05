import logging
import asyncio
import os
import time
import hashlib
import httpx
from typing import Optional, List, Dict
import json
import uuid
from PIL import Image

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
    """
    Handles background generation of AI Virtual Try-On (VTON) images
    and 5-Scene Hailuo Video Rendering.
    """
    def __init__(self):
        self.vton_endpoint = os.getenv("VTON_API_ENDPOINT", "http://ai-worker:8080/v1/generate")
        self.rembg_endpoint = os.getenv("REMBG_API_ENDPOINT", "http://ai-worker:8080/v1/remove-bg")
        self.hailuo_video_endpoint = os.getenv("HAILUO_API_ENDPOINT", "http://ai-worker:8080/v1/video/hailuo-5scene")
        
    async def pre_generate_fitting(
        self, 
        hq_product_id: int, 
        original_image_url: str, 
        category: str,
        user_body_shape: Optional[Dict[str, any]] = None
    ) -> Optional[str]:
        """
        Calls VTON API to fit the product, utilizing user_body_shape for Smart Fitting.
        """
        logger.info(f"Starting VTON pre-generation for Product ID: {hq_product_id} ({category})")
        
        model_type = "headless_asian_default"
        
        if user_body_shape:
            model_type = "custom_scanned_avatar"
            logger.info(f"Applying custom user body shape: {user_body_shape}")

        payload = {
            "cloth_image": original_image_url, 
            "model_type": model_type,
            "body_parameters": user_body_shape or {},
            "detail_lock": True
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.vton_endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
                generated_url = data.get("result_url")
                logger.info(f"VTON Pre-generation success. Url: {generated_url}")
                return generated_url
        except Exception as e:
            logger.error(f"Failed to generate VTON for {hq_product_id}. Reason: {str(e)}")
            return f"https://cdn.ai-mall.com/cache/vton/product_{hq_product_id}_fallback_fit.jpg"

    async def generate_hailuo_5scene_video(self, hq_product_id: int, vton_image_url: str) -> Optional[List[Dict[str, str]]]:
        """Hailuo-2.3 기반 5씬 자동화 렌더러 연동"""
        logger.info(f"Triggering Hailuo-2.3 Video Pipeline for VTON image: {vton_image_url}")
        
        payload = {
            "source_image": vton_image_url,
            "scenes": ["orbit", "crane", "low-angle", "front", "back"],
            "model_version": "hailuo-2.3",
            " quality": "high-fidelity"
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.hailuo_video_endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
                video_results = data.get("videos", [])
                logger.info(f"Successfully rendered 5-scene videos for {hq_product_id}")
                return video_results
        except Exception as e:
            logger.error(f"Hailuo Pipeline failed: {str(e)}")
            return None
        
    async def extract_transparent_clothing(self, original_image_url: str) -> Optional[str]:
        """Removes background via Local rembg CLI subprocess to prevent asyncio deadlock."""
        logger.info(f"Extracting transparent item from (local rembg CLI): {original_image_url}")
        
        try:
            import urllib.request
            
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            temp_dir = os.path.join(backend_dir, "uploads", "temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            save_dir = os.path.join(backend_dir, "uploads", "transparent")
            os.makedirs(save_dir, exist_ok=True)
            
            # 1. 원본 이미지 다운로드 및 임시 저장
            file_id = uuid.uuid4().hex[:8]
            temp_input_path = os.path.join(temp_dir, f"in_{file_id}.png")
            
            req = urllib.request.Request(original_image_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                img_data = response.read()
            with open(temp_input_path, "wb") as f:
                f.write(img_data)
                
            # 2. 로컬 rembg CLI 비동기 실행 (데드락 원천 예방)
            file_name = f"item_{file_id}.png"
            temp_output_path = os.path.join(save_dir, file_name)
            
            rembg_exe = os.path.join(backend_dir, "venv", "Scripts", "rembg.exe")
            if not os.path.exists(rembg_exe):
                rembg_exe = "rembg"
                
            cmd = f'"{rembg_exe}" i "{temp_input_path}" "{temp_output_path}"'
            logger.info(f"Executing rembg CLI: {cmd}")
            
            # 스레드 풀 상에서 동기식 subprocess.run을 실행하여 asyncio loop 및 Windows Proactor/Selector 제약 해결
            def run_rembg():
                import subprocess
                cmd = [rembg_exe, "i", temp_input_path, temp_output_path]
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                res = subprocess.run(
                    cmd,
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
                
            # 프론트에서 접근할 수 있는 로컬 정적 경로 URL 지정
            backend_url = os.getenv("BACKEND_URL", "http://localhost:8002")
            result_url = f"{backend_url}/uploads/transparent/{file_name}"
            logger.info(f"rembg extraction success via CLI. Saved at: {result_url}")
            return result_url
            
        except Exception as e:
            logger.error(f"Local RemBG extraction failed via CLI: {str(e)}", exc_info=True)
            # 실패 시 원본 URL 을 반환하면 비투명 이미지가 transparent 로 저장되므로 None 반환
            return None


# =====================================================================
# 스마트 믹스앤매치 VTON (상/하의 조합) - 실제 PIL 합성
# =====================================================================

async def smart_layering_vton(top_id: Optional[int] = None, bottom_id: Optional[int] = None) -> str:
    """
    상/하의 조합 VTON. 캐시 HIT 시 비용 $0.
    Python Pillow(PIL)를 사용해 물리적 레이어 덧씌우기 수행.
    """
    logger.info(f"IDM-VTON Smart Layering — Top: {top_id}, Bottom: {bottom_id}")
    
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
                        backend_url = os.getenv("BACKEND_URL", "http://localhost:8002")
                        orig_url = f"{backend_url}{orig_url}"
                    
                    try:
                        generator = AIFittingPreGenerator()
                        new_transparent_url = await generator.extract_transparent_clothing(orig_url)
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
            bbox = b_img.getbbox()
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
            bbox = t_img.getbbox()
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
 
        # 1. 상/하의 둘 다 선택된 경우
        if top_id and bottom_id:
            top_path = await get_product_transparent_img(top_id)
            bottom_path = await get_product_transparent_img(bottom_id)
            
            # DB 동적 경로로 존재할 시
            if top_path and bottom_path:
                b_img = Image.open(bottom_path).convert("RGBA")
                base_img = apply_bottom_layer(base_img, b_img, gender)
                t_img = Image.open(top_path).convert("RGBA")
                base_img = apply_top_layer(base_img, t_img, gender)
            else:
                # 하드코딩 fallback 검사
                t_name = get_layer_name(top_id)
                b_name = get_layer_name(bottom_id)
                transparent_dir = os.path.join(backend_dir, "uploads", "transparent")
                trans_t_path = os.path.join(transparent_dir, f"{t_name}.png") if t_name else ""
                trans_b_path = os.path.join(transparent_dir, f"{b_name}.png") if b_name else ""
                
                if trans_t_path and trans_b_path and os.path.exists(trans_t_path) and os.path.exists(trans_b_path):
                    b_img = Image.open(trans_b_path).convert("RGBA")
                    base_img = apply_bottom_layer(base_img, b_img, gender)
                    t_img = Image.open(trans_t_path).convert("RGBA")
                    base_img = apply_top_layer(base_img, t_img, gender)
                else:
                    # 기존 하드코딩 콤보 png 리딩
                    merged_layer = None
                    if t_name == "shirt" and bottom_id == 3:
                        combo_path = os.path.join(frontend_mockups, "shirt_jeans.png")
                        if os.path.exists(combo_path):
                            merged_layer = Image.open(combo_path).convert("RGBA")
                    elif t_name == "sweater" and bottom_id == 3:
                        combo_path = os.path.join(frontend_mockups, "sweater_jeans.png")
                        if os.path.exists(combo_path):
                            merged_layer = Image.open(combo_path).convert("RGBA")
                            
                    if merged_layer is None and t_name and b_name:
                        b_path = os.path.join(frontend_mockups, f"{b_name}.png")
                        t_path = os.path.join(frontend_mockups, f"{t_name}.png")
                        if os.path.exists(b_path):
                            b_img = Image.open(b_path).convert("RGBA")
                            base_img = Image.alpha_composite(base_img, b_img.resize(base_img.size))
                        if os.path.exists(t_path):
                            t_img = Image.open(t_path).convert("RGBA")
                            base_img = Image.alpha_composite(base_img, t_img.resize(base_img.size))
        
        # 2. 하나만 선택된 경우
        else:
            single_id = top_id if top_id else bottom_id
            single_path = await get_product_transparent_img(single_id)
            
            if single_path:
                t_img = Image.open(single_path).convert("RGBA")
                if top_id:
                    base_img = apply_top_layer(base_img, t_img, gender)
                else:
                    base_img = apply_bottom_layer(base_img, t_img, gender)
            else:
                # 하드코딩 fallback 검사
                s_name = get_layer_name(single_id)
                if s_name:
                    transparent_dir = os.path.join(backend_dir, "uploads", "transparent")
                    trans_path = os.path.join(transparent_dir, f"{s_name}.png")
                    if os.path.exists(trans_path):
                        t_img = Image.open(trans_path).convert("RGBA")
                        if top_id:
                            base_img = apply_top_layer(base_img, t_img, gender)
                        else:
                            base_img = apply_bottom_layer(base_img, t_img, gender)
                    else:
                        s_path = os.path.join(frontend_mockups, f"{s_name}.png")
                        if os.path.exists(s_path):
                            merged_layer = Image.open(s_path).convert("RGBA")
                            if merged_layer.size != base_img.size:
                                merged_layer = merged_layer.resize(base_img.size)
                            base_img = Image.alpha_composite(base_img, merged_layer)
                    
        # 3. 브라우저 서빙용 파일 저장
        filename = f"vton_result_{uuid.uuid4().hex[:8]}.png"
        save_path = os.path.join(vton_save_dir, filename)
        
        base_img.save(save_path, "PNG")
        
        # FastAPI 정적 경로 서빙
        backend_url = os.getenv("BACKEND_URL", "http://localhost:8002")
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
    
    # [3] 외부 AI API 호출 시도 (현재는 Mock)
    fitting_url = None
    confidence = 0.0
    
    try:
        vton_api = os.getenv("VTON_API_ENDPOINT", "")
        
        if vton_api:
            # 실제 API 모드
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
            await asyncio.sleep(1.5)  # AI 렌더링 시간 시뮬레이션
            
            # 체형별 다른 마네킹 이미지 반환
            fallback_base = _BODY_TYPE_FALLBACKS.get(body_type, _BODY_TYPE_FALLBACKS["regular"])
            fitting_url = fallback_base
            
            # 신뢰도: 체형 데이터 완성도에 따라 가중치
            confidence = 0.85
            if shoulder_width > 0:
                confidence += 0.05
            if 150 <= height <= 200 and 40 <= weight <= 120:
                confidence += 0.05
                
    except Exception as e:
        logger.error(f"SmartFit API failed for {cache_key}: {str(e)}")
        # [4] Fallback: 기본 마네킹 이미지
        fitting_url = _BODY_TYPE_FALLBACKS["regular"]
        confidence = 0.60
    
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
