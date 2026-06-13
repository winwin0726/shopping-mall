from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models import HQProduct, Category, Brand, User
from backend.utils.deps import get_current_user_optional

router = APIRouter()

# 상품 대표(피팅용 누끼) 이미지가 없을 때의 폴백 (D4: 매직 URL 상수화)
FALLBACK_PRODUCT_IMAGE = "https://cdn-icons-png.flaticon.com/512/863/863684.png"


def _display_image(p) -> str:
    """상품 목록/카드용 표시 이미지 단일 규칙 (D5: 갤러리 ➔ 피팅 ➔ 누끼 ➔ 폴백)."""
    return (
        (p.images[0] if p.images else None)
        or p.ai_fitting_image_url
        or p.transparent_item_image_url
        or FALLBACK_PRODUCT_IMAGE
    )


# Schema for response (Mocking Pydantic for brevity, full Pydantic should be in schemas.py)
# 슬래시 유무 모두 직접 응답 → 프록시 뒤에서 trailing-slash 리다이렉트(내부주소 노출) 방지
@router.get("/brands", response_model=List[dict])
def get_all_brands(
    category_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    활성화된 브랜드 목록 전체를 반환합니다.
    category_name 이 제공될 경우, 해당 품목군(또는 all) 브랜드만 필터링하여 반환합니다.
    """
    query = db.query(Brand).filter(Brand.is_active == True)
    
    if category_name:
        from backend.utils.brand_detector import get_category_group_key
        group_key = get_category_group_key(category_name)
        if group_key:
            query = query.filter(
                (Brand.category_group == 'all') | 
                (Brand.category_group.like(f"%{group_key}%"))
            )
            
    brands = query.order_by(Brand.eng_name.asc()).all()
    result = []
    for b in brands:
        result.append({
            "id": b.id,
            "name": b.name,
            "eng_name": b.eng_name,
            "slug": b.slug,
            "logo_url": b.logo_url,
            "is_premium": b.is_premium,
            "category_group": b.category_group
        })
    return result

@router.get("", response_model=List[dict])
@router.get("/", response_model=List[dict])
def get_products(
    brand_id: Optional[int] = Query(None),
    brand_slug: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Returns the list of HQ products with their transparent images for VTON.
    Using real DB data.
    """
    query = db.query(HQProduct).outerjoin(Category).outerjoin(Brand).filter(HQProduct.status == "APPROVED")
    
    if brand_id is not None:
        query = query.filter(HQProduct.brand_id == brand_id)
    if brand_slug is not None:
        query = query.filter(Brand.slug == brand_slug)
    if search:
        query = query.filter(HQProduct.kr_name.contains(search))
        
    products = query.all()
    
    is_masked = current_user is None or current_user.grade == 5
    
    result = []
    for p in products:
        cat_slug = p.category.slug if p.category else "top"
        layer = "top"
        if p.category:
            if "bottom" in cat_slug or "하의" in p.category.name:
                layer = "bottom"
            elif "acc" in cat_slug or "가방" in p.category.name:
                layer = "accessory"
            
        result.append({
            "id": p.id,
            "name": "🔒 가입 후 확인 가능" if is_masked else p.kr_name,
            "category": layer,
            "category_id": p.category_id,
            "category_name": p.category.name if p.category else "기타",
            "brand_id": p.brand_id,
            "brand_name": p.brand.name if p.brand else "미지정",
            "brand_eng_name": p.brand.eng_name if p.brand else "",
            "price": 0 if is_masked else p.base_price,
            "sale_price": 0 if is_masked else p.sale_price,
            "discount_rate": 0 if is_masked else p.discount_rate,
            "transparentImage": _display_image(p),
        })
    
    return result

@router.get("/category/{main_category}", response_model=List[dict])
def get_products_by_category(
    main_category: str, 
    sub_category: str = None, 
    brand_id: Optional[int] = Query(None),
    brand_slug: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Returns products filtered by main category (e.g., '남성의류') and optionally by subcategory.
    """
    query = db.query(HQProduct).outerjoin(Category).outerjoin(Brand).filter(HQProduct.status == "APPROVED")
    
    # 1. 대분류 카테고리(부모) 및 그 하위 중/소분류 카테고리 상품 필터링 (3단계 재귀 지원)
    if main_category and main_category != "전체" and main_category != "summer-sale":
        main_cat = db.query(Category).filter(Category.name == main_category, Category.parent_id == None).first()
        if main_cat:
            # 1단계 자식들 (중분류)
            sub_cats = db.query(Category).filter(Category.parent_id == main_cat.id).all()
            sub_cat_ids = [sc.id for sc in sub_cats]
            
            # 2단계 자식들 (소분류)
            sub_sub_cats = db.query(Category).filter(Category.parent_id.in_(sub_cat_ids)).all() if sub_cat_ids else []
            sub_sub_cat_ids = [ssc.id for ssc in sub_sub_cats]
            
            # 대분류 + 중분류 + 소분류 ID 목록 통합
            cat_ids = [main_cat.id] + sub_cat_ids + sub_sub_cat_ids
            query = query.filter(HQProduct.category_id.in_(cat_ids))
        else:
            query = query.filter(Category.name == main_category)
            
    # 2. 소/중분류 카테고리 추가 필터링 (sub_category 파라미터 처리)
    if sub_category and sub_category != "전체":
        main_cat = db.query(Category).filter(Category.name == main_category, Category.parent_id == None).first()
        if main_cat:
            # 해당 대분류 아래 of 모든 하위 중분류 및 소분류 수집하여 이름 매칭 (동명이명 중복 방지)
            sub_cats = db.query(Category).filter(Category.parent_id == main_cat.id).all()
            sub_cat_ids = [sc.id for sc in sub_cats]
            sub_sub_cats = db.query(Category).filter(Category.parent_id.in_(sub_cat_ids)).all() if sub_cat_ids else []
            
            target_cat = None
            for c in (sub_cats + sub_sub_cats):
                if c.slug == sub_category or c.name == sub_category:
                    target_cat = c
                    break
                    
            if target_cat:
                # 선택한 중/소분류 카테고리 자체와 만약 자식 소분류가 있다면 자식 ID까지 함께 포함
                child_cats = db.query(Category).filter(Category.parent_id == target_cat.id).all()
                filter_cat_ids = [target_cat.id] + [cc.id for cc in child_cats]
                query = query.filter(HQProduct.category_id.in_(filter_cat_ids))
            else:
                query = query.filter((Category.slug == sub_category) | (Category.name == sub_category))
        else:
            query = query.filter((Category.slug == sub_category) | (Category.name == sub_category))
        
    # 브랜드 필터링
    if brand_id is not None:
        query = query.filter(HQProduct.brand_id == brand_id)
    if brand_slug is not None:
        query = query.filter(Brand.slug == brand_slug)
        
    real_products = query.all()
    
    is_masked = current_user is None or current_user.grade == 5
    
    result = []
    for p in real_products:
        cat_slug = p.category.slug if p.category else "top"
        layer = "top"
        if p.category:
            if "bottom" in cat_slug or "하의" in p.category.name:
                layer = "bottom"
            elif "acc" in cat_slug or "가방" in p.category.name.lower():
                layer = "accessory"
            
        result.append({
            "id": p.id,
            "name": "🔒 가입 후 확인 가능" if is_masked else p.kr_name,
            "category": layer,
            "category_id": p.category_id,
            "category_name": p.category.name if p.category else "기타",
            "sub_category": p.category.name if p.category else "기타",
            "brand_id": p.brand_id,
            "brand_name": p.brand.name if p.brand else "미지정",
            "brand_eng_name": p.brand.eng_name if p.brand else "",
            "price": 0 if is_masked else p.base_price,
            "sale_price": 0 if is_masked else p.sale_price,
            "discount_rate": 0 if is_masked else p.discount_rate,
            "transparentImage": _display_image(p),
        })
        
    return result

@router.get("/{product_id}")
def get_product_detail(
    product_id: int, 
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    스토어프론트: 상품 단건 상세 조회
    - 상품의 모든 필드 반환
    - 같은 카테고리의 관련 상품 최대 8개 추가 반환
    """
    product = db.query(HQProduct).filter(
        HQProduct.id == product_id,
        HQProduct.status == "APPROVED"
    ).first()
    
    if not product:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    
    is_masked = current_user is None or current_user.grade == 5
    
    # 같은 카테고리의 관련 상품 (자기 자신 제외, 최대 8개)
    related = db.query(HQProduct).filter(
        HQProduct.category_id == product.category_id,
        HQProduct.id != product.id,
        HQProduct.status == "APPROVED"
    ).limit(8).all()
    
    related_list = []
    for r in related:
        related_list.append({
            "id": r.id,
            "name": "🔒 가입 후 확인 가능" if is_masked else r.kr_name,
            "price": 0 if is_masked else r.base_price,
            "sale_price": 0 if is_masked else r.sale_price,
            "discount_rate": 0 if is_masked else r.discount_rate,
            "image": (r.images[0] if r.images and len(r.images) > 0 
                      else r.ai_fitting_image_url 
                      or FALLBACK_PRODUCT_IMAGE),
        })
    
    cat_name = product.category.name if product.category else "기타"
    
    return {
        "id": product.id,
        "name": "🔒 가입 후 확인 가능" if is_masked else product.kr_name,
        "cn_name": "" if is_masked else product.cn_name,
        "category": cat_name,
        "category_id": product.category_id,
        "brand_id": product.brand_id,
        "brand_name": product.brand.name if product.brand else "미지정",
        "brand_eng_name": product.brand.eng_name if product.brand else "",
        "description": "가입 승인 후 조회가 가능합니다." if is_masked else product.kr_description,
        "description_html": "<div class='product-description'>🔒 가입 승인 후 상세 정보 조회가 가능합니다.</div>" if is_masked else product.description_html,
        "base_price": 0 if is_masked else product.base_price,
        "sale_price": 0 if is_masked else product.sale_price,
        "discount_rate": 0 if is_masked else product.discount_rate,
        "stock_quantity": 0 if is_masked else product.stock_quantity,
        "sku": "🔒" if is_masked else product.sku,
        "keywords": [] if is_masked else (product.keywords or []),
        "images": [] if is_masked else (product.images or []),
        "ai_fitting_image_url": None if is_masked else product.ai_fitting_image_url,
        "transparent_item_image_url": None if is_masked else product.transparent_item_image_url,
        "created_at": str(product.created_at) if (product.created_at and not is_masked) else None,
        "related_products": related_list,
    }


@router.get("/{product_id}/transparent-image")
def get_transparent_image(product_id: int, db: Session = Depends(get_db)):
    """
    상품의 투명배경(누끼) 이미지 URL 반환.
    SmartFittingCanvas 컴포넌트에서 인터랙티브 드래그 레이어로 사용.
    - transparent_item_image_url 존재 시 → 해당 URL
    - 없을 경우 → 첫번째 갤러리 이미지를 Fallback
    """
    from fastapi import HTTPException
    product = db.query(HQProduct).filter(HQProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
    
    transparent_url = product.transparent_item_image_url
    if not transparent_url and product.images and len(product.images) > 0:
        transparent_url = product.images[0]
    if not transparent_url:
        transparent_url = product.ai_fitting_image_url or FALLBACK_PRODUCT_IMAGE
    
    return {
        "product_id": product_id,
        "transparent_image_url": transparent_url,
        "product_name": product.kr_name,
    }

