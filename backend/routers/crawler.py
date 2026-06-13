from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Header, Query, Request
import re
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import random
import urllib.request
import urllib.error
import json
from backend.crawler.engine import CrawlerEngine
from backend.crawler.ai_translator import AITranslatorPipeline
from backend.ai_engine.vton import AIFittingPreGenerator
from backend.database import SessionLocal, get_db
from backend.models import HQProduct, Category, Tenant, User, Brand
from backend.config import settings
from backend.utils.deps import get_current_admin
from backend.utils.gemini import generate_text, GeminiError
from backend.utils.brand_detector import detect_brand_id
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()
crawler_engine = CrawlerEngine(headless=True)
ai_pipeline = AITranslatorPipeline()
vton_engine = AIFittingPreGenerator()

# 전역 크롤링 동시 실행 방지 락 (G2: bool 플래그의 check-then-set 경쟁 제거)
import os
import threading
import uuid
import httpx
_crawler_lock = threading.Lock()

# 수집 이미지 영구 저장 위치 (webhook 도킹 — main.py 가 /uploads 로 서빙)
_UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
_CRAWLER_IMG_DIR = os.path.join(_UPLOADS_DIR, "crawler")


async def _rehost_images(urls: list, max_count: int = 30) -> list:
    """원격 이미지 URL을 backend/uploads/crawler 로 내려받아 영구 /uploads URL 로 변환.
    (원격 이미지는 핫링크 차단/만료 가능 → 쇼핑몰이 직접 보관). 실패 시 원본 URL 유지(best-effort)."""
    if not urls:
        return []
    os.makedirs(_CRAWLER_IMG_DIR, exist_ok=True)
    out = []
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0"}) as client:
        for u in urls[:max_count]:
            # 이미 우리 쇼핑몰 /uploads 에 올라온 이미지는 재다운로드 불필요(연결기가 선업로드한 경우)
            if u.startswith(settings.BACKEND_URL) and "/uploads/" in u:
                out.append(u)
                continue
            try:
                r = await client.get(u)
                r.raise_for_status()
                ext = ".jpg"
                low = u.lower().split("?")[0]
                for e in (".png", ".gif", ".webp", ".jpeg", ".jpg"):
                    if low.endswith(e):
                        ext = e
                        break
                fname = f"{uuid.uuid4().hex[:12]}{ext}"
                with open(os.path.join(_CRAWLER_IMG_DIR, fname), "wb") as f:
                    f.write(r.content)
                out.append(f"{settings.BACKEND_URL}/uploads/crawler/{fname}")
            except Exception as e:
                logger.warning(f"[webhook] 이미지 재호스팅 실패, 원본 URL 유지: {u} ({e})")
                out.append(u)
    return out


def compute_retail_price(wholesale, margin_type: str, margin_value) -> int:
    """[윈윈 도킹] 도매가(원) + 카테고리 마진 → 소매가.
    percent: 도매가×(1+%/100) 후 '천원 단위 올림'. fixed: 도매가 + 고정마진(원)."""
    import math
    try:
        w = int(float(wholesale or 0))
    except (ValueError, TypeError):
        w = 0
    if w <= 0:
        return 0
    mt = (margin_type or "percent").lower()
    try:
        mv = float(margin_value if margin_value is not None else 0)
    except (ValueError, TypeError):
        mv = 0.0
    if mt == "fixed":
        return w + int(round(mv))
    retail = w * (1.0 + mv / 100.0)
    return int(math.ceil(retail / 1000.0) * 1000)  # 천원 단위 올림

@router.get("/vendors")
def get_weishang_vendors(_admin: User = Depends(get_current_admin)):
    """ winwin_engine/weishang_vendors.json 에서 필수 필드만 추출하여 리턴 """
    import os
    import json
    
    crawler_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # backend
    json_path = os.path.join(crawler_dir, "crawler", "winwin_engine", "weishang_vendors.json")
    
    if not os.path.exists(json_path):
        alternative_path = os.path.join(os.path.dirname(crawler_dir), "backend", "crawler", "winwin_engine", "weishang_vendors.json")
        if os.path.exists(alternative_path):
            json_path = alternative_path
            
    if not os.path.exists(json_path):
        logger.warning(f"Weishang vendors file not found at: {json_path}")
        return []
        
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        slim_data = []
        for item in data:
            slim_data.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "url": item.get("url"),
                "category": item.get("category"),
                "vendor_code": item.get("vendor_code") or ""
            })
        return slim_data
    except Exception as e:
        logger.error(f"Failed to read vendors file: {e}")
        return []

class ScrapeRequest(BaseModel):
    target_urls: List[str]
    category_id: int
    exchange_rate: Optional[float] = 200.0
    margin_rate: Optional[float] = 1.3

