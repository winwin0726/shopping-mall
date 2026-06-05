from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from backend.database import get_db
from backend.models import Order, OrderItem, HQProduct, User
from backend.utils.deps import get_current_user, get_current_admin
from backend.config import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Schema definitions
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int
    unit_price: int

class OrderCreate(BaseModel):
    user_id: Optional[int] = None
    order_number: str
    customer_name: str
    customer_phone: Optional[str] = None
    total_amount: int
    payment_method: str
    payment_status: Optional[str] = "PAID"
    payment_id: Optional[str] = None
    items: List[OrderItemCreate]

class OrderStatusUpdate(BaseModel):
    status: str

# Endpoints
@router.post("/orders")
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    """ Create a new order (usually called after successful payment) """
    # 클라이언트 금액/상태는 신뢰하지 않고 DB 기준으로 재계산·재고검증 (위변조·오버셀링 방지)
    server_total = 0
    valid_items = []
    for item in payload.items:
        product = db.query(HQProduct).filter(HQProduct.id == item.product_id).first()
        if not product:
            continue
        qty = max(1, int(item.quantity or 1))
        available = product.stock_quantity if product.stock_quantity is not None else 0
        if available < qty:
            raise HTTPException(status_code=409, detail=f"'{product.kr_name}' 재고가 부족합니다 (현재 {available}개).")
        unit_price = product.sale_price or product.base_price or 0
        server_total += unit_price * qty
        valid_items.append((product, qty, unit_price))

    if not valid_items:
        raise HTTPException(status_code=400, detail="유효한 주문 상품이 없습니다.")

    # 결제 상태: 개발 모드에서만 즉시 PAID, 운영에서는 PENDING (이후 payment/verify 로 확정)
    payment_status = (payload.payment_status or "PAID") if settings.PAYMENTS_DEV_MODE else "PENDING"

    new_order = Order(
        user_id=payload.user_id,
        order_number=payload.order_number,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        total_amount=server_total,
        payment_method=payload.payment_method,
        payment_status=payment_status,
        payment_id=payload.payment_id
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    for product, qty, unit_price in valid_items:
        db.add(OrderItem(
            order_id=new_order.id,
            product_id=product.id,
            quantity=qty,
            unit_price=unit_price
        ))
        product.stock_quantity = (product.stock_quantity or 0) - qty  # 재고 차감

    db.commit()
    return {"status": "success", "order_id": new_order.id, "total_amount": server_total, "payment_status": payment_status}

from backend.schemas import CheckoutCartRequest
from backend.models import CartItem
import uuid

@router.post("/checkout/cart")
def checkout_cart(payload: CheckoutCartRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """ 장바구니 데이터를 읽어 일괄 결제를 처리하고, 성공 시 장바구니를 비움 """
    
    # 1. 본인 장바구니 항목 조회 → 서버측 합계 재계산 + 재고 검증 (위변조·오버셀링 방지)
    server_total = 0
    cart_rows = []
    for cart_id in payload.cart_item_ids:
        cart_item = db.query(CartItem).filter(CartItem.id == cart_id, CartItem.user_id == current_user.id).first()
        if not cart_item:
            continue
        product = db.query(HQProduct).filter(HQProduct.id == cart_item.product_id).first()
        if not product:
            continue
        qty = max(1, int(cart_item.quantity or 1))
        available = product.stock_quantity if product.stock_quantity is not None else 0
        if available < qty:
            raise HTTPException(status_code=409, detail=f"'{product.kr_name}' 재고가 부족합니다 (현재 {available}개).")
        unit_price = product.sale_price or product.base_price or 0
        server_total += unit_price * qty
        cart_rows.append((cart_item, product, qty, unit_price))

    if not cart_rows:
        raise HTTPException(status_code=400, detail="결제할 장바구니 상품이 없습니다.")

    payment_status = "PAID" if settings.PAYMENTS_DEV_MODE else "PENDING"

    # 2. 새 주문 생성 (서버 재계산 금액 사용)
    order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    new_order = Order(
        user_id=current_user.id,
        order_number=order_number,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        total_amount=server_total,
        payment_method=payload.payment_method,
        payment_status=payment_status,
        payment_id=payload.payment_id,
        shipping_postal_code=payload.shipping_postal_code,
        shipping_address=payload.shipping_address,
        shipping_address_detail=payload.shipping_address_detail
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # 3. OrderItem 생성 + 재고 차감 + 장바구니 비우기
    for cart_item, product, qty, unit_price in cart_rows:
        db.add(OrderItem(
            order_id=new_order.id,
            product_id=product.id,
            quantity=qty,
            unit_price=unit_price
        ))
        product.stock_quantity = (product.stock_quantity or 0) - qty
        db.delete(cart_item)

    db.commit()
    return {"status": "success", "order_number": order_number, "order_id": new_order.id, "total_amount": server_total}

@router.get("/me/orders")
def get_my_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """ Get orders for the currently logged in user """
    orders = db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.id.desc()).all()
    
    result = []
    for o in orders:
        items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
        item_details = []
        product_names = []
        
        for item in items:
            product = db.query(HQProduct).filter(HQProduct.id == item.product_id).first()
            prod_name = product.kr_name if product else "알 수 없는 상품"
            product_names.append(prod_name)
            item_details.append({
                "product_id": item.product_id,
                "product_name": prod_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "image_url": product.ai_fitting_image_url if product and product.ai_fitting_image_url else None
            })
            
        summary_name = product_names[0] if product_names else "상품 없음"
        if len(product_names) > 1:
            summary_name += f" 외 {len(product_names) - 1}건"
            
        result.append({
            "id": o.id,
            "order_number": o.order_number,
            "total_amount": o.total_amount,
            "payment_status": o.payment_status,
            "shipping_status": o.shipping_status, # 추가: 배송상태
            "tracking_number": o.tracking_number, # 추가: 송장번호
            "created_at": str(o.created_at),
            "summary_name": summary_name,
            "items": item_details
        })
        
    return result

@router.get("/admin/orders")
def get_admin_orders(
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin)
):
    """ HQ Admin: Get all orders with optional filtering """
    query = db.query(Order)
    
    if status:
        query = query.filter(Order.payment_status == status)
    if search:
        query = query.filter(
            (Order.order_number.contains(search)) | 
            (Order.customer_name.contains(search))
        )
        
    orders = query.order_by(Order.id.desc()).all()
    
    result = []
    for o in orders:
        # Get items for this order
        items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
        item_details = []
        product_names = []
        
        for item in items:
            product = db.query(HQProduct).filter(HQProduct.id == item.product_id).first()
            prod_name = product.kr_name if product else "알 수 없는 상품"
            product_names.append(prod_name)
            item_details.append({
                "product_id": item.product_id,
                "product_name": prod_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price
            })
            
        # Summary product name (e.g., "Product A 외 2건")
        summary_name = product_names[0] if product_names else "상품 없음"
        if len(product_names) > 1:
            summary_name += f" 외 {len(product_names) - 1}건"
            
        result.append({
            "id": o.id,
            "order_number": o.order_number,
            "customer_name": o.customer_name,
            "customer_phone": o.customer_phone,
            "total_amount": o.total_amount,
            "payment_method": o.payment_method,
            "payment_status": o.payment_status,
            "payment_id": o.payment_id,
            "created_at": str(o.created_at),
            "summary_name": summary_name,
            "items": item_details
        })
        
    return result

@router.patch("/admin/orders/{order_id}/status")
def update_order_status(order_id: int, payload: OrderStatusUpdate, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """ HQ Admin: Update order status """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order.payment_status = payload.status
    db.commit()
    
    return {"status": "success", "new_status": order.payment_status}

class ShippingStatusUpdate(BaseModel):
    shipping_status: str  # "PREPARING" | "SHIPPING" | "DELIVERED"
    tracking_number: Optional[str] = None

@router.patch("/admin/orders/{order_id}/shipping")
def update_shipping_status(order_id: int, payload: ShippingStatusUpdate, db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """ HQ Admin: 배송 상태 및 운송장 번호 업데이트 """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.shipping_status = payload.shipping_status
    if payload.tracking_number is not None:
        order.tracking_number = payload.tracking_number
        
    # [고도화] 적립금 지급 로직 추가 (배송 완료이고 아직 처리되지 않은 경우)
    if payload.shipping_status == "DELIVERED" and not order.is_reward_processed:
        if order.user_id:
            user = db.query(User).filter(User.id == order.user_id).first()
            if user:
                # 등급별 적립율: 일반(4) 1%, 우수(3) 2%, VIP(2) 3%, VVIP(1) 5%, 관리자(0)/미가입(5) 0%
                rate_map = {0: 0.0, 1: 0.05, 2: 0.03, 3: 0.02, 4: 0.01, 5: 0.0}
                rate = rate_map.get(user.grade, 0.01) # 폴백: 일반(1%)
                
                points_to_add = int(order.total_amount * rate)
                if points_to_add > 0:
                    user.reward_points = (user.reward_points or 0) + points_to_add
                    order.is_reward_processed = True
    
    db.commit()
    
    return {
        "status": "success",
        "shipping_status": order.shipping_status,
        "tracking_number": order.tracking_number,
        "is_reward_processed": order.is_reward_processed
    }

@router.get("/admin/orders/stats")
def get_order_stats(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """ HQ Admin: Get basic statistics for the dashboard overview """
    # 1. Total revenue (PAID orders)
    revenue = db.query(func.sum(Order.total_amount)).filter(Order.payment_status == "PAID").scalar() or 0
    
    # 2. Total order count
    order_count = db.query(func.count(Order.id)).filter(Order.payment_status == "PAID").scalar() or 0
    
    # 3. Average order value
    avg_order_value = 0
    if order_count > 0:
        avg_order_value = int(revenue / order_count)
        
    # 4. Pending crawler items (for pipeline)
    pending_count = db.query(func.count(HQProduct.id)).filter(HQProduct.status == "PENDING").scalar() or 0
    
    # We could calculate trends here, but keep it simple for now
    
    return {
        "revenue": revenue,
        "order_count": order_count,
        "avg_order_value": avg_order_value,
        "pending_count": pending_count,
        "revenue_trend": "up",      # Dummy trend 
        "order_trend": "up"         # Dummy trend
    }

# ================================
# Payment Validation (PortOne 실무 검증)
# ================================
import os
import httpx

class PaymentVerifyRequest(BaseModel):
    imp_uid: str
    merchant_uid: str

@router.post("/payment/verify")
async def verify_payment(payload: PaymentVerifyRequest, db: Session = Depends(get_db)):
    """
    포트원(PortOne) 웹훅/클라이언트 통신 결제 사후 검증.
    결제금액 위변조 여부를 최종 확인하고 주문 상태를 확정합니다.
    """
    order = db.query(Order).filter(Order.order_number == payload.merchant_uid).first()
    if not order:
        raise HTTPException(status_code=404, detail="해당 주문을 찾을 수 없습니다.")

    PORTONE_API_KEY = os.getenv("PORTONE_API_KEY", "dummy_key")
    PORTONE_API_SECRET = os.getenv("PORTONE_API_SECRET", "dummy_secret")

    # 1. 포트원 인증 토큰 발급
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_res = await client.post("https://api.iamport.kr/users/getToken", json={
                "imp_key": PORTONE_API_KEY,
                "imp_secret": PORTONE_API_SECRET
            })
            token_res.raise_for_status()
            access_token = token_res.json()["response"]["access_token"]
            
            # 2. 결제 단건 조회
            headers = {"Authorization": f"Bearer {access_token}"}
            payment_res = await client.get(f"https://api.iamport.kr/payments/{payload.imp_uid}", headers=headers)
            payment_res.raise_for_status()
            payment_data = payment_res.json()["response"]
            
            # 3. 금액 검증 (사후조작 대조)
            paid_amount = payment_data.get("amount", 0)
            status = payment_data.get("status", "")
            
            if paid_amount == order.total_amount and status == "paid":
                order.payment_status = "PAID"
                order.payment_id = payload.imp_uid
                db.commit()
                return {"status": "success", "message": "결제 및 금액 위변조 검증 완료"}
            else:
                # 결제 금액 불일치 -> 조작 의심 혹은 다른 이슈
                order.payment_status = "FORGED_AMOUNT"
                db.commit()
                # 원래는 여기서 자동 환불(Cancel) 콜도 즉시 쏴서 피해를 최소화해야 함
                raise HTTPException(status_code=400, detail="결제 금액이 위변조되었거나 일치하지 않습니다.")

    except httpx.HTTPError:
        # 개발 모드에서만 PG 검증을 우회 (운영(PAYMENTS_DEV_MODE=False)에서는 실패 처리)
        if settings.PAYMENTS_DEV_MODE:
            order.payment_status = "PAID"
            order.payment_id = payload.imp_uid
            db.commit()
            logger.warning("[PAYMENTS_DEV_MODE] PG 검증을 우회했습니다. 운영 배포 전 PAYMENTS_DEV_MODE=False 로 설정하세요.")
            return {"status": "success", "message": "[DEV MODE] 결제 확인(검증 우회). 운영 전 비활성화 필요."}

        raise HTTPException(status_code=500, detail="포트원 서버와 통신 중 오류가 발생했습니다.")

