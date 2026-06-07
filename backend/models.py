from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, JSON, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    profile_image = Column(String, nullable=True) # 신규 업로드 항목
    role = Column(String, default="USER") # USER, ADMIN
    grade = Column(Integer, default=4) # 0: ADMIN, 1: VVIP, 2: VIP, 3: 우수, 4: 일반, 5: 미가입
    reward_points = Column(Integer, default=0) # 적립금
    
    # [방문적립금 고도화] 12시간 주기 및 일일 한도 제어용 컬럼 추가
    last_visit_reward_at = Column(DateTime, nullable=True)
    today_visit_reward_count = Column(Integer, default=0)
    last_visit_reward_date = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, index=True, nullable=False) # e.g., 'hq.mall.com', 'sub1.mall.com'
    name = Column(String, nullable=False)
    theme_config = Column(JSON, nullable=True) # UI theming for sub-malls
    is_active = Column(Boolean, default=True)
    
    products = relationship("TenantProduct", back_populates="tenant")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey('categories.id'), nullable=True)
    name = Column(String, nullable=False, index=True) # 남성의류, 여성의류, etc.
    slug = Column(String, unique=True, index=True)
    # [윈윈 도킹] 카테고리별 소매 마진 (도매가 → 소매가 변환). margin_type: 'percent' | 'fixed'
    margin_type = Column(String, default="percent")
    margin_value = Column(Float, default=30.0)  # percent면 %, fixed면 원(￦)

    parent = relationship("Category", remote_side=[id], backref="children")
    products = relationship("HQProduct", back_populates="category")

class Brand(Base):
    __tablename__ = "brands"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)       # 한글명 (예: 루이비통)
    eng_name = Column(String, nullable=False, index=True)   # 영문명 (예: Louis Vuitton)
    slug = Column(String, unique=True, index=True, nullable=False) # URL 주소용 (예: louis-vuitton)
    logo_url = Column(String, nullable=True)
    is_premium = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    category_group = Column(String, default="all", nullable=True) # 품목 매핑용 카테고리 그룹 (예: 'all', 'shoes', 'watch', 'bag,wallet')
    
    products = relationship("HQProduct", back_populates="brand")

class HQProduct(Base):
    __tablename__ = "hq_products"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    brand_id = Column(Integer, ForeignKey('brands.id'), nullable=True)
    
    # Crawler data
    original_source_url = Column(String, nullable=True)
    cn_name = Column(String, nullable=True)
    
    # AI Translated data
    kr_name = Column(String, nullable=False, index=True)
    kr_description = Column(Text, nullable=True)
    description_html = Column(Text, nullable=True) # Full HTML Source from Rich Editor
    
    base_price = Column(Integer, nullable=False, default=0)
    wholesale_price = Column(Integer, nullable=True, default=0)  # [윈윈 도킹] 윈윈크롤러 도매원가(원)
    sale_price = Column(Integer, nullable=True)
    discount_rate = Column(Integer, nullable=True)
    
    stock_quantity = Column(Integer, default=0)
    sku = Column(String, nullable=True, index=True)
    
    keywords = Column(JSON, nullable=True) # Array of strings for tags
    images = Column(JSON, nullable=True) # Array of Image URLs for Gallery
    
    # AI Cache Image Path
    ai_fitting_image_url = Column(String, nullable=True)  # Pre-generated fitting image for UI
    transparent_item_image_url = Column(String, nullable=True)  # Transparent background(누끼) for Canvas
    pre_rendered_vtons = Column(JSON, default={}) # 선제적 프리-렌더링 딕셔너리 (체형 버켓 URL 보관)
    video_url = Column(String, nullable=True) # 상품 동영상 URL (MP4 / 유튜브)
    size_stock_config = Column(JSON, nullable=True) # JSON config for sizes and options
    
    status = Column(String, default="PENDING") # PENDING, APPROVED, REJECTED
    created_at = Column(DateTime, default=datetime.utcnow)
    
    category = relationship("Category", back_populates="products")
    brand = relationship("Brand", back_populates="products")
    tenant_links = relationship("TenantProduct", back_populates="product")

class TenantProduct(Base):
    """
    Mapping table to allow Sub-malls to have custom pricing or visibility for HQ products.
    """
    __tablename__ = "tenant_products"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('hq_products.id'), nullable=False)
    
    custom_price = Column(Integer, nullable=True) # Overrides HQ base_price if not null
    is_visible = Column(Boolean, default=True) # Allows specific tenants to hide an item
    
    tenant = relationship("Tenant", back_populates="products")
    product = relationship("HQProduct", back_populates="tenant_links")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True) # 신규 회원 연동
    order_number = Column(String, unique=True, index=True, nullable=False)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=True)
    
    total_amount = Column(Integer, nullable=False, default=0)
    payment_method = Column(String, nullable=False) # e.g., EASY_PAY, CARD
    payment_status = Column(String, default="PAID") # PAID, PENDING, CANCELLED
    payment_id = Column(String, nullable=True) # PortOne payment ID
    
    # 배송 기능 코어
    shipping_status = Column(String, default="PREPARING") # PREPARING, SHIPPING, DELIVERED
    tracking_number = Column(String, nullable=True) # 운송장 번호
    shipping_postal_code = Column(String, nullable=True)
    shipping_address = Column(String, nullable=True)
    shipping_address_detail = Column(String, nullable=True)
    is_reward_processed = Column(Boolean, default=False)
    # 결제 시 적용된 할인 내역 (영수증/환불 추적용)
    discount_amount = Column(Integer, default=0)  # 쿠폰 할인액
    used_points = Column(Integer, default=0)      # 사용한 적립금(원)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("OrderItem", back_populates="order")

class AddressBook(Base):
    """ 배송지 주소록 모델 """
    __tablename__ = "address_book"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    address_line1 = Column(String, nullable=False)
    address_line2 = Column(String, nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('hq_products.id'), nullable=False)
    
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Integer, nullable=False)
    
    order = relationship("Order", back_populates="items")
    product = relationship("HQProduct")

# ================================
# Shopping Cart & Wishlist Models
# ================================

class CartItem(Base):
    """ 장바구니 모델 (User N:1, Product N:1 연결) """
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("hq_products.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship Setup
    user = relationship("User")
    product = relationship("HQProduct")

class WishlistItem(Base):
    """ 위시리스트 모델 (User N:1, Product N:1 연결) """
    __tablename__ = "wishlist_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("hq_products.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    product = relationship("HQProduct")

# ================================
# Review & Support Models
# ================================

class Review(Base):
    """ 상품 리뷰 모델 """
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("hq_products.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False, default=5)  # 1~5
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    product = relationship("HQProduct")

class SupportTicket(Base):
    """ 1:1 고객 문의 모델 """
    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String, default="PENDING")  # PENDING, ANSWERED, CLOSED
    answer = Column(Text, nullable=True)         # 관리자 답변
    answered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

class Coupon(Base):
    """ 할인쿠폰 모델 """
    __tablename__ = "coupons"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code = Column(String, unique=True, index=True, nullable=False) # e.g. "CPN-XXXXXX"
    name = Column(String, nullable=False)
    discount_amount = Column(Integer, nullable=False, default=0)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")