class CrawlerSettingsUpdate(BaseModel):
    enabled: bool
    exchangeRate: float
    marginRate: float
    securityToken: str
    kakaoId: Optional[str] = ""
    kakaoPw: Optional[str] = ""
    bandId: Optional[str] = ""
    bandPw: Optional[str] = ""
    kakaoTargetUrl: Optional[str] = ""
    bandTargetUrl: Optional[str] = ""

class CrawlerTestRequest(BaseModel):
    raw_json: str

def extract_sizes_from_text(text: str, category_name: str) -> dict:
    if not text:
        return {}
    
    text_upper = text.upper()
    sizes = {}
    category_name_lower = category_name.lower()
    
    # 의류 카테고리
    if any(k in category_name_lower for k in ["의류", "상의", "하의", "아우터", "패션", "mens-clothing", "clothing"]):
        clothing_patterns = ["XS", "S", "M", "L", "XL", "XXL", "XXXL", "FREE"]
        for size in clothing_patterns:
            pattern = rf"\b{size}\b"
            if re.search(pattern, text_upper) or f" {size} " in text_upper or f"-{size}" in text_upper or f"/{size}" in text_upper:
                sizes[size] = 99
    # 신발 카테고리
    elif any(k in category_name_lower for k in ["신발", "슈즈", "스니커즈", "shoes"]):
        shoe_sizes = ["220", "225", "230", "235", "240", "245", "250", "255", "260", "265", "270", "275", "280", "285", "290"]
        for size in shoe_sizes:
            if size in text_upper:
                sizes[size] = 99
    # 가방 카테고리
    elif any(k in category_name_lower for k in ["가방", "백", "핸드백", "bags"]):
        bag_sizes = ["MINI", "MEDIUM", "LARGE", "FREE"]
        for size in bag_sizes:
            pattern = rf"\b{size}\b"
            if re.search(pattern, text_upper):
                formatted = size.capitalize() if size != "FREE" else "Free"
                sizes[formatted] = 99
                
    return sizes

