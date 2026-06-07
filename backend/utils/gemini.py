# -*- coding: utf-8 -*-
"""Gemini 2.5 Flash REST 호출 공용 헬퍼 (D3).

기존에는 admin 배너 생성 / 상품 자동완성 / 크롤러 매핑 3곳이 동일한 HTTP 호출
코드를 각자 복붙해 두었다. 이를 단일 함수로 통합한다.

generate_text() 는 동기 함수다. async 컨텍스트(크롤러)에서는 이벤트 루프를
막지 않도록 loop.run_in_executor(...) 로 호출할 것.
"""
import json
import logging
import urllib.request
import urllib.error

from backend.config import settings

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
)


class GeminiError(Exception):
    """Gemini 호출 실패(키 미설정 / 통신 오류 / 빈 응답)."""


def generate_text(system_instruction: str, user_prompt: str, timeout: int = 20) -> str:
    """Gemini 를 호출해 응답 텍스트를 반환한다(마크다운 코드펜스 제거).

    실패 시 GeminiError 를 던진다. 호출측에서 적절한 HTTP 상태로 변환할 것.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise GeminiError("Gemini API Key가 설정되어 있지 않습니다 (.env 의 GEMINI_API_KEY).")

    url = f"{GEMINI_ENDPOINT}?key={api_key}"
    body = json.dumps({
        "contents": [
            {"parts": [{"text": f"System Instruction: {system_instruction}\nUser Prompt: {user_prompt}"}]}
        ]
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "ignore")
        logger.error(f"Gemini API HTTP error {e.code}: {err_body}")
        raise GeminiError(f"Gemini API HTTP {e.code}: {err_body}")
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        raise GeminiError(f"Gemini 통신 오류: {e}")

    candidates = data.get("candidates", [])
    if not candidates:
        raise GeminiError("Gemini 응답 후보가 비어 있습니다.")
    text = candidates[0]["content"]["parts"][0]["text"].strip()

    # 마크다운 코드펜스(```json ... ```) 제거
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
