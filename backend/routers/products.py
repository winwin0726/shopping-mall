from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models import HQProduct, Category

router = APIRouter()

# Schema for response (Mocking Pydantic for brevity, full Pydantic should be in schemas.py)
@router.get("/", response_model=List[dict])
def get_products(db: Session = Depends(get_db)):
    """
    Returns the list of HQ products with their transparent images for VTON.
    Using real DB data.
    """
    products = db.query(HQProduct).join(Category).filter(HQProduct.status == "APPROVED").all()
    
    result = []
    for p in products:
        # DB에서 slug (top, bottom, accessory) 등을 바로 사용하도록 설정
        cat_slug = p.category.slug if p.category else "top"
        # 피팅룸 컴포넌트 호환성을 위해 "상의", "하의" 등을 top, bottom 매핑할 수 있으나 임시로 slug 사용.
        # category_slug -> top, bottom, accessory
        layer = "top"
        if "bottom" in cat_slug or "하의" in p.category.name:
            layer = "bottom"
        elif "acc" in cat_slug or "가방" in p.category.name:
            layer = "accessory"
            
        result.append({
            "id": p.id,
            "name": p.kr_name,
            "category": layer,
            "price": p.base_price,
            "transparentImage": p.transparent_item_image_url or "https://cdn-icons-png.flaticon.com/512/863/863684.png"
        })
    
    return result

@router.get("/category/{main_category}", response_model=List[dict])
def get_products_by_category(main_category: str, sub_category: str = None, db: Session = Depends(get_db)):
    """
    Returns products filtered by main category (e.g., '남성의류') and optionally by subcategory.
    """
    query = db.query(HQProduct).join(Category).filter(HQProduct.status == "APPROVED")
    
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
            # 해당 대분류 아래의 모든 하위 중분류 및 소분류 수집하여 이름 매칭 (동명이명 중복 방지)
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
        
    real_products = query.all()

    
    result = []
    for p in real_products:
        cat_slug = p.category.slug if p.category else "top"
        layer = "top"
        if "bottom" in cat_slug or "하의" in p.category.name:
            layer = "bottom"
        elif "acc" in cat_slug or "가방" in p.category.name.lower():
            layer = "accessory"
            
        result.append({
            "id": p.id,
            "name": p.kr_name,
            "category": layer,
            "sub_category": p.category.name if p.category else "기타",
            "price": p.base_price,
            "transparentImage": p.ai_fitting_image_url or "https://cdn-icons-png.flaticon.com/512/863/863684.png"
        })
        
    return result

@router.get("/{product_id}")
def get_product_detail(product_id: int, db: Session = Depends(get_db)):
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
            "name": r.kr_name,
            "price": r.base_price,
            "sale_price": r.sale_price,
            "discount_rate": r.discount_rate,
            "image": (r.images[0] if r.images and len(r.images) > 0 
                      else r.ai_fitting_image_url 
                      or "https://cdn-icons-png.flaticon.com/512/863/863684.png"),
        })
    
    cat_name = product.category.name if product.category else "기타"
    
    return {
        "id": product.id,
        "name": product.kr_name,
        "cn_name": product.cn_name,
        "category": cat_name,
        "category_id": product.category_id,
        "description": product.kr_description,
        "description_html": product.description_html,
        "base_price": product.base_price,
        "sale_price": product.sale_price,
        "discount_rate": product.discount_rate,
        "stock_quantity": product.stock_quantity,
        "sku": product.sku,
        "keywords": product.keywords or [],
        "images": product.images or [],
        "ai_fitting_image_url": product.ai_fitting_image_url,
        "transparent_item_image_url": product.transparent_item_image_url,
        "created_at": str(product.created_at) if product.created_at else None,
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
        transparent_url = product.ai_fitting_image_url or "https://cdn-icons-png.flaticon.com/512/863/863684.png"
    
    return {
        "product_id": product_id,
        "transparent_image_url": transparent_url,
        "product_name": product.kr_name,
    }

