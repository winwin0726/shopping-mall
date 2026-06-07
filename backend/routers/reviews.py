from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from backend.database import get_db
from backend.models import User, Review, HQProduct, Order, OrderItem
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

    # E2: 같은 상품 중복 리뷰 방지 (1인 1상품 1리뷰)
    dup = db.query(Review).filter(
        Review.user_id == current_user.id,
        Review.product_id == payload.product_id,
    ).first()
    if dup:
        raise HTTPException(status_code=400, detail="이미 이 상품에 리뷰를 작성하셨습니다.")

    # E2: 구매 이력이 있는 상품만 리뷰 허용
    purchased = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.user_id == current_user.id, OrderItem.product_id == payload.product_id)
        .first()
    )
    if not purchased:
        raise HTTPException(status_code=403, detail="구매한 상품에만 리뷰를 작성할 수 있습니다.")

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


@router.get("/product/{product_id}")
def get_product_reviews(product_id: int, db: Session = Depends(get_db)):
    """상품별 공개 리뷰 목록 + 평점 요약 (비로그인도 조회 가능). 작성자명은 마스킹."""
    reviews = (
        db.query(Review)
        .options(joinedload(Review.user))
        .filter(Review.product_id == product_id)
        .order_by(Review.id.desc())
        .all()
    )
    items = []
    total = 0
    for r in reviews:
        total += r.rating or 0
        name = (r.user.name if r.user else None) or "익명"
        masked = name[0] + ("*" * (len(name) - 1)) if len(name) > 1 else name
        items.append({
            "id": r.id,
            "rating": r.rating,
            "content": r.content,
            "user_name": masked,
            "created_at": str(r.created_at) if r.created_at else None,
        })
    count = len(items)
    average = round(total / count, 1) if count else 0
    return {"count": count, "average": average, "items": items}


@router.get("/me", response_model=List[ReviewResponse])
def get_my_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """내가 작성한 리뷰 전체 조회"""
    reviews = (
        db.query(Review)
        .options(joinedload(Review.product))
        .filter(Review.user_id == current_user.id)
        .order_by(Review.id.desc())
        .all()
    )

    result = []
    for r in reviews:
        product = r.product
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
