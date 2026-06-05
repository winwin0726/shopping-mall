"""core.option_extractor
- 본문에서 사이즈 추출
- 이미지에서 컬러 추정(중앙 ROI)
"""

from __future__ import annotations

import os
import re
import colorsys
from collections import defaultdict
from typing import List, Tuple

from PIL import Image

def extract_sizes_from_body(raw_body: str):
    """
    본문에서 사이즈 후보를 최대한 안전하게 추출해서 리스트로 반환.
    ✅ 강화 포인트
    - <br> / <br/> / <br /> 가 섞여 있어도 줄 단위로 인식
    - '✔ 사이즈 :', '사이즈', 'SIZE', '尺码/碼數' 라인 + 다음줄 표까지 흡수
    - M~3XL, S/M/L/XL, 29-40, 35~46, 'M(100) L(105)' 형태까지 처리
    """
    if not raw_body:
        return []

    text = str(raw_body)

    # 1) HTML 줄바꿈을 실제 줄바꿈으로
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)

    # 2) 전각/탭 정리
    text = text.replace("　", " ").replace("\t", " ")

    # 3) 줄 리스트
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # 4) 사이즈 라인 후보 찾기 (첫 발견 + 바로 뒤의 관련 라인도 붙여서 분석)
    size_idx = -1
    for i, l in enumerate(lines):
        low = l.lower()
        if ("사이즈" in l) or ("size" in low) or ("尺码" in l) or ("碼數" in l) or ("码数" in l):
            size_idx = i
            break

    if size_idx == -1:
        return []

    # 5) 사이즈 블록 구성: "사이즈 라인" + (다음 6줄까지 중 사이즈 토큰이 있는 줄만 추가)
    block_lines = [lines[size_idx]]
    for j in range(size_idx + 1, min(size_idx + 7, len(lines))):
        nxt = lines[j]
        # 구분선/배송문구/코드 시작하면 종료
        if re.search(r"^[ㅡ―—–\-_=]{6,}$", nxt):
            break
        if any(k in nxt for k in ["특송", "개인통관", "배송", "CJ", "2박", "택배"]):
            break
        # 숫자/영문 사이즈 토큰이 조금이라도 있으면 포함
        if re.search(r"(XXS|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL|\b\d{2}\b|\d{2}\s*[~\-]\s*\d{2})", nxt, re.I):
            block_lines.append(nxt)

    size_text = " ".join(block_lines)

    # ':' 뒤 우선
    if ":" in size_text:
        size_part = size_text.split(":", 1)[1].strip()
    elif "：" in size_text:
        size_part = size_text.split("：", 1)[1].strip()
    else:
        size_part = size_text.strip()

    # 불필요 단어 제거
    size_part = (
        size_part.replace("추천", "")
        .replace("인치", "")
        .replace("inch", "")
        .replace("㎜", "")
        .replace("mm", "")
        .replace("주문제작", "")
    ).strip()

    # 구분자 통일
    for ch in [",", "／", "/", "|", "·", "ㆍ"]:
        size_part = size_part.replace(ch, " ")

    size_part = " ".join(size_part.split())

    # 1) 영문 사이즈 범위 (M ~ 3XL)
    order = ["XXS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL"]
    m = re.search(r"(XXS|XS|S|M|L|XL|2XL|3XL|4XL|5XL|XXL|XXXL)\s*[~\-]\s*(XXS|XS|S|M|L|XL|2XL|3XL|4XL|5XL|XXL|XXXL)", size_part, re.I)
    if m:
        a = m.group(1).upper()
        b = m.group(2).upper()
        a = a.replace("XXL", "2XL").replace("XXXL", "3XL")
        b = b.replace("XXL", "2XL").replace("XXXL", "3XL")
        if a in order and b in order:
            ia, ib = order.index(a), order.index(b)
            if ia <= ib:
                return order[ia:ib + 1]

    # 2) 숫자 범위 (35~46, 29-40)
    m2 = re.search(r"(\d{2})\s*[~\-]\s*(\d{2})", size_part)
    if m2:
        s = int(m2.group(1))
        e = int(m2.group(2))
        if 10 <= s <= 70 and 10 <= e <= 70 and s <= e:
            return [str(x) for x in range(s, e + 1)]

    # 3) 토큰 추출 (S M L XL / 29 30 31 ...)
    tokens = re.split(r"\s+", size_part)
    cleaned = []
    for t in tokens:
        t = t.strip().upper()
        if not t:
            continue

        # M(100) 형태 -> M
        t = re.sub(r"\(.*?\)", "", t)

        # 2XL 형태 보정
        t = t.replace("XXL", "2XL").replace("XXXL", "3XL")

        if re.fullmatch(r"(XXS|XS|S|M|L|XL|2XL|3XL|4XL|5XL)", t):
            cleaned.append(t)
        elif re.fullmatch(r"\d{2}", t):
            cleaned.append(t)

    # 중복 제거(순서 유지)
    seen = set()
    out = []
    for x in cleaned:
        if x not in seen:
            seen.add(x)
            out.append(x)

    return out




