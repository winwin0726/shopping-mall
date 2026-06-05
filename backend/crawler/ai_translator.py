import json
import httpx
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

class AITranslatorPipeline:
    def __init__(self):
        # .env 는 pydantic settings 로 로드된다 (os.getenv 는 uvicorn 환경에서 .env 를 못 읽음)
        self.api_key = settings.GEMINI_API_KEY or ""
        self.model_endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        )

    async def translate_product_info(self, cn_title: str, cn_desc: str) -> dict:
        """
        중국어 상품 정보를 한국어 쇼핑몰 양식으로 번역한다.
        키가 없거나 실패하면 원본 제목을 활용한 폴백을 반환한다.
        """
        fallback = {
            "kr_name": (f"[수집] {cn_title}".strip())[:50],
            "kr_description": cn_desc or "",
        }

        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. Returning passthrough translation.")
            return fallback

        prompt = (
            "당신은 한국의 트렌디하고 세련된 패션 쇼핑몰 MD입니다. "
            "다음 중국어 상품 정보를 자연스럽고 매력적인 한국어로 번역하세요. "
            "반드시 아래 스키마의 JSON 객체만 출력하세요 (마크다운/설명 금지):\n"
            '{"kr_name": "한국어 상품명(최대 50자)", "kr_description": "한국어 상품 설명"}\n\n'
            f"상품명: {cn_title}\n설명: {cn_desc}"
        )
        params = {"key": self.api_key}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.model_endpoint, params=params, json=payload, timeout=15.0
                )
                response.raise_for_status()
                data = response.json()

                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                # 마크다운 코드펜스 제거
                if text.startswith("```"):
                    text = "\n".join(
                        ln for ln in text.splitlines() if not ln.strip().startswith("```")
                    ).strip()

                parsed = json.loads(text)
                kr_name = (parsed.get("kr_name") or fallback["kr_name"]).strip()[:50]
                kr_desc = parsed.get("kr_description") or cn_desc or ""
                logger.info("Translation successful.")
                return {"kr_name": kr_name, "kr_description": kr_desc}

        except Exception as e:
            logger.error(f"AI Translation failed: {e}")
            return fallback
