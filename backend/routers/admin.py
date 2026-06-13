from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from pydantic import BaseModel
from backend.database import get_db
from backend.models import HQProduct, Category, User, Tenant, SupportTicket, Brand
from backend.config import settings
from backend.utils.gemini import generate_text, GeminiError
from backend.crawler.ai_translator import AITranslatorPipeline

router = APIRouter()

class ProductStatusUpdate(BaseModel):
    status: str # "APPROVED" | "REJECTED" | "PENDING"
    category_id: Optional[int] = None

class CategoryCreate(BaseModel):
    name: str # e.g. "아우터"
    slug: str # e.g. "outer"
    parent_id: Optional[int] = None

class CategoryResponse(BaseModel):
    id: int
    name: str
    slug: str
    parent_id: Optional[int]
    margin_type: Optional[str] = "percent"   # [윈윈 도킹] 'percent' | 'fixed'
    margin_value: Optional[float] = 30.0      # percent면 %, fixed면 원

    model_config = {"from_attributes": True}

import logging
logger = logging.getLogger(__name__)

async def pre_generate_transparent_clothing_task(product_id: int):
    from backend.database import SessionLocal
    from backend.models import HQProduct
    from backend.ai_engine.vton import AIFittingPreGenerator
    
    db = SessionLocal()
    try:
        product = db.query(HQProduct).filter(HQProduct.id == product_id).first()
        if not product:
            return
            
        # 대표 이미지가 있고 아직 transparent_item_image_url 이 없는 경우에만 실행
        if product.images and len(product.images) > 0:
            orig_url = product.images[0]
            # 로컬 정적 서비스 경로 대응
            if not orig_url.startswith("http") and not orig_url.startswith("/"):
                orig_url = f"{settings.BACKEND_URL}/{orig_url}"
            elif orig_url.startswith("/"):
                orig_url = f"{settings.BACKEND_URL}{orig_url}"
                
            generator = AIFittingPreGenerator()
            transparent_url = await generator.extract_transparent_clothing(orig_url)
            if transparent_url:
                product.transparent_item_image_url = transparent_url
                db.commit()
                logger.info(f"Background transparent image pre-generation success for Product {product_id}: {transparent_url}")
                # [고도화 추가] 백그라운드 누끼 가공 성공 시 마네킹 착장 및 마스크 사전 렌더링 자동 기동
                try:
                    await generator.pre_render_mannequin_fit(db, product.id)
                except Exception as e_pr:
                    logger.error(f"Background pre-render mannequin fit failed for Product {product_id}: {e_pr}")
    except Exception as e:
        logger.error(f"Background transparent image pre-generation failed for Product {product_id}: {e}")
        db.rollback()
    finally:
        db.close()

@router.get("/pending-products", response_model=List[dict])
def get_pending_products(db: Session = Depends(get_db)):
    """
    HQ Admin: Get list of products scraped by crawler but not yet approved.
    (Real Database Query)
    """
    products = db.query(HQProduct).filter(HQProduct.status == "PENDING").limit(50).all()
    
    result = []
    for p in products:
        image_url = None
        if p.images and len(p.images) > 0:
            image_url = p.images[0]
        else:
            image_url = p.ai_fitting_image_url

        result.append({
            "id": p.id,
            "originalName": p.cn_name,
            "name": p.kr_name,
            "price": p.base_price,
            "margin": "30%", # Dummy for now
            "imageUrl": image_url,
            "description": p.kr_description or "",
            "images": p.images or []
        })
    return result