# Helper to call Gemini mapping REST API
async def run_gemini_mapping(raw_data: dict, db: Session) -> dict:
    """
    Gemini 2.5 Flash API를 활용하여 임의의 크롤러 데이터를 표준 E-Commerce 상품 구조로 실시간 매핑
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise Exception("Gemini API Key가 백엔드 환경변수(.env)에 설정되어 있지 않습니다.")

    # 실시간 카테고리 구조 로드
    categories = db.query(Category).all()
    cat_list = [{"id": c.id, "name": c.name} for c in categories]
    
    
    system_instruction = (
        "You are an expert e-commerce product manager. "
        "Analyze the provided raw crawler JSON data and map/transform it into a standardized product structure in Korean. "
        "1. Translate product names and descriptions from Chinese/English/others to natural, highly appealing Korean. "
        "2. Select the most appropriate category ID from the provided list. "
        "3. Identify the product price field in the crawler data (usually in Chinese Yuan CNY, or USD), extract the raw numeric value, and assign it to base_price_foreign. "
        "4. Extract gallery images (array of URLs) and product video url (if any). "
        "The output MUST be a valid JSON object matching this schema exactly:\n"
        "{\n"
        "  \"kr_name\": \"Appeal Korean product name (max 50 chars)\",\n"
        "  \"kr_description\": \"Natural Korean product description / summary\",\n"
        "  \"category_id\": int (most matching category id from the provided list, default to 1 if none match),\n"
        "  \"base_price_foreign\": float or int (the foreign price identified in the data, default to 0.0),\n"
        "  \"images\": [\"url1\", \"url2\", ...] (extract image URLs from the data, default to empty list),\n"
        "  \"video_url\": \"extracted video URL or null\" (extract MP4 or streaming video URL if exists, otherwise null)\n"
        "}\n"
        "Return ONLY the raw JSON object. Do not include markdown code block syntax (like ```json ... ```)."
    )
    
    prompt = f"Available Category List: {json.dumps(cat_list, ensure_ascii=False)}\nRaw Crawler Data: {json.dumps(raw_data, ensure_ascii=False)}"
    
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        # 동기 urllib 호출을 스레드풀에서 실행 → async 이벤트 루프 블로킹 방지 (D3/F2)
        text_result = await loop.run_in_executor(None, generate_text, system_instruction, prompt)
    except GeminiError as e:
        logger.error(f"Gemini Mapping Call Failed: {e}")
        raise
    return json.loads(text_result)

# 1. 크롤러 설정 조회 API
@router.get("/settings")
def get_crawler_settings(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """ HQ Admin: 크롤러 연동 설정 조회 """
    hq = db.query(Tenant).filter(Tenant.domain == "hq.mall.com").first()
    if not hq:
        raise HTTPException(status_code=404, detail="HQ 테넌트를 찾을 수 없습니다.")
    
    theme = hq.theme_config or {}
    settings_data = theme.get("crawlerSettings", {
        "enabled": True,
        "exchangeRate": 200.0,
        "marginRate": 1.3,
        "securityToken": "LUXAI-WINWIN-TOKEN-1234",
        "kakaoId": "",
        "kakaoPw": "",
        "bandId": "",
        "bandPw": "",
        "kakaoTargetUrl": "",
        "bandTargetUrl": ""
    })
    # B4: 비밀번호 평문을 프론트로 반환하지 않음(마스킹). 설정 여부만 *Set 플래그로 노출.
    safe = dict(settings_data)
    safe["kakaoPwSet"] = bool((safe.get("kakaoPw") or "").strip())
    safe["bandPwSet"] = bool((safe.get("bandPw") or "").strip())
    safe["kakaoPw"] = ""
    safe["bandPw"] = ""
    return safe

# 2. 크롤러 설정 업데이트 API
@router.put("/settings")
def update_crawler_settings(payload: CrawlerSettingsUpdate, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """ HQ Admin: 크롤러 연동 설정 수정 """
    hq = db.query(Tenant).filter(Tenant.domain == "hq.mall.com").first()
    if not hq:
        raise HTTPException(status_code=404, detail="HQ 테넌트를 찾을 수 없습니다.")
    
    # SQLAlchemy JSON 변경 감지를 위해 새 dict 로 구성(동일 객체 변경은 감지 안 될 수 있음)
    theme = dict(hq.theme_config or {})
    existing = theme.get("crawlerSettings", {}) or {}
    new_settings = payload.model_dump()
    # B4: 비밀번호가 비어 오면 기존 저장값 유지(마스킹된 폼을 그대로 저장해 덮어쓰는 사고 방지)
    for pw_field in ("kakaoPw", "bandPw"):
        if not (new_settings.get(pw_field) or "").strip():
            new_settings[pw_field] = existing.get(pw_field, "")
    theme["crawlerSettings"] = new_settings

    hq.theme_config = theme
    db.commit()
    # 응답에서도 비밀번호 마스킹
    safe = dict(new_settings)
    safe["kakaoPwSet"] = bool((safe.get("kakaoPw") or "").strip())
    safe["bandPwSet"] = bool((safe.get("bandPw") or "").strip())
    safe["kakaoPw"] = ""
    safe["bandPw"] = ""
    return {"status": "success", "message": "크롤러 연동 설정이 성공적으로 저장되었습니다.", "settings": safe}

# 2-1. 윈윈크롤러 자동 연결(페어링) API
class CrawlerPairRequest(BaseModel):
    token: str

@router.post("/pair")
def pair_crawler(payload: CrawlerPairRequest, request: Request, db: Session = Depends(get_db)):
    """ 윈윈크롤러 자동 연결(페어링): 동일 PC(localhost)에서만 보안 토큰을 1클릭 동기화.
    관리자 로그인 없이 winwin → LUXAI 토큰을 맞춰주기 위한 전용 통로.
    보안 경계: localhost(127.0.0.1) 요청만 허용 → 외부 노출 환경에서는 차단된다. """
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1"):
        raise HTTPException(status_code=403, detail=f"자동 페어링은 동일 PC(localhost)에서만 허용됩니다. (요청 출처: {client_host})")
    token = (payload.token or "").strip()
    if len(token) < 8:
        raise HTTPException(status_code=400, detail="토큰은 8자 이상이어야 합니다.")
    if token == "LUXAI-WINWIN-TOKEN-1234":
        raise HTTPException(status_code=400, detail="기본 토큰은 보안상 사용할 수 없습니다. 고유한 토큰을 사용하세요.")
    hq = db.query(Tenant).filter(Tenant.domain == "hq.mall.com").first()
    if not hq:
        raise HTTPException(status_code=404, detail="HQ 테넌트를 찾을 수 없습니다.")
    # 기존 update_crawler_settings 와 동일하게 새 dict 재구성(JSON 변경 감지)
    theme = dict(hq.theme_config or {})
    cs = dict(theme.get("crawlerSettings", {}) or {})
    cs["securityToken"] = token
    cs["enabled"] = True
    theme["crawlerSettings"] = cs
    hq.theme_config = theme
    db.commit()
    logger.info(f"[PAIR] 윈윈크롤러 자동 연결 완료 (localhost). token_len={len(token)}")
    return {"status": "success", "message": "윈윈크롤러와 자동 연결되었습니다.", "enabled": True}

# 3. 크롤러 데이터 AI 해석 테스트 API
@router.post("/test-mapping")
async def test_crawler_mapping(payload: CrawlerTestRequest, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """ HQ Admin: 크롤러 JSON 데이터 AI 해석 가상 매핑 테스트 """
    try:
        raw_data = json.loads(payload.raw_json)
    except Exception:
        raise HTTPException(status_code=400, detail="유효한 JSON 포맷이 아닙니다.")
    
    try:
        mapped = await run_gemini_mapping(raw_data, db)
        
        # 가격 연산
        hq = db.query(Tenant).filter(Tenant.domain == "hq.mall.com").first()
        theme = hq.theme_config or {} if hq else {}
        crawler_settings = theme.get("crawlerSettings", {})
        
        exchange_rate = float(crawler_settings.get("exchangeRate", 200.0))
        margin_rate = float(crawler_settings.get("marginRate", 1.3))
        
        foreign_price = mapped.get("base_price_foreign", 0.0)
        calculated_price = foreign_price * exchange_rate * margin_rate
        base_price = int(round(calculated_price, -2)) if calculated_price > 0 else 30000
        
        # 카테고리 이름 매칭
        cat = db.query(Category).filter(Category.id == mapped.get("category_id", 1)).first()
        category_name = cat.name if cat else "미분류"
        
        # 가상 데이터에서 사이즈 감지 테스트
        title_text = raw_data.get("title") or raw_data.get("goodsName") or mapped.get("kr_name") or ""
        desc_text = mapped.get("kr_description") or ""
        parsed_sizes = extract_sizes_from_text(f"{title_text} {desc_text}", category_name)
        
        return {
            "status": "success",
            "mapped_data": mapped,
            "calculated_price": base_price,
            "category_name": category_name,
            "parsed_sizes": parsed_sizes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 해석 중 오류 발생: {str(e)}")

# 4. 윈윈크롤러3 실시간 웹훅 수신 API
@router.post("/webhook")
async def crawler_webhook(
    payload: Dict[str, Any], 
    bg_tasks: BackgroundTasks,
    token: Optional[str] = Query(None),
    x_crawler_token: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    윈윈크롤러3 및 타 크롤러 전용 AI 자동화 웹훅
    """
    hq = db.query(Tenant).filter(Tenant.domain == "hq.mall.com").first()
    if not hq:
        raise HTTPException(status_code=404, detail="HQ 테넌트를 찾을 수 없습니다.")
    
    theme = hq.theme_config or {}
    crawler_settings = theme.get("crawlerSettings", {
        "enabled": True,
        "exchangeRate": 200.0,
        "marginRate": 1.3,
        "securityToken": "LUXAI-WINWIN-TOKEN-1234"
    })
    
    # 토큰 검증 (B3: 기본값/미설정 토큰은 fail-closed 로 거부 — 고유 토큰 강제)
    req_token = token or x_crawler_token
    DEFAULT_TOKEN = "LUXAI-WINWIN-TOKEN-1234"
    configured_token = (crawler_settings.get("securityToken") or "").strip()
    if not configured_token or configured_token == DEFAULT_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="크롤러 보안 토큰이 미설정/기본값 상태입니다. 관리자 설정에서 고유한 securityToken 을 지정해야 웹훅이 활성화됩니다."
        )
    if req_token != configured_token:
        raise HTTPException(status_code=401, detail="보안 토큰이 일치하지 않습니다.")
    
    # 자동 등록 기능 체크
    if not crawler_settings.get("enabled", True):
        return {"status": "ignored", "message": "자동 등록 설정이 비활성화되어 있습니다."}
    
    # 1) 원본 payload 에서 기본 필드 추출 (Gemini 실패/미설정 대비 폴백 소스)
    raw_title = (payload.get("title") or payload.get("goodsName") or payload.get("name") or "").strip()
    raw_desc = (payload.get("desc") or payload.get("description") or payload.get("content") or "").strip()
    raw_images = payload.get("images") or payload.get("image_urls") or []
    if isinstance(raw_images, str):
        raw_images = [raw_images]
    source_url = payload.get("original_url") or payload.get("source_url") or "winwin_crawler3"

    # 최소 검증: 콘텐츠가 전혀 없으면 거부
    if not raw_title and not raw_desc and not raw_images:
        raise HTTPException(status_code=400, detail="수집 데이터가 비어 있습니다 (title/desc/images 중 하나는 필요).")

    # 2) 중복 방지 — 같은 출처 URL + 같은 원본 제목이면 재등록하지 않음 (재시도/중복 전송 대비)
    if raw_title:
        existing = db.query(HQProduct).filter(
            HQProduct.original_source_url == source_url,
            HQProduct.cn_name == raw_title,
        ).first()
        if existing:
            return {"status": "duplicate", "message": "이미 등록된 상품입니다.", "product_id": existing.id}

    # 3) AI 매핑 시도 — 실패(키없음/통신오류)해도 원본 데이터로 폴백 등록 (도킹이 끊기지 않게)
    try:
        mapped = await run_gemini_mapping(payload, db)
    except Exception as e:
        logger.warning(f"[webhook] Gemini 매핑 실패 → 원본 데이터로 폴백 등록: {e}")
        mapped = {}

    # 4) 필드 확정 (매핑값 우선, 없으면 원본 폴백) — kr_name 은 절대 None 금지
    kr_name = (mapped.get("kr_name") or raw_title or "[수집] 미상 상품").strip()[:50]
    kr_desc = mapped.get("kr_description") or raw_desc
    category_id = mapped.get("category_id") or payload.get("category_id")
    # [윈윈 도킹] 윈윈이 보낸 카테고리 '이름'(가방/지갑/신발 등)으로도 매칭 (이미 분류된 상태)
    if not category_id and payload.get("category"):
        _cat_by_name = db.query(Category).filter(Category.name == str(payload.get("category")).strip()).first()
        if _cat_by_name:
            category_id = _cat_by_name.id
    category_id = category_id or 1

    # 5) 가격: [윈윈 도킹] 원화 '도매가'가 오면 카테고리별 마진으로 소매가 산출.
    #    (윈윈은 지침공식으로 도매가를 이미 계산해 보냄 → 더블계산 방지)
    #    도매가가 없으면(타 크롤러/구버전) 기존 외화×환율×마진으로 폴백.
    wholesale_krw = payload.get("wholesale_price_krw") or payload.get("wholesale_price") or 0
    try:
        wholesale_krw = int(float(wholesale_krw))
    except (ValueError, TypeError):
        wholesale_krw = 0

    if wholesale_krw > 0:
        _mcat = db.query(Category).filter(Category.id == category_id).first()
        _m_type = getattr(_mcat, "margin_type", None) or "percent"
        _m_value = getattr(_mcat, "margin_value", None)
        if _m_value is None:
            _m_value = 30.0
        base_price = compute_retail_price(wholesale_krw, _m_type, _m_value)
    else:
        exchange_rate = float(crawler_settings.get("exchangeRate", 200.0))
        margin_rate = float(crawler_settings.get("marginRate", 1.3))
        foreign_price = mapped.get("base_price_foreign") or payload.get("price") or 0
        try:
            foreign_price = float(foreign_price)
        except (ValueError, TypeError):
            foreign_price = 0.0
        calculated_price = foreign_price * exchange_rate * margin_rate
        base_price = int(round(calculated_price, -2)) if calculated_price > 0 else 30000

    # 6) 이미지: http 원격 URL 만 추려 /uploads 로 영구 재호스팅 (없으면 placeholder)
    src_images = mapped.get("images") or raw_images or []
    web_images = await _rehost_images([u for u in src_images if isinstance(u, str) and u.startswith("http")])
    if not web_images:
        web_images = ["/placeholder.png"]

    # 7) 카테고리 검증 (없는 id 면 첫 카테고리로 폴백) + 사이즈 파싱
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        cat = db.query(Category).first()
        category_id = cat.id if cat else 1
    cat_name = cat.name if cat else ""
    parsed_sizes = extract_sizes_from_text(f"{kr_name} {kr_desc}", cat_name)

    # 7-2) 브랜드 판별
    detected_brand_id = detect_brand_id(db, kr_name, kr_desc, cat_name)

    # 8) 상품 등록
    new_prod = HQProduct(
        category_id=category_id,
        brand_id=detected_brand_id,
        original_source_url=source_url,
        cn_name=raw_title or kr_name,
        kr_name=kr_name,
        kr_description=kr_desc,
        base_price=base_price,
        wholesale_price=wholesale_krw,  # [윈윈 도킹] 도매원가 보관 (마진 변경 시 재계산용)
        images=web_images,
        video_url=mapped.get("video_url"),
        status="PENDING",
    )
    if parsed_sizes:
        new_prod.size_stock_config = parsed_sizes
        new_prod.stock_quantity = sum(parsed_sizes.values())
    else:
        new_prod.stock_quantity = 0
        new_prod.size_stock_config = None

    db.add(new_prod)
    db.commit()
    db.refresh(new_prod)

    return {
        "status": "success",
        "message": f"수집 데이터 등록 완료: {new_prod.kr_name} (도매 {wholesale_krw:,}원 → 소매 {base_price:,}원, 사이즈 {len(parsed_sizes)}종, 이미지 {len(web_images)}장)",
        "product_id": new_prod.id,
        "wholesale_price": wholesale_krw,
        "price": base_price,
        "parsed_sizes": parsed_sizes,
        "ai_mapped": bool(mapped),
    }