def detect_colors_from_images(image_paths, max_images=6):
    """
    ✅ 개선된 이미지 색상 추정
    - 흰 배경/회색 배경에 덜 끌리도록 '중앙 크롭 + 밝은배경 제거' 적용
    - 각 이미지별 대표색을 뽑아서 중복 제거 후 반환
    - 반환값은 옵션 엑셀용 한국어(레드/옐로우/블루 등)로 통일
    """
    if not image_paths:
        return []

    try:
        from PIL import Image
    except Exception:
        return []

    import colorsys

    def classify_rgb(r, g, b):
        # 배경 제거 후에도 흰/검은/회색 우선
        mx = max(r, g, b)
        mn = min(r, g, b)

        # 검정
        if mx < 55:
            return "블랙"

        # 화이트 (밝고 채도 낮음)
        if mn > 215 and (mx - mn) < 22:
            return "화이트"

        # 그레이 (채도 낮음)
        if (mx - mn) < 18 and 55 <= mx <= 215:
            return "그레이"

        # HSV로 색상 계열
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

        # 채도 낮으면 회색 계열
        if s < 0.14:
            return "그레이"

        hue = h * 360.0

        # 베이지/브라운(대략)
        if 20 <= hue < 55:
            if v >= 0.72:
                return "베이지"
            return "브라운"

        if (0 <= hue < 15) or (345 <= hue <= 360):
            return "레드"
        if 15 <= hue < 40:
            return "옐로우"
        if 40 <= hue < 85:
            return "그린"
        if 85 <= hue < 200:
            return "블루"
        if 200 <= hue < 255:
            return "네이비"
        if 255 <= hue < 310:
            return "퍼플"
        if 310 <= hue < 345:
            return "핑크"

        return "멀티"

    out = []
    for p in (image_paths[:max_images]):
        try:
            img = Image.open(p).convert("RGB")

            # 1) 중앙 크롭(가장자리에 배경이 많은 경우가 많음)
            w, h = img.size
            cx1, cy1 = int(w * 0.2), int(h * 0.2)
            cx2, cy2 = int(w * 0.8), int(h * 0.8)
            img = img.crop((cx1, cy1, cx2, cy2))

            # 2) 축소
            img = img.resize((90, 90))

            pixels = list(img.getdata())

            # 3) 밝은 배경/연한 회색 배경 제거
            filtered = []
            for (r, g, b) in pixels:
                mx = max(r, g, b)
                mn = min(r, g, b)
                # 거의 흰 배경
                if r > 245 and g > 245 and b > 245:
                    continue
                # 아주 밝은 회색 배경
                if mx > 230 and (mx - mn) < 12:
                    continue
                filtered.append((r, g, b))

            if not filtered:
                filtered = pixels

            # 4) 대표색: 평균보다 "중앙값(median)"이 배경에 덜 끌림
            rs = sorted([x[0] for x in filtered])
            gs = sorted([x[1] for x in filtered])
            bs = sorted([x[2] for x in filtered])
            mid = len(filtered) // 2
            r, g, b = rs[mid], gs[mid], bs[mid]

            name = classify_rgb(int(r), int(g), int(b))
            name = _normalize_option_color_kor(name)

            if name and name not in out:
                out.append(name)
        except Exception:
            continue

    return out


