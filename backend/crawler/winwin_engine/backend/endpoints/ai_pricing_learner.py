from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import json
import re

router = APIRouter()

VENDOR_RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "vendor_rules.json")

class PriceLearnRequest(BaseModel):
    vendor_name: str
    sample_text: str
    api_key: str | None = None

class PriceLearnResponse(BaseModel):
    success: bool
    pattern: str = ""
    extracted_price: str = ""
    reasoning: str = ""
    error: str = ""

def load_vendor_rules():
    if not os.path.exists(VENDOR_RULES_PATH):
        return {}
    try:
        with open(VENDOR_RULES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_vendor_rules(rules):
    with open(VENDOR_RULES_PATH, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=4)

@router.post("/learn_vendor_price_rule", response_model=PriceLearnResponse)
async def learn_vendor_price_rule(req: PriceLearnRequest):
    """
    AI를 이용해 판매자 전용 단가 표기 패턴을 도출합니다.
    """
    try:
        from google.genai import Client
        # 1순위: 클라이언트(UI)에서 전달된 API 키 사용
        api_key = req.api_key
        
        # 2순위: config.json 에서 로드 (하위 호환)
        if not api_key:
            config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    api_key = cfg.get("gemini_api_key")
                
        if not api_key:
            return PriceLearnResponse(success=False, error="Gemini API Key가 설정되지 않았습니다.")
            
        client = Client(api_key=api_key)
        
        prompt = f"""
다음은 중국 도매/의류/가방 등 Weishang 판매자의 포스팅 원문입니다.
이 텍스트 어딘가에 위안화 원가(단가)가 숨어 있습니다.
주로 다음과 같은 패턴이 존재합니다:
1. 기호/이모지 뒤: 🅿 150, 💰150, 🔎150, ¥150
2. 알파벳/한자 뒤: P 150, p150, 米 150, ㄷㄱ 150
3. 특수 괄호 안 숫자: 【150】, [150], (150)
4. 맨 마지막 줄에 의미 없이 숫자만 단독으로 존재: 150

당신은 이 판매자의 원문 텍스트를 분석하여, 단가(위안화 숫자)를 정확히 뽑아낼 수 있는 파이썬 정규표현식(Regex) 패턴을 만들어야 합니다.
작성한 정규식은 `re.search(pattern, text).group(1)`을 통해 반드시 숫자가 첫 번째 그룹(group 1)에 캡처되도록 소괄호 `(\\d+)` 를 포함해야 합니다.

[판매자 이름] : {req.vendor_name}
[원문 텍스트] : 
{req.sample_text}

[주의사항]
- 캡처 그룹(Parentheses)은 오직 단가 숫자 `(\\d+)`에만 하나 적용하세요. 비캡처 그룹 `(?:)` 은 자유롭게 사용 가능합니다.
- 불필요한 백슬래시 이스케이프(예: `\\\\d` 대신 `\\d` 사용 등)를 하지 말고, 파이썬 r'' 안에 들어갈 순수한 정규식 문자열만 작성하세요.
- 결과는 반드시 아래 JSON 형식으로만 출력하세요. 다른 설명은 절대 금지합니다.

{{
    "pattern": "(?:🅿|P|💰|米|¥)\\s*(\\d+)",
    "extracted_price": "150",
    "reasoning": "가격 앞에 🅿 이모지를 사용하는 패턴입니다."
}}
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=[prompt]
        )
        
        res_text = response.text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(res_text)
        
        pattern = parsed.get("pattern", "")
        if pattern.startswith("r'") and pattern.endswith("'"):
            pattern = pattern[2:-1] # r'' 제거
        elif pattern.startswith('r"') and pattern.endswith('"'):
            pattern = pattern[2:-1] # r"" 제거
            
        extracted = parsed.get("extracted_price", "")
        reasoning = parsed.get("reasoning", "")
        
        # 테스트 검증
        try:
            match = re.search(pattern, req.sample_text)
            if not match:
                return PriceLearnResponse(success=False, error="AI가 제안한 패턴으로 원문에서 단가를 찾을 수 없습니다. 다시 시도해주세요.")
        except Exception as e:
            return PriceLearnResponse(success=False, error=f"AI가 유효하지 않은 정규식을 생성했습니다: {e}")

        # 분석 완료 (여기서는 저장하지 않고, 프론트엔드가 모달에서 확인 후 명시적으로 /save_vendor_rule 을 호출하도록 할 수도 있으나, 
        # 원클릭 저장을 위해 바로 저장 후 응답을 넘깁니다)
        rules = load_vendor_rules()
        vendor_id = req.vendor_name.strip()
        rules[vendor_id] = {
            "pattern": pattern,
            "example_price": extracted,
            "reasoning": reasoning,
            "sample_text": req.sample_text[:100]
        }
        save_vendor_rules(rules)
        
        # 패턴 학습 기여 포인트 100 P 적립
        try:
            from backend.database import get_db
            get_db().add_points(100, f"업체 '{req.vendor_name}' 단가 표기 패턴 AI 학습 완료")
        except Exception as pe:
            print(f"[Reward System] Error adding points for price rule learn: {pe}")

        return PriceLearnResponse(
            success=True, 
            pattern=pattern, 
            extracted_price=extracted, 
            reasoning=reasoning
        )
        
    except Exception as e:
        return PriceLearnResponse(success=False, error=f"AI 분석 중 오류 발생: {str(e)}")
