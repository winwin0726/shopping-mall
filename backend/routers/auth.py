from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Any
import os
import shutil
import uuid

from backend.database import get_db
from backend.models import User
from backend.schemas import UserCreate, UserResponse, UserUpdate
from backend.utils.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from backend.utils.deps import get_current_user

router = APIRouter()

@router.post("/register", response_model=UserResponse)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)) -> Any:
    # 이메일 중복 확인
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    hashed = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email,
        hashed_password=hashed,
        name=user_in.name,
        phone=user_in.phone
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

from backend.models import Coupon

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Any:
    """
    OAuth2 compatible token login, getting an access token for future requests.
    (Note: OAuth2PasswordRequestForm uses 'username' field for email)
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화되었거나 탈퇴한 계정입니다.",
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    coupon_cnt = db.query(Coupon).filter(Coupon.user_id == user.id, Coupon.is_used == False).count()
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "grade": user.grade if user.grade is not None else 4,
            "reward_points": user.reward_points if user.reward_points is not None else 0,
            "coupon_count": coupon_cnt
        }
    }

@router.get("/me", response_model=UserResponse)
def get_user_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """현재 로그인 사용자 정보 반환 (부수효과 없음 — 멱등)."""
    coupon_cnt = db.query(Coupon).filter(Coupon.user_id == current_user.id, Coupon.is_used == False).count()
    current_user.coupon_count = coupon_cnt
    return current_user


@router.get("/me/coupons")
def get_my_coupons(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """현재 로그인 사용자의 사용 가능한(미사용) 쿠폰 목록. 체크아웃에서 선택용."""
    coupons = (
        db.query(Coupon)
        .filter(Coupon.user_id == current_user.id, Coupon.is_used == False)
        .order_by(Coupon.id.desc())
        .all()
    )
    return [
        {"id": c.id, "code": c.code, "name": c.name, "discount_amount": c.discount_amount}
        for c in coupons
    ]


@router.post("/me/visit-reward")
def claim_visit_reward(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    방문 적립금 지급 (1회 200P, 일 최대 2회, 12시간 간격).
    상태를 변경하는 액션이므로 GET /me 와 분리하여 POST 로 노출 (멱등성 확보).
    """
    now_utc = datetime.utcnow()
    now_kst = now_utc + timedelta(hours=9)  # KST
    today_str = now_kst.strftime("%Y-%m-%d")

    # 마지막 적립일이 오늘과 다르면 횟수 리셋
    if current_user.last_visit_reward_date != today_str:
        current_user.today_visit_reward_count = 0
        current_user.last_visit_reward_date = today_str

    awarded = 0
    if (current_user.today_visit_reward_count or 0) < 2:
        can_reward = True
        if current_user.last_visit_reward_at:
            if (now_utc - current_user.last_visit_reward_at) < timedelta(hours=12):
                can_reward = False
        if can_reward:
            awarded = 200
            current_user.reward_points = (current_user.reward_points or 0) + awarded
            current_user.today_visit_reward_count = (current_user.today_visit_reward_count or 0) + 1
            current_user.last_visit_reward_at = now_utc
            db.add(current_user)
            db.commit()
            db.refresh(current_user)

    return {"awarded": awarded, "reward_points": current_user.reward_points or 0}

@router.patch("/me", response_model=UserResponse)
def update_user_me(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update my profile information (name, phone, password, profile_image).
    """
    if user_in.name:
        current_user.name = user_in.name
    if user_in.phone:
        current_user.phone = user_in.phone
    if user_in.profile_image:
        current_user.profile_image = user_in.profile_image
    if user_in.password:
        current_user.hashed_password = get_password_hash(user_in.password)
        
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.delete("/me")
def delete_user_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Soft delete user account.
    """
    current_user.is_active = False
    db.add(current_user)
    db.commit()
    return {"status": "success", "message": "Account successfully disabled."}

# Profile image upload directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "profiles")
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/me/profile-image", response_model=UserResponse)
def upload_profile_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Upload and set a profile image for the current user.
    """
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    new_filename = f"profile_{current_user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, new_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    web_path = f"/uploads/profiles/{new_filename}"
    
    current_user.profile_image = web_path
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    
    return current_user
