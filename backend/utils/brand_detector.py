# -*- coding: utf-8 -*-
import re
import unicodedata
from sqlalchemy.orm import Session
from backend.models import Brand
from typing import Optional

def _norm_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).lower()
    # 제로폭 문자 제거 및 알파벳/한글/숫자만 보존
    s = re.sub(r"[\u200B-\u200F\u2060\uFEFF]", "", s)
    s = re.sub(r"[^0-9a-z가-힣]+", "", s)
    return s

def get_category_group_key(category_name: str) -> Optional[str]:
    if not category_name:
        return None
    cat_lower = category_name.lower()
    
    # 1) 가방
    if any(k in cat_lower for k in ["가방", "백", "bags", "backpack", "crossbag", "totebag"]):
        return "bag"
    # 2) 지갑
    if any(k in cat_lower for k in ["지갑", "wallets", "wallet"]):
        return "wallet"
    # 3) 신발
    if any(k in cat_lower for k in ["신발", "슈즈", "스니커즈", "shoes"]):
        return "shoes"
    # 4) 시계
    if any(k in cat_lower for k in ["시계", "watches", "watch"]):
        return "watch"
    # 5) 의류
    if any(k in cat_lower for k in ["의류", "상의", "하의", "아우터", "패션", "clothing"]):
        return "clothing"
    # 6) 악세사리
    if any(k in cat_lower for k in ["악세사리", "악세사리", "주얼리", "accessories", "accessory"]):
        return "accessory"
        
    return None

def detect_brand_id(db: Session, title: str, description: str = "", category_name: str = "") -> Optional[int]:
    """
    상품의 제목과 상세 설명을 분석하여 등록된 브랜드 사전에 매칭되는 최적의 Brand ID를 자동 반환합니다.
    카테고리 정보가 제공될 시, 해당 품목군(또는 all) 브랜드만으로 범위를 좁혀 오탐을 차단합니다.
    """
    text = (title or "") + " " + (description or "")
    text_norm = _norm_text(text)
    if not text_norm:
        return None

    # 카테고리 기반 1차 필터링
    group_key = get_category_group_key(category_name)
    query = db.query(Brand).filter(Brand.is_active == True)
    if group_key:
        query = query.filter(
            (Brand.category_group == 'all') | 
            (Brand.category_group.like(f"%{group_key}%"))
        )
    brands = query.all()

    best_match = None
    best_len = 0

    for brand in brands:
        # 1) 한글 브랜드명 매칭 검증 (예: 루이비통, 구찌)
        b_name_norm = _norm_text(brand.name)
        if b_name_norm and b_name_norm in text_norm:
            if len(b_name_norm) > best_len:
                best_len = len(b_name_norm)
                best_match = brand.id

        # 2) 영문 브랜드명 매칭 검증 (예: Louis Vuitton, Gucci)
        b_eng_norm = _norm_text(brand.eng_name)
        if b_eng_norm:
            # 영문 약어(예: LV, D&G 등 3글자 이하)는 앞뒤 단어 경계를 정밀 대조하여 오탐 방지
            if len(b_eng_norm) <= 3:
                pattern = rf"\b{re.escape(brand.eng_name.lower())}\b"
                if re.search(pattern, text.lower()):
                    if len(b_eng_norm) > best_len:
                        best_len = len(b_eng_norm)
                        best_match = brand.id
            else:
                if b_eng_norm in text_norm:
                    if len(b_eng_norm) > best_len:
                        best_len = len(b_eng_norm)
                        best_match = brand.id

    return best_match