@router.patch("/product/{product_id}/status")
def update_product_status(product_id: int, payload: ProductStatusUpdate, db: Session = Depends(get_db)):
    """
    HQ Admin: Updates the status of an HQProduct (e.g. APPROVED or REJECTED)
    """
    product = db.query(HQProduct).filter(HQProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    product.status = payload.status
    if payload.category_id is not None:
        product.category_id = payload.category_id
        
    db.commit()
    
    return {"status": "success", "new_status": product.status, "category_id": product.category_id}


# ==========================================
# Category Management
# ==========================================

@router.get("/categories", response_model=List[CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    """ HQ Admin: 모든 카테고리 조회 """
    return db.query(Category).all()

@router.post("/category", response_model=CategoryResponse)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    """ HQ Admin: 새 카테고리 생성 """
    existing = db.query(Category).filter(Category.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Slug already exists.")
        
    new_cat = Category(
        name=payload.name,
        slug=payload.slug,
        parent_id=payload.parent_id
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat

@router.delete("/category/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db)):
    """ HQ Admin: 카테고리 삭제 """
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
        
    db.delete(cat)
    db.commit()
    return {"status": "success", "message": "Category deleted"}


# ==========================================
# [윈윈 도킹] 카테고리별 소매 마진 설정
# ==========================================

class CategoryMarginUpdate(BaseModel):
    margin_type: str       # 'percent' | 'fixed'
    margin_value: float    # percent면 %, fixed면 원(￦)

@router.put("/category/{cat_id}/margin")
def update_category_margin(cat_id: int, payload: CategoryMarginUpdate, recompute: bool = False, include_children: bool = False, db: Session = Depends(get_db)):
    """카테고리별 소매 마진(%/고정) 저장. recompute=true면 이 카테고리 기존 상품의 소매가도 재계산.
    include_children=true면 하위 카테고리 마진율도 일괄 저장하고 소매가를 재계산."""
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    mt = (payload.margin_type or "percent").lower()
    if mt not in ("percent", "fixed"):
        mt = "percent"
    val = float(payload.margin_value or 0)
    cat.margin_type = mt
    cat.margin_value = val

    updated = 0
    from backend.routers.crawler import compute_retail_price
    
    # 1. 본인 카테고리 재계산
    if recompute:
        prods = db.query(HQProduct).filter(HQProduct.category_id == cat_id).all()
        for p in prods:
            if p.wholesale_price and p.wholesale_price > 0:
                p.base_price = compute_retail_price(p.wholesale_price, cat.margin_type, cat.margin_value)
                updated += 1

    # 2. 하위 카테고리 일괄 변경 및 재계산
    if include_children:
        children = db.query(Category).filter(Category.parent_id == cat_id).all()
        for child in children:
            child.margin_type = mt
            child.margin_value = val
            if recompute:
                child_prods = db.query(HQProduct).filter(HQProduct.category_id == child.id).all()
                for cp in child_prods:
                    if cp.wholesale_price and cp.wholesale_price > 0:
                        cp.base_price = compute_retail_price(cp.wholesale_price, child.margin_type, child.margin_value)
                        updated += 1
                        
    db.commit()
    return {
        "status": "success", "category_id": cat_id,
        "margin_type": cat.margin_type, "margin_value": cat.margin_value,
        "recomputed_products": updated,
    }


class BulkMarginUpdate(BaseModel):
    margin_value: float
    margin_type: Optional[str] = "percent"

@router.put("/categories/margin/bulk")
def bulk_update_categories_margin(payload: BulkMarginUpdate, recompute: bool = False, db: Session = Depends(get_db)):
    """전체 카테고리 마진 일괄 수정 (% 및 고정단위 지원)"""
    categories = db.query(Category).all()
    mt = (payload.margin_type or "percent").lower()
    if mt not in ("percent", "fixed"):
        mt = "percent"
    val = float(payload.margin_value or 0)
    
    updated_cats = 0
    updated_prods = 0
    from backend.routers.crawler import compute_retail_price
    
    for cat in categories:
        cat.margin_type = mt
        cat.margin_value = val
        updated_cats += 1
        
        if recompute:
            prods = db.query(HQProduct).filter(HQProduct.category_id == cat.id).all()
            for p in prods:
                if p.wholesale_price and p.wholesale_price > 0:
                    p.base_price = compute_retail_price(p.wholesale_price, cat.margin_type, cat.margin_value)
                    updated_prods += 1
                    
    db.commit()
    return {
        "status": "success",
        "updated_categories": updated_cats,
        "recomputed_products": updated_prods,
        "margin_type": mt,
        "margin_value": val
    }


# ==========================================
# Brand Management (브랜드 관리)
# ==========================================

class BrandCreate(BaseModel):
    name: str
    eng_name: str
    slug: str
    logo_url: Optional[str] = None
    is_premium: bool = False
    is_active: bool = True

class BrandUpdate(BaseModel):
    name: Optional[str] = None
    eng_name: Optional[str] = None
    slug: Optional[str] = None
    logo_url: Optional[str] = None
    is_premium: Optional[bool] = None
    is_active: Optional[bool] = None

@router.get("/brands", response_model=List[dict])
def get_admin_brands(db: Session = Depends(get_db)):
    """ HQ Admin: 모든 브랜드 목록 조회 """
    brands = db.query(Brand).order_by(Brand.name.asc()).all()
    result = []
    for b in brands:
        result.append({
            "id": b.id,
            "name": b.name,
            "eng_name": b.eng_name,
            "slug": b.slug,
            "logo_url": b.logo_url,
            "is_premium": b.is_premium,
            "is_active": b.is_active
        })
    return result

@router.post("/brand", response_model=dict)
def create_brand(payload: BrandCreate, db: Session = Depends(get_db)):
    """ HQ Admin: 새 브랜드 생성 """
    existing = db.query(Brand).filter(Brand.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 존재하는 슬러그(slug)입니다.")
        
    new_brand = Brand(
        name=payload.name,
        eng_name=payload.eng_name,
        slug=payload.slug,
        logo_url=payload.logo_url,
        is_premium=payload.is_premium,
        is_active=payload.is_active
    )
    db.add(new_brand)
    db.commit()
    db.refresh(new_brand)
    return {"status": "success", "id": new_brand.id, "message": f"브랜드 '{new_brand.name}'가 생성되었습니다."}

@router.put("/brand/{brand_id}", response_model=dict)
def update_brand(brand_id: int, payload: BrandUpdate, db: Session = Depends(get_db)):
    """ HQ Admin: 브랜드 정보 수정 """
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="브랜드를 찾을 수 없습니다.")
        
    update_data = payload.model_dump(exclude_unset=True)
    if "slug" in update_data and update_data["slug"] != brand.slug:
        existing = db.query(Brand).filter(Brand.slug == update_data["slug"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="이미 사용 중인 슬러그(slug)입니다.")
            
    for field, value in update_data.items():
        if value is not None:
            setattr(brand, field, value)
            
    db.commit()
    return {"status": "success", "id": brand.id, "message": f"브랜드 '{brand.name}' 정보가 수정되었습니다."}

@router.delete("/brand/{brand_id}")
def delete_brand(brand_id: int, db: Session = Depends(get_db)):
    """ HQ Admin: 브랜드 삭제 """
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="브랜드를 찾을 수 없습니다.")
        
    db.query(HQProduct).filter(HQProduct.brand_id == brand_id).update({HQProduct.brand_id: None})
    
    brand_name = brand.name
    db.delete(brand)
    db.commit()
    return {"status": "success", "message": f"브랜드 '{brand_name}'가 삭제되었습니다."}


# ==========================================
# Product Management (상품 관리 CRUD)
# ==========================================

class ProductCreate(BaseModel):
    kr_name: str
    base_price: int
    category_id: int
    brand_id: Optional[int] = None
    cn_name: Optional[str] = None
    kr_description: Optional[str] = None
    description_html: Optional[str] = None
    sale_price: Optional[int] = None
    discount_rate: Optional[int] = None
    stock_quantity: int = 0
    sku: Optional[str] = None
    keywords: Optional[List[str]] = None
    images: Optional[List[str]] = None
    ai_fitting_image_url: Optional[str] = None
    transparent_item_image_url: Optional[str] = None
    video_url: Optional[str] = None
    size_stock_config: Optional[Any] = None

class ProductUpdate(BaseModel):
    kr_name: Optional[str] = None
    base_price: Optional[int] = None
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    cn_name: Optional[str] = None
    kr_description: Optional[str] = None
    description_html: Optional[str] = None
    sale_price: Optional[int] = None
    discount_rate: Optional[int] = None
    stock_quantity: Optional[int] = None
    sku: Optional[str] = None
    keywords: Optional[List[str]] = None
    images: Optional[List[str]] = None
    ai_fitting_image_url: Optional[str] = None
    transparent_item_image_url: Optional[str] = None
    video_url: Optional[str] = None
    size_stock_config: Optional[Any] = None
    status: Optional[str] = None

class ProductResponse(BaseModel):
    id: int
    kr_name: str
    cn_name: Optional[str]
    base_price: int
    sale_price: Optional[int] = None
    discount_rate: Optional[int] = None
    stock_quantity: int
    sku: Optional[str] = None
    keywords: Optional[List[str]] = None
    images: Optional[List[str]] = None
    category_id: int
    category_name: Optional[str] = None
    status: str
    ai_fitting_image_url: Optional[str]
    transparent_item_image_url: Optional[str]
    video_url: Optional[str] = None
    kr_description: Optional[str]
    description_html: Optional[str] = None
    size_stock_config: Optional[Any] = None
    created_at: Optional[str] = None

@router.get("/products", response_model=List[dict])
def get_admin_products(
    category_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    HQ Admin: 전체 상품 목록 조회 (카테고리/상태/검색 필터)
    """
    query = db.query(HQProduct)
    
    if category_id:
        query = query.filter(HQProduct.category_id == category_id)
    if status:
        query = query.filter(HQProduct.status == status)
    if search:
        query = query.filter(HQProduct.kr_name.contains(search))
    
    products = query.order_by(HQProduct.id.desc()).limit(200).all()
    
    result = []
    for p in products:
        cat_name = ""
        if p.category:
            cat_name = p.category.name
        result.append({
            "id": p.id,
            "kr_name": p.kr_name,
            "cn_name": p.cn_name,
            "base_price": p.base_price,
            "sale_price": p.sale_price,
            "discount_rate": p.discount_rate,
            "stock_quantity": p.stock_quantity,
            "sku": p.sku,
            "category_id": p.category_id,
            "category_name": cat_name,
            "brand_id": p.brand_id,
            "brand_name": p.brand.name if p.brand else "미지정",
            "status": p.status,
            "ai_fitting_image_url": p.ai_fitting_image_url,
            "transparent_item_image_url": p.transparent_item_image_url,
            "video_url": p.video_url,
            "kr_description": p.kr_description,
            "description_html": p.description_html,
            "keywords": p.keywords,
            "images": p.images,
            "size_stock_config": p.size_stock_config,
            "created_at": str(p.created_at) if p.created_at else None,
        })
    return result

@router.post("/product", response_model=dict)
def create_product(payload: ProductCreate, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    HQ Admin: 상품 수동 등록 (크롤러 거치지 않고 직접 등록)
    """
    # 카테고리 존재 확인
    cat = db.query(Category).filter(Category.id == payload.category_id).first()
    if not cat:
        raise HTTPException(status_code=400, detail="Invalid category_id")
    
    new_product = HQProduct(
        kr_name=payload.kr_name,
        cn_name=payload.cn_name,
        base_price=payload.base_price,
        sale_price=payload.sale_price,
        discount_rate=payload.discount_rate,
        stock_quantity=payload.stock_quantity,
        sku=payload.sku,
        keywords=payload.keywords,
        images=payload.images,
        category_id=payload.category_id,
        brand_id=payload.brand_id,
        kr_description=payload.kr_description,
        description_html=payload.description_html,
        ai_fitting_image_url=payload.ai_fitting_image_url,
        transparent_item_image_url=payload.transparent_item_image_url,
        video_url=payload.video_url,
        size_stock_config=payload.size_stock_config,
        status="APPROVED",  # 수동 등록은 바로 승인 상태
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    
    # [고도화] 백그라운드 AI 누끼 선 가공 예약 등록 (수동 1컷 가공 후작업 전환에 따른 자동 가공 비활성화)
    # bg_tasks.add_task(pre_generate_transparent_clothing_task, new_product.id)
    
    return {
        "status": "success",
        "id": new_product.id,
        "message": f"상품 '{new_product.kr_name}' 등록 완료"
    }

@router.put("/product/{product_id}", response_model=dict)
def update_product(product_id: int, payload: ProductUpdate, bg_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    HQ Admin: 상품 정보 편집
    """
    product = db.query(HQProduct).filter(HQProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # None이 아닌 필드만 업데이트
    update_data = payload.model_dump(exclude_unset=True)
    images_changed = "images" in update_data
    for field, value in update_data.items():
        if value is not None:
            setattr(product, field, value)
    
    db.commit()
    db.refresh(product)
    
    # [고도화] 이미지가 변경되었거나 누끼가 없는 경우 백그라운드 AI 누끼 가공 재수행 (수동 1컷 가공 후작업 전환에 따른 자동 가공 비활성화)
    # if images_changed or not product.transparent_item_image_url:
    #     bg_tasks.add_task(pre_generate_transparent_clothing_task, product.id)
        
    return {
        "status": "success",
        "id": product.id,
        "message": f"상품 '{product.kr_name}' 수정 완료"
    }

@router.delete("/product/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """
    HQ Admin: 상품 삭제
    """
    product = db.query(HQProduct).filter(HQProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product_name = product.kr_name

    # 상품에 연결된 업로드 이미지 파일 정리 (고아 파일 누적 방지)
    # /uploads/ 내부 파일만, 경로 이탈(traversal) 방지 가드 포함
    removed_files = 0
    try:
        import os
        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
        uploads_real = os.path.realpath(uploads_dir)
        for u in (product.images or []):
            if not isinstance(u, str) or "/uploads/" not in u:
                continue  # 외부(원격) URL 이나 placeholder 는 건너뜀
            rel = u.split("/uploads/", 1)[1].split("?")[0]
            fp = os.path.realpath(os.path.join(uploads_dir, rel))
            if fp.startswith(uploads_real + os.sep) and os.path.isfile(fp):
                os.remove(fp)
                removed_files += 1
    except Exception as e:
        logger.warning(f"[delete_product] 이미지 파일 정리 실패(무시): {e}")

    db.delete(product)
    db.commit()

    return {"status": "success", "message": f"상품 '{product_name}' 삭제 완료 (이미지 {removed_files}개 정리)"}

class ExtractTransparentRequest(BaseModel):
    image_url: str
    model_name: Optional[str] = "u2net"
    category_id: Optional[int] = None

@router.post("/ai/extract-transparent")
async def extract_image_transparent_generic(payload: ExtractTransparentRequest, db: Session = Depends(get_db)):
    """
    HQ Admin: 특정 이미지 1컷에 대해 수동으로 AI 누끼(배경 제거) 및 마네킹 피팅(VTON) 가공을 수행합니다 (상품 ID 무관).
    """
    orig_url = payload.image_url.strip()
    if not orig_url:
        raise HTTPException(status_code=400, detail="이미지 주소가 올바르지 않습니다.")
        
    # 로컬 정적 서비스 경로 대응
    if not orig_url.startswith("http") and not orig_url.startswith("/"):
        orig_url = f"{settings.BACKEND_URL}/{orig_url}"
    elif orig_url.startswith("/"):
        orig_url = f"{settings.BACKEND_URL}{orig_url}"
        
    from backend.ai_engine.vton import AIFittingPreGenerator
    try:
        generator = AIFittingPreGenerator()
        transparent_url = await generator.extract_transparent_clothing(orig_url, model_name=payload.model_name or "u2net")
        if transparent_url:
            ai_fitting_image_url = None
            if payload.category_id:
                try:
                    cat = db.query(Category).filter(Category.id == payload.category_id).first()
                    if cat:
                        cat_name = cat.name.lower()
                        is_top = True
                        gender = "female"
                        
                        # 성별 판별
                        if any(x in cat_name for x in ["여성", "women", "female", "여자", "womens"]):
                            gender = "female"
                        elif any(x in cat_name for x in ["남성", "men", "male", "남자", "mens"]):
                            gender = "male"
                            
                        # 상의/하의 판별
                        if any(x in cat_name for x in ["바지", "스커트", "하의", "bottom", "pants", "skirt", "jeans"]):
                            is_top = False
                            
                        # render_mannequin_fit_generic 호출
                        ai_fitting_image_url = await generator.render_mannequin_fit_generic(
                            transparent_image_url=transparent_url,
                            gender=gender,
                            is_top=is_top
                        )
                except Exception as e_fit:
                    logger.error(f"Generic temporary mannequin fit failed: {e_fit}")

            return {
                "status": "success",
                "message": "AI 누끼 및 가상 피팅 가공이 완료되었습니다.",
                "transparent_item_image_url": transparent_url,
                "ai_fitting_image_url": ai_fitting_image_url
            }
        else:
            raise HTTPException(status_code=500, detail="AI 누끼 이미지 생성 결과가 없습니다.")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"배경 제거 중 AI 엔진 내부 오류 발생: {str(e)}")

@router.post("/product/{product_id}/extract-transparent")
async def extract_product_image_transparent(product_id: int, payload: ExtractTransparentRequest, db: Session = Depends(get_db)):
    """
    HQ Admin: 특정 상품의 지정된 이미지 1컷에 대해 수동으로 AI 누끼(배경 제거) 가공을 수행합니다.
    """
    product = db.query(HQProduct).filter(HQProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
        
    orig_url = payload.image_url.strip()
    if not orig_url:
        raise HTTPException(status_code=400, detail="이미지 주소가 올바르지 않습니다.")
        
    # 로컬 정적 서비스 경로 대응
    if not orig_url.startswith("http") and not orig_url.startswith("/"):
        orig_url = f"{settings.BACKEND_URL}/{orig_url}"
    elif orig_url.startswith("/"):
        orig_url = f"{settings.BACKEND_URL}{orig_url}"
        
    from backend.ai_engine.vton import AIFittingPreGenerator
    try:
        # 카테고리 매핑 파악하여 누끼 가공에 주입 (옷걸이 지능형 제거 지원)
        category_type = "Top" # 기본값
        if product.category:
            cat_name = product.category.name.lower()
            if any(x in cat_name for x in ["bottom", "하의", "pants", "denim", "jeans"]):
                category_type = "Bottom"
            elif any(x in cat_name for x in ["shoes", "신발"]):
                category_type = "Shoes"
                
        generator = AIFittingPreGenerator()
        transparent_url = await generator.extract_transparent_clothing(orig_url, model_name=payload.model_name or "u2net", category_type=category_type)
        if transparent_url:
            product.transparent_item_image_url = transparent_url
            db.commit()
            # [고도화 추가] 마네킹 착장 및 마스크 사전 렌더링 기동
            try:
                await generator.pre_render_mannequin_fit(db, product.id)
            except Exception as e_pr:
                logger.error(f"Manual pre-render mannequin fit failed for Product {product_id}: {e_pr}")
            return {
                "status": "success",
                "message": "AI 누끼 및 마네킹 착장 가공이 완료되었습니다.",
                "transparent_item_image_url": transparent_url,
                "ai_fitting_image_url": product.ai_fitting_image_url
            }
        else:
            raise HTTPException(status_code=500, detail="AI 누끼 이미지 생성 결과가 없습니다.")
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"배경 제거 중 AI 엔진 내부 오류 발생: {str(e)}")

# ==========================================
# User Management (회원 관리)
# ==========================================

class UserRoleUpdate(BaseModel):
    role: str # "USER" | "ADMIN"

class UserGradeUpdate(BaseModel):
    grade: int # 0: ADMIN, 1: VVIP, 2: VIP, 3: 우수, 4: 일반, 5: 미가입

@router.get("/users")
def get_all_users(db: Session = Depends(get_db)):
    """ HQ Admin: 모든 유저 목록 조회 """
    users = db.query(User).order_by(User.id.desc()).all()
    result = []
    for u in users:
        result.append({
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "phone": u.phone,
            "role": u.role,
            "grade": u.grade if u.grade is not None else 4,
            "reward_points": u.reward_points if u.reward_points is not None else 0,
            "is_active": u.is_active,
            "created_at": str(u.created_at) if u.created_at else None
        })
    return result

@router.patch("/users/{user_id}/role")
def update_user_role(user_id: int, payload: UserRoleUpdate, db: Session = Depends(get_db)):
    """ HQ Admin: 특정 유저의 관리자 권한 변경(토글) """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.role = payload.role
    db.commit()
    return {"status": "success", "user_id": user.id, "new_role": user.role}

@router.patch("/users/{user_id}/grade")
def update_user_grade(user_id: int, payload: UserGradeUpdate, db: Session = Depends(get_db)):
    """ HQ Admin: 특정 유저의 등급 변경 """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if payload.grade not in [0, 1, 2, 3, 4, 5]:
        raise HTTPException(status_code=400, detail="Invalid grade value")
        
    user.grade = payload.grade
    
    # 0등급(ADMIN)일 경우 role도 ADMIN으로, 그 외는 USER로 동기화
    if payload.grade == 0:
        user.role = "ADMIN"
    else:
        user.role = "USER"
        
    db.commit()
    return {
        "status": "success", 
        "user_id": user.id, 
        "new_grade": user.grade,
        "new_role": user.role
    }

from backend.models import Coupon
import uuid

class UserRewardPointsUpdate(BaseModel):
    reward_points: int

class CouponIssuePayload(BaseModel):
    name: str
    discount_amount: int

@router.patch("/users/{user_id}/reward-points")
def update_user_reward_points(user_id: int, payload: UserRewardPointsUpdate, db: Session = Depends(get_db)):
    """ HQ Admin: 특정 유저의 보유 적립금 강제 수정 """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if payload.reward_points < 0:
        raise HTTPException(status_code=400, detail="Reward points cannot be negative")
        
    user.reward_points = payload.reward_points
    db.commit()
    return {"status": "success", "user_id": user.id, "new_reward_points": user.reward_points}

@router.post("/users/{user_id}/coupons")
def issue_user_coupon(user_id: int, payload: CouponIssuePayload, db: Session = Depends(get_db)):
    """ HQ Admin: 특정 유저에게 설정된 금액의 할인쿠폰 수동 발급 """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if payload.discount_amount <= 0:
        raise HTTPException(status_code=400, detail="Discount amount must be positive")
        
    coupon_code = f"CPN-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}"
    
    new_coupon = Coupon(
        user_id=user.id,
        code=coupon_code,
        name=payload.name,
        discount_amount=payload.discount_amount,
        is_used=False
    )
    db.add(new_coupon)
    db.commit()
    db.refresh(new_coupon)
    return {
        "status": "success", 
        "coupon_id": new_coupon.id, 
        "code": new_coupon.code,
        "name": new_coupon.name,
        "discount_amount": new_coupon.discount_amount
    }

# ==========================================
# Dashboard Enhanced Stats (고도화 통계)
# ==========================================

from sqlalchemy import func

@router.get("/stats/product-distribution")
def get_product_distribution(db: Session = Depends(get_db)):
    """ 상품 상태별 분포 (PENDING / APPROVED / REJECTED) """
    rows = db.query(HQProduct.status, func.count(HQProduct.id)).group_by(HQProduct.status).all()
    result = {}
    for status, count in rows:
        result[status] = count
    return result

@router.get("/stats/category-product-counts")
def get_category_product_counts(db: Session = Depends(get_db)):
    """ 카테고리별 상품 수 집계 """
    rows = (
        db.query(Category.id, Category.name, Category.slug, Category.parent_id, func.count(HQProduct.id))
        .outerjoin(HQProduct, HQProduct.category_id == Category.id)
        .group_by(Category.id)
        .all()
    )
    return [
        {"id": cid, "name": name, "slug": slug, "parent_id": pid, "product_count": cnt}
        for cid, name, slug, pid, cnt in rows
    ]

@router.get("/stats/recent-users")
def get_recent_users(db: Session = Depends(get_db)):
    """ 최근 가입 회원 5명 """
    users = db.query(User).order_by(User.id.desc()).limit(5).all()
    return [
        {"id": u.id, "email": u.email, "name": u.name, "role": u.role, "created_at": str(u.created_at) if u.created_at else None}
        for u in users
    ]


# ==========================================
# Tenant Management (테넌트 설정 및 관리)
# ==========================================

class TenantCreate(BaseModel):
    domain: str # e.g. "hq.mall.com"
    name: str # e.g. "HQ Premium Shop"
    theme_config: Optional[dict] = None
    is_active: bool = True

class TenantUpdate(BaseModel):
    domain: Optional[str] = None
    name: Optional[str] = None
    theme_config: Optional[dict] = None
    is_active: Optional[bool] = None

@router.get("/tenants")
def get_tenants(db: Session = Depends(get_db)):
    """ HQ Admin: 모든 테넌트(서브몰) 목록 조회 """
    tenants = db.query(Tenant).order_by(Tenant.id.desc()).all()
    result = []
    for t in tenants:
        result.append({
            "id": t.id,
            "domain": t.domain,
            "name": t.name,
            "theme_config": t.theme_config or {},
            "is_active": t.is_active
        })
    return result

@router.post("/tenants")
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    """ HQ Admin: 새로운 테넌트 생성 """
    existing = db.query(Tenant).filter(Tenant.domain == payload.domain).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 사용 중인 도메인입니다.")
        
    new_tenant = Tenant(
        domain=payload.domain,
        name=payload.name,
        theme_config=payload.theme_config,
        is_active=payload.is_active
    )
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    return {
        "status": "success",
        "message": f"테넌트 '{new_tenant.name}'가 생성되었습니다.",
        "tenant": {
            "id": new_tenant.id,
            "name": new_tenant.name,
            "domain": new_tenant.domain
        }
    }

@router.put("/tenants/{tenant_id}")
def update_tenant(tenant_id: int, payload: TenantUpdate, db: Session = Depends(get_db)):
    """ HQ Admin: 테넌트 정보 수정 """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="테넌트를 찾을 수 없습니다.")
        
    update_data = payload.model_dump(exclude_unset=True)
    
    # 도메인 변경 시 중복 검사
    if "domain" in update_data and update_data["domain"] != tenant.domain:
        existing = db.query(Tenant).filter(Tenant.domain == update_data["domain"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="이미 사용 중인 도메인입니다.")
            
    for field, value in update_data.items():
        if value is not None:
            setattr(tenant, field, value)
            
    db.commit()
    db.refresh(tenant)
    return {
        "status": "success",
        "message": f"테넌트 '{tenant.name}' 정보가 수정되었습니다.",
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "domain": tenant.domain,
            "theme_config": tenant.theme_config,
            "is_active": tenant.is_active
        }
    }

@router.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: int, db: Session = Depends(get_db)):
    """ HQ Admin: 테넌트 삭제 """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="테넌트를 찾을 수 없습니다.")
        
    tenant_name = tenant.name
    db.delete(tenant)
    db.commit()
    return {
        "status": "success",
        "message": f"테넌트 '{tenant_name}'가 성공적으로 삭제되었습니다."
    }


from sqlalchemy import distinct
from backend.models import Order, OrderItem, TenantProduct

@router.get("/tenants/{tenant_id}/stats")
def get_tenant_stats(tenant_id: int, db: Session = Depends(get_db)):
    """ HQ Admin: 특정 테넌트의 매출 및 주문 통계 정보 조회 (실시간 DB 쿼리 + 데모용 폴백) """
    try:
        # 1. 실시간 DB 매출액 집계
        real_sales = db.query(func.sum(Order.total_amount))\
            .join(OrderItem, OrderItem.order_id == Order.id)\
            .join(TenantProduct, TenantProduct.product_id == OrderItem.product_id)\
            .filter(TenantProduct.tenant_id == tenant_id)\
            .scalar() or 0
            
        # 2. 실시간 주문 건수 집계 (중복 제거)
        real_orders = db.query(func.count(distinct(Order.id)))\
            .join(OrderItem, OrderItem.order_id == Order.id)\
            .join(TenantProduct, TenantProduct.product_id == OrderItem.product_id)\
            .filter(TenantProduct.tenant_id == tenant_id)\
            .scalar() or 0

        # 3. 배송 상태별 건수
        pending_count = db.query(func.count(distinct(Order.id)))\
            .join(OrderItem, OrderItem.order_id == Order.id)\
            .join(TenantProduct, TenantProduct.product_id == OrderItem.product_id)\
            .filter(TenantProduct.tenant_id == tenant_id, Order.shipping_status == "PREPARING")\
            .scalar() or 0

        shipping_count = db.query(func.count(distinct(Order.id)))\
            .join(OrderItem, OrderItem.order_id == Order.id)\
            .join(TenantProduct, TenantProduct.product_id == OrderItem.product_id)\
            .filter(TenantProduct.tenant_id == tenant_id, Order.shipping_status == "SHIPPING")\
            .scalar() or 0

        delivered_count = db.query(func.count(distinct(Order.id)))\
            .join(OrderItem, OrderItem.order_id == Order.id)\
            .join(TenantProduct, TenantProduct.product_id == OrderItem.product_id)\
            .filter(TenantProduct.tenant_id == tenant_id, Order.shipping_status == "DELIVERED")\
            .scalar() or 0

        # H1: 매출 0 시 랜덤 가짜데이터를 반환하던 로직 제거 → 항상 실제 집계값 사용

        # 실시간 데이터가 존재하는 경우
        months = ["12월", "1월", "2월", "3월", "4월", "5월"]
        monthly_sales = []
        base_sale = real_sales // len(months)
        for m in months:
            monthly_sales.append({"month": m, "amount": base_sale})
            
        return {
            "total_sales": real_sales,
            "total_orders": real_orders,
            "shipping_stats": {
                "preparing": pending_count,
                "shipping": shipping_count,
                "delivered": delivered_count
            },
            "monthly_sales": monthly_sales,
            "is_demo": False
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 집계 실패: {str(e)}")


# ==========================================
# Support Ticket Management (1:1 문의 관리)
# ==========================================

from datetime import datetime

class TicketAnswerPayload(BaseModel):
    answer: str

@router.get("/support/tickets")
def get_all_tickets(db: Session = Depends(get_db)):
    """ HQ Admin: 모든 유저의 1:1 문의 전체 내역 조회 """
    tickets = db.query(SupportTicket).order_by(SupportTicket.id.desc()).all()
    result = []
    for t in tickets:
        result.append({
            "id": t.id,
            "user_id": t.user_id,
            "user_email": t.user.email if t.user else "알 수 없는 사용자",
            "user_name": t.user.name if t.user else "알 수 없는 사용자",
            "subject": t.subject,
            "content": t.content,
            "status": t.status,
            "answer": t.answer,
            "answered_at": str(t.answered_at) if t.answered_at else None,
            "created_at": str(t.created_at) if t.created_at else None
        })
    return result

@router.post("/support/tickets/{ticket_id}/answer")
def answer_ticket(ticket_id: int, payload: TicketAnswerPayload, db: Session = Depends(get_db)):
    """ HQ Admin: 특정 1:1 문의에 대한 답변 작성 및 수정 """
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="문의글을 찾을 수 없습니다.")
        
    ticket.answer = payload.answer
    ticket.status = "ANSWERED"
    ticket.answered_at = datetime.utcnow()
    db.commit()
    return {
        "status": "success",
        "message": "답변이 성공적으로 등록되었습니다.",
        "ticket_status": ticket.status
    }

@router.delete("/support/tickets/{ticket_id}")
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """ HQ Admin: 특정 1:1 문의 삭제 """
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="문의글을 찾을 수 없습니다.")
        
    db.delete(ticket)
    db.commit()
    return {
        "status": "success",
        "message": "문의글이 성공적으로 삭제되었습니다."
    }

# ==========================================
# AI Banner Generation (AI 메인 배너 생성)
# ==========================================

import urllib.request
import urllib.error
import json
from backend.config import settings

class AIBannerRequest(BaseModel):
    prompt: str

@router.post("/banner/ai-generate")
def generate_ai_banner(payload: AIBannerRequest):
    """ HQ Admin: Gemini 2.5 Flash API를 활용한 메인 배너 카피라이팅 및 테마 컬러 생성 """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=400, 
            detail="Gemini API Key가 백엔드 환경변수(.env)에 셋팅되어 있지 않습니다. 설정 후 다시 시도해 주세요."
        )

    # Gemini REST API 호출 준비
    
    # 구조화된 JSON 출력을 위한 System Instruction 및 Prompt 작성
    system_instruction = (
        "You are an expert e-commerce copywriter and UI designer. "
        "Based on the user's prompt, generate a matching main banner configuration in JSON format. "
        "The output MUST be a valid JSON object matching this schema exactly: "
        "{\n"
        "  \"bannerTitle\": \"Creative banner title in Korean (max 40 chars)\",\n"
        "  \"bannerSubtitle\": \"Sentimental banner subtitle in Korean (max 100 chars)\",\n"
        "  \"primaryColor\": \"Primary hex color code (e.g., #2563eb) matching the theme style\",\n"
        "  \"secondaryColor\": \"Secondary hex color code (e.g., #4f46e5) matching the theme style\",\n"
        "  \"fontFamily\": \"Outfit, Inter, Roboto, or Noto Sans KR (choose one that fits best)\",\n"
        "  \"layoutStyle\": \"modern, gallery, or card (choose one that fits best)\"\n"
        "}\n"
        "Return ONLY the raw JSON object. Do not include markdown code block syntax (like ```json ... ```)."
    )
    
    try:
        text_response = generate_text(system_instruction, payload.prompt, timeout=15)
        parsed_json = json.loads(text_response)
        # 누락 키 채움 (무결성)
        for _k in ["bannerTitle", "bannerSubtitle", "primaryColor", "secondaryColor", "fontFamily", "layoutStyle"]:
            parsed_json.setdefault(_k, "")
        return parsed_json
    except GeminiError as e:
        raise HTTPException(status_code=502, detail=f"Gemini API 호출 에러: {e}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Gemini 응답을 JSON 으로 파싱하지 못했습니다.")


class ProductInlineUpdate(BaseModel):
    kr_name: Optional[str] = None
    base_price: Optional[int] = None
    sale_price: Optional[int] = None

@router.put("/products/{product_id}/inline-update")
def inline_update_product(product_id: int, payload: ProductInlineUpdate, db: Session = Depends(get_db)):
    """ HQ Admin: 쇼핑몰 현장 실시간 1-클릭 인라인 상품정보 변경 """
    product = db.query(HQProduct).filter(HQProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(product, field, value)
            
    db.commit()
    db.refresh(product)
    
    return {
        "status": "success",
        "message": f"상품 '{product.kr_name}'의 정보가 실시간 수정되었습니다.",
        "product": {
            "id": product.id,
            "kr_name": product.kr_name,
            "base_price": product.base_price,
            "sale_price": product.sale_price
        }
    }


class ProductAIAutofillRequest(BaseModel):
    kr_name: Optional[str] = None
    cn_name: Optional[str] = None
    category_id: Optional[int] = None
    hint: Optional[str] = None

@router.post("/ai/product-autofill")
def ai_autofill_product(payload: ProductAIAutofillRequest, db: Session = Depends(get_db)):
    """ HQ Admin: Gemini 2.5 Flash API를 활용하여 상품정보 자동 완성 파이프라인 """
    import json
    import urllib.request
    import urllib.error
    
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=400, 
            detail="Gemini API Key가 백엔드 환경변수(.env)에 셋팅되어 있지 않습니다. 설정 후 다시 시도해 주세요."
        )

    # 1. 사용 가능한 카테고리 목록 로드
    categories = db.query(Category).all()
    cat_list_str = "\n".join([f"- ID: {c.id}, Name: {c.name}, Slug: {c.slug}" for c in categories])

    # 2. Gemini REST API 호출 준비
    
    # 구조화된 JSON 출력을 위한 System Instruction 및 Prompt 작성
    system_instruction = (
        "You are an expert e-commerce copywriter. "
        "Based on the provided product information (kr_name, cn_name, hint) and category list, "
        "generate optimized e-commerce product information. "
        "Make sure to return a valid JSON object matching this schema exactly:\n"
        "{\n"
        "  \"kr_name\": \"A sophisticated, clean, and catchy product name in Korean (max 30 chars). If the input kr_name is already good, keep it or polish it slightly. If it is long Chinese/English crawler raw name, translate and optimize it.\",\n"
        "  \"kr_description\": \"A beautiful, detailed, and persuasive marketing description in Korean (at least 3-4 sentences, about 100-200 Korean characters) highlighting quality, design, and styling tips. Avoid generic placeholders.\",\n"
        "  \"category_id\": \"Recommend the best category ID from the provided list as an integer. If no category matches, recommend the most general one.\",\n"
        "  \"recommended_price\": \"An integer value representing the suggested selling price in KRW (South Korean Won). If base_price hint is available, apply domestic margin and exchange rate. Otherwise, recommend a standard premium price for this item.\"\n"
        "}\n"
        "Return ONLY the raw JSON object. Do not include markdown code block syntax (like ```json ... ```)."
    )

    prompt = (
        f"Available Category List:\n{cat_list_str}\n\n"
        f"Input Product Information:\n"
        f"- Current Korean Name: {payload.kr_name or 'N/A'}\n"
        f"- Current Chinese/English Original Name: {payload.cn_name or 'N/A'}\n"
        f"- Chosen Category ID: {payload.category_id or 'N/A'}\n"
        f"- Extra Hint/Detail: {payload.hint or 'N/A'}"
    )
    
    try:
        text_response = generate_text(system_instruction, prompt, timeout=20)
        parsed_json = json.loads(text_response)

        # 무결성 및 타입 체크
        if "kr_name" not in parsed_json:
            parsed_json["kr_name"] = payload.kr_name or ""
        if "kr_description" not in parsed_json:
            parsed_json["kr_description"] = ""
        if "category_id" not in parsed_json:
            parsed_json["category_id"] = payload.category_id or (categories[0].id if categories else 1)
        else:
            try:
                parsed_json["category_id"] = int(parsed_json["category_id"])
            except (ValueError, TypeError):
                parsed_json["category_id"] = payload.category_id or 1
        if "recommended_price" not in parsed_json:
            parsed_json["recommended_price"] = 39000
        else:
            try:
                parsed_json["recommended_price"] = int(parsed_json["recommended_price"])
            except (ValueError, TypeError):
                parsed_json["recommended_price"] = 39000

        return parsed_json
    except GeminiError as e:
        raise HTTPException(status_code=502, detail=f"Gemini API 호출 에러: {e}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Gemini 응답을 JSON 으로 파싱하지 못했습니다.")


# ==========================================
# AI Translation Engine Integration (AI 번역 엔드포인트)
# ==========================================

# 일괄 번역 상태 관리용 글로벌 변수
bulk_translate_state = {
    "is_running": False,
    "total": 0,
    "current": 0,
    "success": 0,
    "failed": 0,
    "should_stop": False
}

class BulkTranslateRequest(BaseModel):
    product_ids: List[int]

async def run_bulk_translate_task(product_ids: List[int]):
    global bulk_translate_state
    
    from backend.database import SessionLocal
    db = SessionLocal()
    translator = AITranslatorPipeline()
    
    try:
        for pid in product_ids:
            if bulk_translate_state["should_stop"]:
                logger.info("Bulk translation stopped by user request.")
                break
                
            product = db.query(HQProduct).filter(HQProduct.id == pid).first()
            if not product:
                bulk_translate_state["current"] += 1
                bulk_translate_state["failed"] += 1
                continue
                
            try:
                # 중국어 원문(cn_name, kr_description)을 기준으로 번역
                cn_title = product.cn_name or product.kr_name or ""
                cn_desc = product.kr_description or ""
                
                cat_name = "의류"
                if product.category:
                    cat_name = product.category.name
                
                translated = await translator.translate_product_info(
                    cn_title=cn_title,
                    cn_desc=cn_desc,
                    wholesale_price_krw=product.wholesale_price or 0,
                    category_name=cat_name,
                    original_source_url=product.original_source_url or ""
                )
                
                product.kr_name = translated.get("kr_name") or product.kr_name
                product.kr_description = translated.get("kr_description") or product.kr_description
                product.description_html = translated.get("description_html") or product.description_html
                
                if translated.get("product_code"):
                    product.sku = translated.get("product_code")
                if translated.get("sale_price"):
                    product.wholesale_price = translated.get("sale_price")
                    if product.category:
                        from backend.routers.crawler import compute_retail_price
                        product.base_price = compute_retail_price(
                            product.wholesale_price,
                            product.category.margin_type,
                            product.category.margin_value
                        )
                
                db.commit()
                bulk_translate_state["success"] += 1
            except Exception as e:
                logger.error(f"Bulk translate error for product {pid}: {e}")
                db.rollback()
                bulk_translate_state["failed"] += 1
            finally:
                bulk_translate_state["current"] += 1
    finally:
        db.close()
        bulk_translate_state["is_running"] = False

@router.post("/product/{product_id}/translate")
async def translate_single_product(product_id: int, db: Session = Depends(get_db)):
    """
    개별 상품 AI 번역 API
    """
    product = db.query(HQProduct).filter(HQProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
        
    cn_title = product.cn_name or product.kr_name or ""
    cn_desc = product.kr_description or ""
    
    cat_name = "의류"
    if product.category:
        cat_name = product.category.name
    
    translator = AITranslatorPipeline()
    translated = await translator.translate_product_info(
        cn_title=cn_title,
        cn_desc=cn_desc,
        wholesale_price_krw=product.wholesale_price or 0,
        category_name=cat_name,
        original_source_url=product.original_source_url or ""
    )
    
    product.kr_name = translated.get("kr_name") or product.kr_name
    product.kr_description = translated.get("kr_description") or product.kr_description
    product.description_html = translated.get("description_html") or product.description_html
    
    if translated.get("product_code"):
        product.sku = translated.get("product_code")
    if translated.get("sale_price"):
        product.wholesale_price = translated.get("sale_price")
        if product.category:
            product.base_price = compute_retail_price(
                product.wholesale_price,
                product.category.margin_type,
                product.category.margin_value
            )
        
    db.commit()
    db.refresh(product)
    
    return {
        "status": "success",
        "id": product.id,
        "kr_name": product.kr_name,
        "kr_description": product.kr_description,
        "sku": product.sku,
        "wholesale_price": product.wholesale_price,
        "base_price": product.base_price
    }

@router.post("/products/bulk-translate")
def bulk_translate_products(payload: BulkTranslateRequest, bg_tasks: BackgroundTasks):
    """
    일괄 상품 AI 번역 API (백그라운드 태스크)
    """
    global bulk_translate_state
    
    if bulk_translate_state["is_running"]:
        raise HTTPException(status_code=400, detail="이미 다른 일괄 번역 작업이 진행 중입니다.")
        
    product_ids = payload.product_ids
    bulk_translate_state = {
        "is_running": True,
        "total": len(product_ids),
        "current": 0,
        "success": 0,
        "failed": 0,
        "should_stop": False
    }
    
    bg_tasks.add_task(run_bulk_translate_task, product_ids)
    return {"status": "success", "message": f"{len(product_ids)}개 상품 일괄 번역 시작"}

@router.get("/products/bulk-translate/status")
def get_bulk_translate_status():
    """
    일괄 번역 진행도 조회 API
    """
    global bulk_translate_state
    return bulk_translate_state

@router.post("/products/bulk-translate/stop")
def stop_bulk_translate():
    """
    일괄 번역 중단 API
    """
    global bulk_translate_state
    if not bulk_translate_state["is_running"]:
        return {"status": "ignored", "message": "진행 중인 일괄 번역 작업이 없습니다."}
        
    bulk_translate_state["should_stop"] = True
    return {"status": "success", "message": "일괄 번역 작업 중단 요청 완료"}

