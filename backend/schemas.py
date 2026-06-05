from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# =======================
# User Authentication Schemas
# =======================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    phone: Optional[str]
    profile_image: Optional[str] = None
    role: str
    grade: int = 4
    reward_points: int = 0
    coupon_count: int = 0
    is_active: bool
    created_at: datetime
    
    # In Pydantic V2, from_attributes is the replacement for orm_mode=True
    model_config = {"from_attributes": True}

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    profile_image: Optional[str] = None
    password: Optional[str] = None

# =======================
# Cart & Wishlist Schemas
# =======================

class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1

class CartItemUpdate(BaseModel):
    quantity: int

class CartItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    created_at: datetime
    # 조인 후 내려줄 상품 정보
    product_name: Optional[str] = None
    product_price: Optional[int] = None
    product_image: Optional[str] = None
    transparent_image: Optional[str] = None
    product_category: Optional[str] = None

    model_config = {"from_attributes": True}


class WishlistToggleRequest(BaseModel):
    product_id: int

class WishlistItemResponse(BaseModel):
    id: int
    product_id: int
    created_at: datetime
    # 조인 후 내려줄 상품 정보
    product_name: Optional[str] = None
    product_price: Optional[int] = None
    product_image: Optional[str] = None

    model_config = {"from_attributes": True}

# =======================
# Address Book Schemas
# =======================

class AddressBookBase(BaseModel):
    recipient_name: str
    phone: str
    postal_code: str
    address_line1: str
    address_line2: Optional[str] = None
    is_default: bool = False

class AddressBookCreate(AddressBookBase):
    pass

class AddressBookUpdate(BaseModel):
    recipient_name: Optional[str] = None
    phone: Optional[str] = None
    postal_code: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    is_default: Optional[bool] = None

class AddressBookResponse(AddressBookBase):
    id: int
    user_id: int
    created_at: datetime
    model_config = {"from_attributes": True}

# =======================
# Order Checkout Schemas
# =======================
from typing import List

class CheckoutCartRequest(BaseModel):
    cart_item_ids: List[int]
    total_amount: int
    payment_method: str
    payment_id: Optional[str] = None
    customer_name: str
    customer_phone: Optional[str] = None
    shipping_postal_code: Optional[str] = None
    shipping_address: Optional[str] = None
    shipping_address_detail: Optional[str] = None

# =======================
# Review Schemas
# =======================

class ReviewCreate(BaseModel):
    product_id: int
    rating: int  # 1~5
    content: Optional[str] = None

class ReviewResponse(BaseModel):
    id: int
    user_id: int
    product_id: int
    rating: int
    content: Optional[str] = None
    created_at: datetime
    product_name: Optional[str] = None
    product_image: Optional[str] = None
    model_config = {"from_attributes": True}

# =======================
# Support Ticket Schemas
# =======================

class TicketCreate(BaseModel):
    subject: str
    content: str

class TicketResponse(BaseModel):
    id: int
    user_id: int
    subject: str
    content: str
    status: str
    answer: Optional[str] = None
    answered_at: Optional[datetime] = None
    created_at: datetime
    model_config = {"from_attributes": True}
