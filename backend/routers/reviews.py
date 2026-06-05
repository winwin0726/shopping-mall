from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.models import User, Review, HQProduct
from backend.schemas import ReviewCreate, ReviewResponse
from backend.utils.deps import get_current_user

router = APIRouter()


@router.post("/", response_model=ReviewResponse)
def create_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """상품 리뷰 작성"""
    # 평점 범위 보정
    rating = max(1, min(5, payload.rating))

    product = db.query(HQProduct).filter(HQProduct.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    new_review = Review(
        user_id=current_user.id,
        product_id=payload.product_id,
        rating=rating,
        content=payload.content,
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)

    return ReviewResponse(
        id=new_review.id,
        user_id=new_review.user_id,
        product_id=new_review.product_id,
        rating=new_review.rating,
        content=new_review.content,
        created_at=new_review.created_at,
        product_name=product.kr_name,
        product_image=(product.images or [None])[0],
    )


@router.get("/me", response_model=List[ReviewResponse])
def get_my_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """내가 작성한 리뷰 전체 조회"""
    reviews = (
        db.query(Review)
        .filter(Review.user_id == current_user.id)
        .order_by(Review.id.desc())
        .all()
    )

    result = []
    for r in reviews:
        product = db.query(HQProduct).filter(HQProduct.id == r.product_id).first()
        result.append(
            ReviewResponse(
                id=r.id,
                user_id=r.user_id,
                product_id=r.product_id,
                rating=r.rating,
                content=r.content,
                created_at=r.created_at,
                product_name=product.kr_name if product else "삭제된 상품",
                product_image=(product.images or [None])[0] if product else None,
            )
        )
    return result


@router.delete("/{review_id}")
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """내 리뷰 삭제"""
    review = (
        db.query(Review)
        .filter(Review.id == review_id, Review.user_id == current_user.id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    db.delete(review)
    db.commit()
    return {"status": "success"}