# ====================================================
# 기존 백그라운드 크롤러 구동 엔드포인트
# ====================================================
async def background_scrape_task(
    urls: List[str],
    category_id: int,
    exchange_rate: float,
    margin_rate: float
):
    db = SessionLocal()
    try:
        # 카테고리 정보 조회
        cat = db.query(Category).filter(Category.id == category_id).first()
        category_name = cat.name if cat else "미분류"
        
        crawler_engine.start_session()
        for url in urls:
            raw_data = await crawler_engine.scrape_album(url)
            
            # [수집 순서 개선] 위챗 앨범은 최신 수집물이 리스트 전면에 오므로,
            # 과거 수집 상품부터 역순(reversed)으로 DB에 저장해야 최신 등록 상품이 쇼핑몰 최상단에 뜨게 됩니다.
            for item in reversed(raw_data):
                image_url = item.get('image_url', '')
                if not image_url:
                    continue
                
                existing = db.query(HQProduct).filter(
                    (HQProduct.original_source_url == url) & 
                    (HQProduct.cn_name == item.get('title', ''))
                ).first()
                if existing:
                    logger.info(f"Product already exists, skip: {item.get('title', '')}")
                    continue
                
                # Gemini 실시간 한글 번역/정제
                trans = await ai_pipeline.translate_product_info(item.get('title', ''), item.get('desc', ''))
                kr_name = trans.get('kr_name', f"[수집] {item.get('title', '')}")
                kr_desc = trans.get('kr_description', item.get('desc', ''))
                
                # 어드민 설정 환율 + 마진 기반 가격 자동 책정
                cn_price = 150.0
                price_match = re.search(r'(\d+)\s*(?:元|¥|CNY)', item.get('desc', ''))
                if price_match:
                    cn_price = float(price_match.group(1))
                    
                calculated_price = cn_price * exchange_rate * margin_rate
                base_price = int(round(calculated_price, -2)) if calculated_price > 0 else 39000
                
                # 본문에서 사이즈 정밀 감지
                parsed_sizes = extract_sizes_from_text(f"{kr_name} {kr_desc}", category_name)
                
                # 백그라운드 AI 누끼 가공 (exec 기반 비동기 rembg 실행)
                transparent_url = await vton_engine.extract_transparent_clothing(
                    original_image_url=image_url
                )
                
                # 브랜드 판별
                detected_brand_id = detect_brand_id(db, kr_name, kr_desc, category_name)

                new_prod = HQProduct(
                    category_id=category_id,
                    brand_id=detected_brand_id,
                    original_source_url=url,
                    cn_name=item.get('title', ''),
                    kr_name=kr_name[:50], # 50자 제한
                    kr_description=kr_desc,
                    base_price=base_price,
                    images=[image_url],
                    transparent_item_image_url=transparent_url,
                    status="PENDING"
                )
                
                if parsed_sizes:
                    new_prod.size_stock_config = parsed_sizes
                    new_prod.stock_quantity = sum(parsed_sizes.values())
                else:
                    # 기본 사이즈런 99개 지정
                    default_sizes = {}
                    if any(k in category_name for k in ["의류", "상의", "하의", "아우터"]):
                        default_sizes = { "S": 99, "M": 99, "L": 99, "XL": 99, "Free": 99 }
                    elif any(k in category_name for k in ["가방", "백"]):
                        default_sizes = { "Mini": 99, "Medium": 99, "Large": 99, "Free": 99 }
                    elif any(k in category_name for k in ["신발", "슈즈"]):
                        default_sizes = { "230": 99, "235": 99, "240": 99, "245": 99, "250": 99, "255": 99, "260": 99, "265": 99, "270": 99, "275": 99, "280": 99 }
                    
                    if default_sizes:
                        new_prod.size_stock_config = default_sizes
                        new_prod.stock_quantity = sum(default_sizes.values())
                    else:
                        new_prod.stock_quantity = 0
                
                db.add(new_prod)
                db.commit()
                logger.info(f"Saved crawler item {new_prod.kr_name}")
                
    except Exception as e:
        logger.error(f"Crawler background task error: {str(e)}")
        db.rollback()
    finally:
        crawler_engine.close_session()
        db.close()

