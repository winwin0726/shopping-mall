"""공통 유틸 (문자/이모지/특수문자 필터)

- UI(Python/PyQt)와 무관하게 동작하는 순수 로직만 모았습니다.
"""

from __future__ import annotations

import os
import time
import json
import re

# PC/모바일 그누보드에서 비교적 안전하게 보이는 문자만 남기기 위한 "허용 특수문자" 목록
GNUBOARD_PC_SPECIALS = set("-_.:,/()[]{}#@&%+*=~^|\\<>")
GNUBOARD_MOBILE_SPECIALS = set("-_.:,/()[]{}#@&%+*=~^|\\<>")

# 한글 자모 호환 (ㄱㄴㄷ 등)을 안전한 문자로 치환 (원본 코드 유지)
JAMO_COMPAT_MAP = {
    "ㄱ": "g", "ㄲ": "gg", "ㄴ": "n", "ㄷ": "d", "ㄸ": "dd", "ㄹ": "r",
    "ㅁ": "m", "ㅂ": "b", "ㅃ": "bb", "ㅅ": "s", "ㅆ": "ss", "ㅇ": "ng",
    "ㅈ": "j", "ㅉ": "jj", "ㅊ": "ch", "ㅋ": "k", "ㅌ": "t", "ㅍ": "p", "ㅎ": "h",
}


def replace_emoji_to_basic(text: str) -> str:
    """이모지/특수기호를 최대한 안전한 문자로 치환 (원본 로직 그대로)."""
    if not text:
        return ""

    replacements = {
        "✅": "[체크] ", "✔": "[체크] ", "☑": "[체크] ",
        "📌": "[중요] ", "📍": "[위치] ", "🧾": "[영수증] ",
        "🎁": "[선물] ", "🚚": "[배송] ", "🚀": "[특송] ",
        "⭐": "*", "🌟": "*", "✨": "*", "🔥": "!", "💥": "!",
        "•": "-", "·": "-", "▶": ">", "→": "->", "⇒": "->",
        "※": "(주의)",
    }

    for k, v in replacements.items():
        text = text.replace(k, v)

    # 남아있는 자모 호환은 안전문자로 치환
    for jamo, rep in JAMO_COMPAT_MAP.items():
        text = text.replace(jamo, rep)

    # 보이지 않는 특수 공백 정리
    text = text.replace(" ", " ").replace("​", "")
    return text


def _filter_text_keep_allowed(text: str, allowed_specials: set) -> str:
    """한글/영문/숫자/기본 공백/허용특수문자만 남기고 제거."""
    if not text:
        return ""

    out = []
    for ch in text:
        if ch.isalnum() or ch.isspace():
            out.append(ch)
            continue
        # 한글 범위
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            out.append(ch)
            continue
        if ch in allowed_specials:
            out.append(ch)
            continue
        # 그 외는 제거
    return "".join(out)


def make_int_safe_sort_orders(count: int, counter_path: str):
    """
    INT 범위에서 '작을수록 최신' + 중복 방지(재실행 포함) 정렬순서 리스트 생성

    ✅ 중요한 포인트
    - 일부 환경에서 정렬순서에 음수(-)가 들어가면 업로드 과정에서 '-'가 누락되는 케이스가 있어
      **음수는 쓰지 않고**, INT 범위 내 '양수'로만 생성합니다.

    로직
    - base = 2147483647 - 현재초(time.time())
      → 시간이 지날수록 base가 작아짐(= 작을수록 최신)
    - counter(누적값) + i 로 중복 방지
    """
    MAX_INT = 2147483647
    base = MAX_INT - int(time.time())

    counter = 0
    try:
        if os.path.exists(counter_path):
            with open(counter_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                counter = int(data.get("counter", 0))
    except Exception:
        counter = 0

    orders = []
    for i in range(int(count) if count else 0):
        v = base - (counter + i)
        if v < 1:
            v = 1
        orders.append(int(v))

    try:
        os.makedirs(os.path.dirname(counter_path), exist_ok=True)
        with open(counter_path, "w", encoding="utf-8") as f:
            json.dump({"counter": counter + len(orders)}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return orders
