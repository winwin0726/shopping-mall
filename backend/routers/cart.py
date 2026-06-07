from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from backend.database import get_db
from backend.models import User, CartItem, HQProduct
from backend.schemas import CartItemCreate, CartItemResponse, CartItemUpdate
from backend.utils.deps import get_current_user

router = APIRouter()

@router.get("/me", response_model=List[CartItemResponse])
def get_my_cart(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """ Get the cart items for the current user """
    items = (
        db.query(CartItem)
        .options(joinedload(CartItem.product).joinedload(HQProduct.category))
        .filter(CartItem.user_id == current_user.id)
        .order_by(CartItem.id.desc())
        .all()
    )

    result = []
    for item in items:
        # Load associated product (eager-loaded — N+1 제거, F1)
        product = item.product
        
        # Category resolution for fitting room mapping
        layer = "top"
        if product and product.category:
            cat_slug = product.category.slug
            if "bottom" in cat_slug or "하의" in product.category.name:
                layer = "bottom"
            elif "acc" in cat_slug or "가방" in product.category.name:
                layer = "accessory"
                
        result.append({
            "id": item.id,
            "product_id": item.product_id,
            "quantity": item.quantity,
            "created_at": item.created_at,
            "product_name": product.kr_name if product else "Unknown Product",
            "product_price": product.sale_price if product and product.sale_price else (product.base_price if product else 0),
            "product_image": product.ai_fitting_image_url if product else None,
            "transparent_image": product.transparent_item_image_url if product else None,
            "product_category": layer
        })
    return result


@router.post("/items", response_model=CartItemResponse)
def add_to_cart(
    payload: CartItemCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """ Add an item to cart or increment quantity if it already exists """
    # 1. Product Validation
    product = db.query(HQProduct).filter(HQProduct.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 2. Check if already in cart
    existing_item = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.product_id == payload.product_id
    ).first()

    # E3: 재고 초과 담기 방지 (기존 담긴 수량 + 추가 수량 > 재고 → 거부)
    stock = product.stock_quantity if product.stock_quantity is not None else 0
    desired = (existing_item.quantity if existing_item else 0) + payload.quantity
    if desired > stock:
        raise HTTPException(status_code=409, detail=f"재고가 부족합니다. (남은 수량 {stock}개)")

    if existing_item:
        existing_item.quantity += payload.quantity
        db.commit()
        db.refresh(existing_item)
        target_item = existing_item
    else:
        new_item = CartItem(
            user_id=current_user.id,
            product_id=payload.product_id,
            quantity=payload.quantity
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        target_item = new_item

    layer = "top"
    if product and product.category:
        cat_slug = product.category.slug
        if "bottom" in cat_slug or "하의" in product.category.name:
            layer = "bottom"
        elif "acc" in cat_slug or "가방" in product.category.name:
            layer = "accessory"

    return {
        "id": target_item.id,
        "product_id": target_item.product_id,
        "quantity": target_item.quantity,
        "created_at": target_item.created_at,
        "product_name": product.kr_name,
        "product_price": product.sale_price or product.base_price,
        "product_image": product.ai_fitting_image_url,
        "transparent_image": product.transparent_item_image_url,
        "product_category": layer
    }


@router.put("/items/{item_id}")
def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ Update item quantity in the cart. 수량이 0 이하이면 해당 항목을 삭제한다. """
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    if payload.quantity <= 0:
        # 정상 흐름을 예외(204)로 던지던 안티패턴 제거 — 일반 200 응답으로 삭제 통지 (A3)
        db.delete(item)
        db.commit()
        return {"status": "deleted", "id": item_id}

    # E3: 재고 초과 수정 방지
    product = db.query(HQProduct).filter(HQProduct.id == item.product_id).first()
    stock = product.stock_quantity if (product and product.stock_quantity is not None) else 0
    if payload.quantity > stock:
        raise HTTPException(status_code=409, detail=f"재고가 부족합니다. (남은 수량 {stock}개)")

    item.quantity = payload.quantity
    db.commit()
    db.refresh(item)
    
    product = db.query(HQProduct).filter(HQProduct.id == item.product_id).first()
    
    layer = "top"
    if product and product.category:
        cat_slug = product.category.slug
        if "bottom" in cat_slug or "하의" in product.category.name:
            layer = "bottom"
        elif "acc" in cat_slug or "가방" in product.category.name:
            layer = "accessory"

    return {
        "id": item.id,
        "product_id": item.product_id,
        "quantity": item.quantity,
        "created_at": item.created_at,
        "product_name": product.kr_name if product else "Unknown",
        "product_price": product.sale_price or product.base_price if product else 0,
        "product_image": product.ai_fitting_image_url if product else None,
        "transparent_image": product.transparent_item_image_url if product else None,
        "product_category": layer
    }


@router.delete("/items/{item_id}")
def delete_cart_item(
    item_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """ Remove an item from the cart entirely """
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.user_id == current_user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    db.delete(item)
    db.commit()
    return {"status": "success", "message": "Item removed from cart"}