class ScrapeDirectRequest(BaseModel):
    target_url: str
    category_id: int
    exchange_rate: Optional[float] = 200.0
    margin_rate: Optional[float] = 1.3

@router.post("/scrape-direct")
async def scrape_direct_product(payload: ScrapeDirectRequest, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """
    URL에서 실시간으로 1개 상품을 스크래핑한 후,
    Gemini AI 정제 및 환율/마진율 가격 계산을 거쳐, 
    현재 작성 중인 프론트엔드 상품 등록 폼에 채워넣을 JSON 데이터 구조를 즉시 동기식으로 반환합니다.
    """
    if not payload.target_url:
        raise HTTPException(status_code=400, detail="URL 주소가 입력되지 않았습니다.")
        
    try:
        # 1. 크롤러 세션 시작 및 스크랩 실행
        crawler_engine.start_session()
        raw_items = await crawler_engine.scrape_album(payload.target_url)
    except Exception as crawler_err:
        logger.error(f"Real-time crawling failed: {crawler_err}")
        raise HTTPException(status_code=500, detail=f"크롤링 실패: {str(crawler_err)}")
    finally:
        crawler_engine.close_session()
        
    if not raw_items:
        raise HTTPException(status_code=400, detail="입력하신 URL에서 수집할 이미지나 상품 정보를 찾을 수 없습니다. 주소를 다시 확인하거나, 웨이상 로그인 세션이 유효한지 확인하세요.")
        
    # 첫 번째 상품 추출
    target_item = raw_items[0]
    
    # 2. Gemini mapping을 위해 payload 구성
    raw_data = {
        "title": target_item.get("title", "수집 상품"),
        "goodsName": target_item.get("title", ""),
        "desc": target_item.get("desc", ""),
        "images": [target_item.get("image_url")]
    }
    
    try:
        mapped = await run_gemini_mapping(raw_data, db)
        
        # 환율 및 마진 계산
        exchange_rate = float(payload.exchange_rate or 200.0)
        margin_rate = float(payload.margin_rate or 1.3)
        
        # 외화 원가 추출
        foreign_price = mapped.get("base_price_foreign", 0.0)
        if foreign_price <= 0:
            price_match = re.search(r'(\d+)\s*(?:元|¥|CNY)', target_item.get("desc", ""))
            if price_match:
                foreign_price = float(price_match.group(1))
            else:
                foreign_price = 150.0
                
        calculated_price = foreign_price * exchange_rate * margin_rate
        base_price = int(round(calculated_price, -2)) if calculated_price > 0 else 30000
        
        cat = db.query(Category).filter(Category.id == mapped.get("category_id", 1)).first()
        category_name = cat.name if cat else "미분류"
        
        # 브랜드 검출
        detected_brand_id = detect_brand_id(
            db, 
            mapped.get("kr_name", target_item.get("title", "")), 
            mapped.get("kr_description", target_item.get("desc", "")),
            category_name
        )
        brand_name = "미지정"
        brand_eng_name = ""
        if detected_brand_id:
            brand_obj = db.query(Brand).filter(Brand.id == detected_brand_id).first()
            if brand_obj:
                brand_name = brand_obj.name
                brand_eng_name = brand_obj.eng_name
        
        # 사이즈 검출
        title_text = target_item.get("title", "")
        desc_text = mapped.get("kr_description", "")
        parsed_sizes = extract_sizes_from_text(f"{title_text} {desc_text}", category_name)
        
        # mapped_data 에도 brand_id 정보 주입
        mapped_brand = dict(mapped)
        mapped_brand["brand_id"] = detected_brand_id
        mapped_brand["brand_name"] = brand_name
        mapped_brand["brand_eng_name"] = brand_eng_name
        
        return {
            "status": "success",
            "mapped_data": mapped_brand,
            "calculated_price": base_price,
            "category_name": category_name,
            "parsed_sizes": parsed_sizes,
            "original_image": target_item.get("image_url")
        }
    except Exception as e:
        logger.error(f"Real-time AI Mapping error: {str(e)}")
        # 폴백 매핑 시에도 브랜드 판별 시도
        cat_fb = db.query(Category).filter(Category.id == payload.category_id).first()
        fallback_cat_name = cat_fb.name if cat_fb else "미분류"
        detected_brand_id = detect_brand_id(
            db, 
            target_item.get("title", ""), 
            target_item.get("desc", ""),
            fallback_cat_name
        )
        brand_name = "미지정"
        brand_eng_name = ""
        if detected_brand_id:
            brand_obj = db.query(Brand).filter(Brand.id == detected_brand_id).first()
            if brand_obj:
                brand_name = brand_obj.name
                brand_eng_name = brand_obj.eng_name
                
        return {
            "status": "success",
            "mapped_data": {
                "kr_name": target_item.get("title", "수집 상품"),
                "kr_description": target_item.get("desc", "설명"),
                "category_id": payload.category_id,
                "brand_id": detected_brand_id,
                "brand_name": brand_name,
                "brand_eng_name": brand_eng_name,
                "images": [target_item.get("image_url")],
                "video_url": None
            },
            "calculated_price": 39000,
            "category_name": "미분류",
            "parsed_sizes": {},
            "original_image": target_item.get("image_url")
        }

@router.post("/start")
async def start_crawler(req: ScrapeRequest, bg_tasks: BackgroundTasks, _admin: User = Depends(get_current_admin)):
    """
    Triggers WeChat album crawler in background.
    """
    if not req.target_urls:
        raise HTTPException(status_code=400, detail="No URLs provided.")
    bg_tasks.add_task(
        background_scrape_task, 
        req.target_urls,
        req.category_id,
        req.exchange_rate or 200.0,
        req.margin_rate or 1.3
    )
    return {
        "status": "success",
        "message": f"백그라운드에서 {len(req.target_urls)}개의 URL 스마트 일괄 수집 및 AI 가공이 시작되었습니다."
    }

class WeChatQRLoginRequest(BaseModel):
    headless: bool = False

@router.post("/wechat-qr-login")
def wechat_qr_login(payload: WeChatQRLoginRequest, _admin: User = Depends(get_current_admin)):
    """
    위챗 QR 로그인을 위한 브라우저를 띄우고 로그인이 끝날 때까지 대기하여 세션 정보를 저장합니다.
    """
    # G2: 서버에서 GUI 브라우저를 띄우는 동작은 배포 환경에서 위험/불가 → 기본 비활성(명시적 옵트인 필요)
    if os.getenv("ENABLE_WECHAT_QR_LOGIN") != "1":
        raise HTTPException(
            status_code=400,
            detail="서버 측 위챗 QR 로그인(GUI 브라우저 구동)은 비활성화되어 있습니다. 운영자가 ENABLE_WECHAT_QR_LOGIN=1 로 옵트인해야 합니다."
        )
    from playwright.sync_api import sync_playwright

    auth_state_path = "auth_state.json"
    LOGIN_URL = "https://www.szwego.com/static/index.html?link_type=pc_login#/pc_login"
    
    def run_login():
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=payload.headless,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context()
            page = context.new_page()
            
            page.goto(LOGIN_URL, timeout=60000)
            
            try:
                # URL이 변경될 때까지 대기 (pc_login 단어가 주소에서 사라질 때까지)
                page.wait_for_url(lambda url: "pc_login" not in url, timeout=180000)
                page.wait_for_timeout(3000)
                context.storage_state(path=auth_state_path)
                browser.close()
                return {"status": "success", "message": "위챗 로그인이 완료되어 세션이 저장되었습니다."}
            except Exception as e:
                browser.close()
                return {"status": "error", "message": f"로그인 대기 시간 초과 또는 실패: {str(e)}"}
                
    result = run_login()
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result

class PlatformScrapeRequest(BaseModel):
    platform: str
    target_url: str
    target_count: int = 1
    exchange_rate: float = 200.0
    margin_rate: float = 1.3
    category_id: int = 1

# 백그라운드 수집을 수행할 동기식 스레드 래퍼 함수
def run_async_scraping_job(
    vendor_url: str,
    target_count: int,
    exchange_rate: float,
    margin_rate: float,
    category_id: int
):
    db = SessionLocal()
    try:
        logger.info(f"Background WeChat scraping job started for URL: {vendor_url}")
        from backend.crawler.winwin_adapter import scrape_weishang_album_sync
        
        scraped = scrape_weishang_album_sync(
            vendor_url=vendor_url,
            target_count=target_count,
            exchange_rate=exchange_rate,
            margin_rate=margin_rate,
            category_id=category_id,
            db=db
        )
        
        # AI 누끼 선 가공 백그라운드 연이어 실행 (수집 시 자동 가공은 API 비용 과다 소모로 제외, 관리자 페이지에서 수동 1컷 가공으로 대체)
        # from backend.routers.admin import pre_generate_transparent_clothing_task
        # import asyncio
        # 
        # for prod in scraped:
        #     if "id" in prod:
        #         try:
        #             # 동기 백그라운드 스레드 상에서 async 함수를 안전하게 동기 호출
        #             loop = asyncio.new_event_loop()
        #             asyncio.set_event_loop(loop)
        #             loop.run_until_complete(pre_generate_transparent_clothing_task(prod["id"]))
        #             loop.close()
        #         except Exception as vton_err:
        #             logger.error(f"VTON pre-generation background error for product {prod.get('id')}: {vton_err}")
                    
        logger.info(f"Background WeChat scraping job finished. Processed {len(scraped)} items.")
    except Exception as err:
        logger.error(f"Background WeChat scraping job failed: {err}", exc_info=True)
    finally:
        _crawler_lock.release()
        db.close()

@router.post("/scrape-platform")
async def scrape_platform(payload: PlatformScrapeRequest, bg_tasks: BackgroundTasks, _admin: User = Depends(get_current_admin)):
    """
    윈윈크롤러3 어댑터를 호출하여 웨이상에서 상품을 긁어와 DB에 PENDING 상태로 등록합니다.
    비동기 백그라운드로 처리하여 웹 연결 타임아웃을 방지하며, 동시 실행 락을 탑재합니다.
    """
    if payload.platform != "weishang":
        raise HTTPException(status_code=400, detail="현재는 'weishang'(웨이상) 플랫폼 크롤러 연동만 지원됩니다.")

    # G2: Lock 으로 원자적 동시실행 방지 (acquire 실패 = 이미 실행 중). 작업 종료 시 백그라운드에서 release.
    if not _crawler_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="현재 다른 도매 업체의 수집 봇이 이미 파견 중입니다. 잠시 후 다시 시도해 주세요."
        )

    # 백그라운드로 작업 이관 (Timeout 방지)
    bg_tasks.add_task(
        run_async_scraping_job,
        payload.target_url,
        payload.target_count,
        payload.exchange_rate,
        payload.margin_rate,
        payload.category_id
    )
    
    return {
        "status": "success",
        "message": "수집 봇이 성공적으로 백그라운드에 파견되었습니다. 1~2분 뒤 대기소 목록을 새로고침 하세요."
    }
