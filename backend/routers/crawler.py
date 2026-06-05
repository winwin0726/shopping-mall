from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Header, Query
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
from backend.models import HQProduct, Category, Tenant, User
from backend.config import settings
from backend.utils.deps import get_current_admin
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter()
crawler_engine = CrawlerEngine(headless=True)
ai_pipeline = AITranslatorPipeline()
vton_engine = AIFittingPreGenerator()

# 전역 크롤링 실행상태 락 플래그
_is_crawler_running = False

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
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
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
    
    request_payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"System Instruction: {system_instruction}\nUser Prompt: {prompt}"}
                ]
            }
        ]
    }
    
    data_bytes = json.dumps(request_payload).encode('utf-8')
    req = urllib.request.Request(
        url, 
        data=data_bytes,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_body = response.read().decode('utf-8')
            res_json = json.loads(res_body)
            
            # 파싱 결과 추출
            candidates = res_json.get("candidates", [])
            if not candidates:
                raise Exception("Gemini API returned empty candidate list.")
            
            text_result = candidates[0]["content"]["parts"][0]["text"].strip()
            
            # Markdown block formatting strip
            if text_result.startswith("```json"):
                text_result = text_result[7:]
            if text_result.endswith("```"):
                text_result = text_result[:-3]
            text_result = text_result.strip()
            
            parsed_data = json.loads(text_result)
            return parsed_data
            
    except urllib.error.HTTPError as he:
        err_body = he.read().decode('utf-8')
        logger.error(f"Gemini API Http Error: {err_body}")
        raise Exception(f"Gemini API HTTP Error {he.code}: {err_body}")
    except Exception as e:
        logger.error(f"Gemini Mapping Call Failed: {str(e)}")
        raise e

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
    return settings_data

# 2. 크롤러 설정 업데이트 API
@router.put("/settings")
def update_crawler_settings(payload: CrawlerSettingsUpdate, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """ HQ Admin: 크롤러 연동 설정 수정 """
    hq = db.query(Tenant).filter(Tenant.domain == "hq.mall.com").first()
    if not hq:
        raise HTTPException(status_code=404, detail="HQ 테넌트를 찾을 수 없습니다.")
    
    theme = hq.theme_config or {}
    theme["crawlerSettings"] = payload.dict()
    
    hq.theme_config = theme
    db.commit()
    return {"status": "success", "message": "크롤러 연동 설정이 성공적으로 저장되었습니다.", "settings": theme["crawlerSettings"]}

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
    
    # 토큰 검증
    req_token = token or x_crawler_token
    configured_token = crawler_settings.get("securityToken", "LUXAI-WINWIN-TOKEN-1234")
    if configured_token and req_token != configured_token:
        raise HTTPException(status_code=401, detail="보안 토큰이 일치하지 않습니다.")
    
    # 자동 등록 기능 체크
    if not crawler_settings.get("enabled", True):
        return {"status": "ignored", "message": "자동 등록 설정이 비활성화되어 있습니다."}
    
    try:
        mapped = await run_gemini_mapping(payload, db)
    except Exception as e:
        logger.error(f"Webhook Gemini Parse Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Gemini AI 해석 실패: {str(e)}")
    
    # 가격 산출 (반올림 백원 단위)
    foreign_price = mapped.get("base_price_foreign", 0.0)
    exchange_rate = float(crawler_settings.get("exchangeRate", 200.0))
    margin_rate = float(crawler_settings.get("marginRate", 1.3))
    calculated_price = foreign_price * exchange_rate * margin_rate
    base_price = int(round(calculated_price, -2)) if calculated_price > 0 else 30000
    
    # 카테고리 이름 조회 및 사이즈 매핑
    cat = db.query(Category).filter(Category.id == mapped.get("category_id", 1)).first()
    cat_name = cat.name if cat else ""
    
    title_text = payload.get("title") or payload.get("goodsName") or mapped.get("kr_name") or ""
    desc_text = mapped.get("kr_description") or ""
    parsed_sizes = extract_sizes_from_text(f"{title_text} {desc_text}", cat_name)
    
    # 상품 DB 등록
    new_prod = HQProduct(
        category_id=mapped.get("category_id", 1),
        original_source_url=payload.get("original_url") or payload.get("source_url") or "winwin_crawler3",
        cn_name=title_text,
        kr_name=mapped.get("kr_name"),
        kr_description=desc_text,
        base_price=base_price,
        images=mapped.get("images") or ["/placeholder.png"],
        video_url=mapped.get("video_url"),
        status="APPROVED"
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
    
    # 백그라운드 AI 누끼 선 생성 예약 (수집 시 자동 가공은 API 비용 과다 소모로 제외, 관리자 페이지에서 수동 1컷 가공으로 대체)
    # from backend.routers.admin import pre_generate_transparent_clothing_task
    # bg_tasks.add_task(pre_generate_transparent_clothing_task, new_prod.id)
    
    return {
        "status": "success",
        "message": f"크롤러 데이터가 AI 자동 정제 및 {len(parsed_sizes)}개 사이즈 자동 수량 매핑 후 등록되었습니다: {new_prod.kr_name}",
        "product_id": new_prod.id,
        "price": base_price,
        "parsed_sizes": parsed_sizes
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
            
            for item in raw_data:
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
                
                new_prod = HQProduct(
                    category_id=category_id,
                    original_source_url=url,
                    cn_name=item.get('title', ''),
                    kr_name=kr_name[:50], # 50자 제한
                    kr_description=kr_desc,
                    base_price=base_price,
                    images=[image_url],
                    transparent_item_image_url=transparent_url,
                    status="APPROVED"
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
        
        # 사이즈 검출
        title_text = target_item.get("title", "")
        desc_text = mapped.get("kr_description", "")
        parsed_sizes = extract_sizes_from_text(f"{title_text} {desc_text}", category_name)
        
        return {
            "status": "success",
            "mapped_data": mapped,
            "calculated_price": base_price,
            "category_name": category_name,
            "parsed_sizes": parsed_sizes,
            "original_image": target_item.get("image_url")
        }
    except Exception as e:
        logger.error(f"Real-time AI Mapping error: {str(e)}")
        return {
            "status": "success",
            "mapped_data": {
                "kr_name": target_item.get("title", "수집 상품"),
                "kr_description": target_item.get("desc", "설명"),
                "category_id": payload.category_id,
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
    from playwright.sync_api import sync_playwright
    import os
    
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
    global _is_crawler_running
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
        _is_crawler_running = False
        db.close()

@router.post("/scrape-platform")
async def scrape_platform(payload: PlatformScrapeRequest, bg_tasks: BackgroundTasks, _admin: User = Depends(get_current_admin)):
    """
    윈윈크롤러3 어댑터를 호출하여 웨이상에서 상품을 긁어와 DB에 PENDING 상태로 등록합니다.
    비동기 백그라운드로 처리하여 웹 연결 타임아웃을 방지하며, 동시 실행 락을 탑재합니다.
    """
    global _is_crawler_running
    
    if payload.platform != "weishang":
        raise HTTPException(status_code=400, detail="현재는 'weishang'(웨이상) 플랫폼 크롤러 연동만 지원됩니다.")
        
    if _is_crawler_running:
        raise HTTPException(
            status_code=400, 
            detail="현재 다른 도매 업체의 수집 봇이 이미 파견 중입니다. 잠시 후 다시 시도해 주세요."
        )
        
    _is_crawler_running = True
    
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
