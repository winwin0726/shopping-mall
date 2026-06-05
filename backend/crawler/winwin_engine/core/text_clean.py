"""본문 필터링 로직 (UI와 분리)"""

from __future__ import annotations

import re

def remove_ddg_price_marker(html_text):
    pattern_ddg = r"ㄷㄱ\s*\d+(\.\d+)?"
    cleaned = re.sub(pattern_ddg, "", html_text)
    pattern_sale = r"=\s*\d+(\.\d+)?\s*판매가기재"
    cleaned = re.sub(pattern_sale, "", cleaned)
    return cleaned

def remove_fullset_freegift_lines(raw_text: str) -> str:
    """
    ✅ 엑셀 변환용 본문 정리(강화):
    - '풀세트/풀구성/매장풀박스' 헤더 제거
    - '사은품/증정/赠品' 문구 제거
    - 헤더 없이도 남는 '구성품 나열' 라인 제거
      예) ': 쇼핑백 + 고급 고야드카드지갑(5만상당)<br>'
    """
    if not raw_text:
        return ""

    # 판단용: HTML 태그 제거한 문자열
    def _strip_html(s: str) -> str:
        return re.sub(r"<[^>]+>", "", s)

    lines = raw_text.splitlines()

    dash_pattern = re.compile(r'^[\u2500-\u2BEF\u2010-\u201F\-―ㅡ]+$')

    # 헤더 키워드(구성/풀세트 계열)
    start_keywords = [
        "풀세트", "풀 세트", "풀구성", "풀 구성", "풀박스", "풀 박스",
        "매장풀박스", "매장 풀박스", "매장풀세트", "매장 풀세트",
        "매장풀구성", "매장 풀구성", "매장풀박스 구성", "매장 풀박스 구성",
        "패키지 구성", "풀패키지", "풀 패키지",
        "包装", "包裝", "全套包装", "原厂包装", "原廠包裝"
    ]

    # 사은품/증정 키워드
    gift_keywords = ["사은품", "증정", "서비스", "赠品", "礼品", "贈品"]

    # 구성품/패키지 아이템 키워드(여기 걸리면 거의 구성 줄)
    pack_item_keywords = [
        "쇼핑백", "영수증", "보증서", "갤런티", "카드", "케이스", "보관함",
        "패딩보관함", "반지갑", "카드지갑", "고야드", "스카프", "더스트", "박스",
        "설명서", "택", "태그", "옷걸이", "항공박스", "파우치"
    ]

    # 구성품 나열 패턴: ':', '+', '/', ',' 등이 있고 아이템 키워드가 같이 있으면 제거
    def _is_pack_list_line(s_nohtml: str) -> bool:
        s2 = s_nohtml.strip()

        # 앞에 ':'로 시작하거나 중간에 ':'가 있고, + / , 형태로 나열되는 경우
        has_colon_style = s2.startswith(":") or (":" in s2 and len(s2.split(":")[0]) <= 3)

        has_list_sep = ("+" in s2) or ("/" in s2) or ("," in s2) or ("ㆍ" in s2) or ("·" in s2)

        has_pack_word = any(k in s2 for k in pack_item_keywords)

        # 금액표현(예: 5만상당/50,000/5만원) + 구성품 키워드가 함께 있으면 거의 사은품 라인
        has_money = bool(re.search(r"(\d+\s*만\s*상당|\d+\s*만원|\d{1,3}(,\d{3})+|\d+\s*원)", s2))

        # 구성품 단어 + (괄호) 설명도 흔함
        has_paren = "(" in s2 and ")" in s2

        # 조건 조합
        if has_pack_word and (has_colon_style or has_list_sep or has_money or has_paren):
            return True

        # pack 키워드가 강하게 들어간 단독 라인도 제거
        if has_pack_word and len(s2) <= 60 and ("구성" in s2 or "포함" in s2):
            return True

        return False

    out = []
    in_pack_block = False

    for line in lines:
        s = line.strip()
        s_nohtml = _strip_html(s).strip()

        if not s_nohtml:
            if in_pack_block:
                in_pack_block = False
                continue
            out.append(line)
            continue

        # 구분선은 유지하되, 구성 블록은 종료
        if dash_pattern.match(s_nohtml):
            in_pack_block = False
            out.append(line)
            continue

        # 사은품 키워드 포함 라인은 즉시 제거(HTML 제거 후 판정)
        if any(k in s_nohtml for k in gift_keywords):
            continue

        # 풀세트/구성 헤더 라인은 블록 시작으로 보고 제거
        if any(k in s_nohtml for k in start_keywords):
            in_pack_block = True
            continue

        # ✅ 헤더 없이도 남는 "구성품 나열" 라인 제거
        if _is_pack_list_line(s_nohtml):
            continue

        # 구성 블록 안에서는 구성품 나열로 보이는 줄은 제거
        if in_pack_block:
            if any(k in s_nohtml for k in pack_item_keywords):
                continue
            # 나열 구분자가 있으면 구성품으로 판단하고 제거
            if ("+" in s_nohtml) or ("/" in s_nohtml) or ("," in s_nohtml):
                continue
            # 다음 섹션(✔/✅/📏) 나오면 블록 종료하고 그 줄은 살림
            if s_nohtml.startswith(("✔", "✅", "📏")):
                in_pack_block = False
                out.append(line)
                continue
            # 그 외는 구성 블록이면 제거
            continue

        out.append(line)

    return "\n".join(out)

