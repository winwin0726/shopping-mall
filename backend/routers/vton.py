from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from backend.ai_engine.vton import smart_layering_vton, smart_fit_single_product

router = APIRouter()

# =============================================
# 1) 스마트 믹스앤매치 (상/하의 조합 레이어링)
# =============================================
class SmartLayeringRequest(BaseModel):
    top_id: Optional[int] = None
    bottom_id: Optional[int] = None

class SmartLayeringResponse(BaseModel):
    result_url: str
    message: str

@router.post("/smart-layering", response_model=SmartLayeringResponse)
async def generate_smart_layering(payload: SmartLayeringRequest):
    """IDM-VTON 기반 상/하의 믹스앤매치 합성 API"""
    if not payload.top_id and not payload.bottom_id:
        raise HTTPException(status_code=400, detail="상의 또는 하의 중 최소 1개를 선택해야 합니다.")
        
    try:
        result_image_url = await smart_layering_vton(payload.top_id, payload.bottom_id)
        
        return SmartLayeringResponse(
            result_url=result_image_url,
            message="Smart layering completed via IDM-VTON pipeline."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VTON Rendering Error: {str(e)}")


# =============================================
# 2) 스마트 피팅 (단일 상품 + 체형 데이터)
# =============================================
class SmartFitRequest(BaseModel):
    """사용자 체형 정보 + 상품 ID 기반 스마트 피팅 요청"""
    product_id: int = Field(..., description="피팅할 상품 ID")
    height: float = Field(default=170.0, ge=100, le=220, description="키 (cm)")
    weight: float = Field(default=65.0, ge=30, le=200, description="몸무게 (kg)")
    shoulder_width: float = Field(default=44.0, ge=30, le=60, description="어깨너비 (cm)")
    model_type: str = Field(default="mannequin", description="모델 타입: mannequin | custom")

class SmartFitResponse(BaseModel):
    fitting_url: str
    product_id: int
    render_time_ms: int
    confidence_score: float = Field(description="피팅 신뢰도 (0.0~1.0)")
    body_params: dict
    message: str

@router.post("/smart-fit", response_model=SmartFitResponse)
async def generate_smart_fit(payload: SmartFitRequest):
    """
    단일 상품 + 사용자 체형 기반 스마트 AI 피팅
    - 체형 파라미터(키/몸무게/어깨너비)를 AI 엔진으로 전달
    - 캐시 HIT 시 비용 $0, MISS 시 외부 API 1회 호출 후 캐싱
    """
    try:
        result = await smart_fit_single_product(
            product_id=payload.product_id,
            height=payload.height,
            weight=payload.weight,
            shoulder_width=payload.shoulder_width,
            model_type=payload.model_type,
        )
        
        return SmartFitResponse(
            fitting_url=result["fitting_url"],
            product_id=payload.product_id,
            render_time_ms=result["render_time_ms"],
            confidence_score=result["confidence_score"],
            body_params={
                "height": payload.height,
                "weight": payload.weight,
                "shoulder_width": payload.shoulder_width,
            },
            message=result["message"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Smart Fit Error: {str(e)}")
