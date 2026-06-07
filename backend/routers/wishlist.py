from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from backend.database import get_db
from backend.models import User, WishlistItem, HQProduct
from backend.schemas import WishlistItemResponse, WishlistToggleRequest
from backend.utils.deps import get_current_user

router = APIRouter()

@router.get("/me", response_model=List[WishlistItemResponse])
def get_my_wishlist(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """ Get the wishlist items for the current user """
    items = (
        db.query(WishlistItem)
        .options(joinedload(WishlistItem.product))
        .filter(WishlistItem.user_id == current_user.id)
        .order_by(WishlistItem.id.desc())
        .all()
    )

    result = []
    for item in items:
        # Load associated product (eager-loaded — N+1 제거, F1)
        product = item.product
        result.append({
            "id": item.id,
            "product_id": item.product_id,
            "created_at": item.created_at,
            "product_name": product.kr_name if product else "Unknown Product",
            "product_price": product.sale_price if product and product.sale_price else (product.base_price if product else 0),
            "product_image": product.ai_fitting_image_url if product else None
        })
    return result

@router.post("/toggle")
def toggle_wishlist(
    payload: WishlistToggleRequest, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """ Toggle wishlist status: Add if not exists, remove if it does. """
    product = db.query(HQProduct).filter(HQProduct.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing_item = db.query(WishlistItem).filter(
        WishlistItem.user_id == current_user.id,
        WishlistItem.product_id == payload.product_id
    ).first()

    if existing_item:
        # Action: Remove
        db.delete(existing_item)
        db.commit()
        return {"status": "removed", "message": "Removed from wishlist", "product_id": payload.product_id}
    else:
        # Action: Add
        new_item = WishlistItem(
            user_id=current_user.id,
            product_id=payload.product_id
        )
        db.add(new_item)
        db.commit()
        return {"status": "added", "message": "Added to wishlist", "product_id": payload.product_id}
