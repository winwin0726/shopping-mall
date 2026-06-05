"""가격 관련 로직 (도매/도착단가 파싱, 판매가 계산)

기존 winwin58의 로직을 기본으로 하되,
- 카테고리별 배수(마진)를 config로 바꿀 수 있게 확장했습니다.
"""

from __future__ import annotations

import json
import os
import re

# 기본 배수 (기존 값 그대로)
DEFAULT_MULTIPLIERS = {
    "남성의류": 1.4,
    "여성의류": 1.4,
    "가방": 1.4,
    "신발": 1.4,
    "지갑": 1.4,
    "시계": 1.25,
    "기타": 1.25,
    "악세사리": 1.6,
    "default": 1.4,
}


def _norm_cat(cat: str) -> str:
    return re.sub(r"\s+", "", (cat or ""))


def load_multipliers(config_path: str | None = None) -> dict:
    """pricing.json이 있으면 그 값으로 덮어쓰기."""
    if not config_path:
        # core/pricing.json 또는 실행폴더 pricing.json
        here = os.path.dirname(__file__)
        cand = [os.path.join(here, 'pricing.json'), os.path.join(os.getcwd(), 'pricing.json')]
        for c in cand:
            if os.path.exists(c):
                config_path = c
                break
    if not config_path or not os.path.exists(config_path):
        return dict(DEFAULT_MULTIPLIERS)

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        out = dict(DEFAULT_MULTIPLIERS)
        out.update({str(k): float(v) for k,v in data.items()})
        return out
    except Exception:
        return dict(DEFAULT_MULTIPLIERS)


def compute_sale_price(ddg_value: float, category: str = "default", multipliers: dict | None = None) -> int:
    """ddg_value(예: 13.2 = 13.2만원) -> 판매가(원)"""
    multipliers = multipliers or load_multipliers()
    cat_key = _norm_cat(category)

    # 기존과 동일하게 '만원 단위' * 10000 * 배수
    mult = None
    for k,v in multipliers.items():
        if _norm_cat(k) == cat_key:
            mult = float(v)
            break
    if mult is None:
        mult = float(multipliers.get('default', 1.4))

    price = int(float(ddg_value) * 10000 * mult)
    # 기존 로직은 1000원 단위 절삭
    price = (price // 1000) * 1000
    return price

def parse_ddg_value(text):
    pattern = r"ㄷㄱ\s*([0-9]+(\.[0-9]+)?)"
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return "0"




def compute_sale_price_legacy(price_input, category):
    try:
        value = float(price_input)
    except Exception:
        value = 0

    # 카테고리 문자열에 들어간 모든 공백 제거(중간에 삽입된 공백까지)
    category_clean = re.sub(r"\s+", "", str(category))

    if category_clean in ["남성의류", "여성의류", "가방", "지갑", "신발"]:
        sale = int((value * 14000) // 1000 * 1000)
    elif category_clean == "시계":
        sale = int((value * 12500) // 1000 * 1000)
    elif category_clean == "ACC":
        sale = int((value * 16000) // 1000 * 1000)
    elif category_clean == "국내배송":
        sale = int(((value * 10000 * 1.4)) // 1000 * 1000)
    else:
        sale = 0

    return sale


########################################
# 8) HTML 수정 및 이미지 태그 추가 함수 (동일)
########################################


