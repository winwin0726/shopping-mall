# -*- coding: utf-8 -*-
"""
smart_extract_price — 웨이상 도매단가(위안) 다중전략 추출기 (결정론 + AI폴백 인터페이스)
실데이터(crawled_products_backup 664건, original_chinese) 패턴 카탈로그 기반.
크롤러 backend/platforms/weishang/crawler.py 의 _extract_price 를 대체/호출 가능.
"""
import re
from collections import Counter

# ── 소매가/함정 키워드(이 라벨이 붙은 숫자는 도매가가 아니다) ───────────────
# 측정근거: 官网售价(24) 网售价(24) 得物售价(4) 原价(120occ) 售价(124occ) — 전부 소매/참고가
RETAIL_TRAP = (
    "官网售价", "官网价", "网售价", "专柜售价", "专柜价", "得物售价",
    "零售价", "吊牌价", "商场价", "市场价", "原价", "定价", "售价",
)
# 프로모션/조건 함정(구매조건 금액·사은품 가치 등): 购满3000, 价值500 등
PROMO_TRAP = ("购满", "满减", "满赠", "免费赠送", "价值", "赠送", "起送", "包邮换")
# 사이즈/치수 키워드 — '약한 전략'에서만 veto 에 사용(강마커는 무시).
# 주의: 码数/参考 등은 가격과 자주 붙어 오탐 → 제외. 실측 치수단어만.
SIZE_KW = ("cm", "mm", "kg", "size", "胸围", "衣长", "裤长", "肩宽", "袖长", "腰围",
           "后中长", "脚围", "脚口", "上胸围", "袖口", "坐围", "臀围", "下摆", "裙长",
           "净重", "重量", "厚度", "底长")

NUM = r"(\d{1,5})"

# ── 마커 전략(우선순위 idx 작을수록 우선). (정규식, 신뢰도, 설명, skip_size_veto) ──
# 측정근거 우선순위:
#   가방벤더는 '一口价¥/特惠¥/限时折扣¥/特价🉐'(구매가=GT) 가 진짜이고
#   '统批💰'(공급 배치가)는 더 높은 참고가 → 후순위 + 原价동반시 함정.
OFFER_WORDS = r"(?:一口价|特价|特惠|福利价|秒杀|限时折扣|时折扣|折扣|优惠|活动价)"
MARKER_STRATEGIES = [
    # 1) 할인/구매가(오퍼) 마커 + 통화기호/🉐  ← 최우선(가방·의류 공통 GT)
    (re.compile(OFFER_WORDS + r"\s*[¥￥]\s*" + NUM), 0.95, "오퍼가(一口价/특가/折扣 ¥)", True),
    (re.compile(OFFER_WORDS + r"\s*🉐\s*" + NUM), 0.94, "오퍼가🉐(福利价/特价/折扣🉐)", True),
    (re.compile(r"🉐\s*" + NUM), 0.86, "🉐 단독마커", True),
    # 2) 통화기호 ¥/元 + 숫자 (소매라벨/万 가드는 별도)
    (re.compile(r"[¥￥]\s*" + NUM + r"(?!\s*[\.\d]*\s*万)"), 0.90, "¥ 통화기호", True),
    (re.compile(r"(\d{1,5})\s*元(?!\s*[\.\d]*\s*万)"), 0.88, "元 통화단어", True),
    # 3) 이모지 도매마커
    (re.compile(r"💰\s*" + NUM), 0.88, "💰 이모지마커", True),
    (re.compile(r"🅿️?\s*" + NUM), 0.90, "🅿 이모지마커", True),
    # 4) 단독 P/p + 숫자 (웨이상 관용 도매표기) — 영단어 일부 제외
    (re.compile(r"(?<![A-Za-z])[Pp]\s*[:：]?\s*" + NUM + r"(?![A-Za-z])"), 0.87, "P/p 도매표기(콜론허용)", False),
    # 맨앞 가격(price-first 벤더, 예: 200💕【GUCCI】, 220▫️L): 본문 첫머리 2~4자리(연도 19/20xx 제외)
    #   + 장식 구분자(이모지/기하도형 ▫▪◆☆/딩벳/【) 선행. 구분자 화이트리스트 무한확장 대신 유니코드 기호블록으로 일반화.
    (re.compile(r"^\s*[¥￥]?\s*(?!19\d\d|20\d\d)(\d{2,4})\s*(?=[\U0001F000-\U0001FAFF☀-➿■-◿⬀-⯿]|【)"), 0.74, "맨앞 가격(선두 숫자)", False),
    # 5) 统批/批发(배치 도매가) — 후순위, 原价 동반시 가드에서 탈락
    (re.compile(r"统批\s*💰?\s*" + NUM), 0.72, "统批 배치도매가", True),
    (re.compile(r"批发价?\s*[:：]?\s*" + NUM), 0.80, "批发(도매) 마커", True),
    # 6) 价(일반 가격어) — 소매라벨 가드 후, 약마커
    (re.compile(r"(?<![售原网柜物场])价\s*[:：]\s*" + NUM), 0.62, "价: 일반가격어", False),
]

# 긴품번 끝3자리: 】 뒤 7자리(4코드+3가) → 끝3자리가 단가 (실측 89/89 last-3, 코드부 항상 9 시작)
# 세트상품은 】 와 숫자 사이에 짧은 라벨(外套/长裤/上衣 등 0~4한자)이 끼므로 허용.
# 예: 【...】外套9760290 长裤9610250  → 첫 9760290 의 끝3자리 290 채택.
LONGNUM = re.compile(r"】[^\d\n】]{0,4}?(9\d{3})(\d{3})(?!\d)")
# 】 없이 본문에 박힌 7자리 품번(9로 시작) — 끝3자리=단가 (심천9 등 price-in-code 벤더)
LONGNUM7 = re.compile(r"(?<!\d)(9\d{3})(\d{3})(?!\d)")
# 마커 없는 본문 단독숫자(보수적): 2~4자리, 앞뒤 공백/문장부호
STANDALONE = re.compile(r"(?:^|[\s\n（(【\[])(\d{2,4})(?:$|[\s\n）)】\]])")
# 万(만) 소매가 라인 — 통째 마스킹 (예: 【官网售价：11200】 ¥ 1 .12 万)
WAN_LINE = re.compile(r"[【\[┃|][^】\]┃|\n]{0,30}?(?:售价|官网|价)[^】\]┃|\n]{0,30}?[】\]┃|]\s*[¥￥]?\s*[\d\. ]+\s*万?")


def _ctx(text, s, e, w=12):
    return text[max(0, s - w):min(len(text), e + w)]


def _is_size_ctx(text, s, e):
    c = _ctx(text, s, e, 9).lower()
    return any(k.lower() in c for k in SIZE_KW)


def _near_retail_trap(text, marker_start):
    """숫자 앞(같은 줄 직전 ~18자) 또는 직후 4자에 소매라벨이 있으면 함정."""
    line_start = text.rfind("\n", 0, marker_start) + 1
    seg = text[max(line_start, marker_start - 18):marker_start]
    if any(t in seg for t in RETAIL_TRAP):
        return True
    return False


def _trailing_retail(text, num_end):
    """숫자 직후 ~5자에 原价/售价 등이 '괄호 없이' 붙으면(예: 统批💰1000原价) 참고가로 간주.
    단, '470（原价1160）'처럼 괄호 안의 原价는 뒤 숫자(1160)의 소매가라 앞 숫자(470)와 무관 → 탈락 안 시킴."""
    seg = text[num_end:num_end + 5]
    if seg[:1] in ("（", "(", "【", "[", "〈", "《", "〔", "「"):
        return False                                   # 괄호 시작 = 뒤 숫자의 소매가
    return any(t in seg for t in ("原价", "售价", "官网", "专柜", "吊牌"))


def _near_promo_trap(text, s, e):
    return any(t in _ctx(text, s, e, 16) for t in PROMO_TRAP)


def smart_extract_price(text, ai_rules=None):
    """
    웨이상 원문에서 도매단가(위안)를 추출.
    반환: (price:str, confidence:float, reason:str)
      price: 숫자문자열 | "-"(미감지) | "0"(가격없음 명시)
      confidence: 0.0~1.0  (≤0.6 이면 AI폴백 권장 구간)
      reason: 근거(사람이 읽음 + 폴백판단용)
    ai_rules(dict, 선택): has_price, price_regex, price_decoder, price_offset,
                          vendor_name, vendor_category
    """
    ai_rules = ai_rules or {}
    if ai_rules.get("has_price") is False:
        return ("0", 1.0, "ai_rules.has_price=False")
    if not text or not text.strip():
        return ("-", 0.0, "빈 텍스트")

    v_name = str(ai_rules.get("vendor_name", "") or "")
    v_cat = str(ai_rules.get("vendor_category", "") or "")
    decoder = ai_rules.get("price_decoder", "")
    offset = int(ai_rules.get("price_offset", 0) or 0)
    custom_regex = ai_rules.get("price_regex", "") or ""

    hv = any(x in v_cat for x in ("가방", "지갑", "시계", "신발", "아우터", "코트", "패딩", "명품"))
    lo = 10 if (v_name and "돼지" in v_name) else (
        15 if any(x in v_cat for x in ("악세", "잡화", "반지", "목걸이", "귀걸이")) else 20)
    hi = 50000 if hv else 5000

    def _decode(n):
        s = str(n)
        if decoder == "panda" or (v_name and "팬더" in v_name):
            try: return int(s.zfill(4)[::-1])
            except: return n
        if decoder == "sandwich" and len(s) >= 3:
            try: return int(s[1:-1])
            except: return n
        return n

    def _finalize(val, conf, reason):
        val = _decode(val)
        if offset:
            val += offset
            reason += f" (offset {offset:+d})"
        if not (lo <= val <= hi):
            return None
        return (str(val), round(conf, 2), reason)

    # ── 0) 업체 전용 커스텀 정규식(AI 학습) — 최우선, 고신뢰 ──────────────────
    if custom_regex:
        try:
            m = re.search(custom_regex, text, re.IGNORECASE)
            if m:
                g = m.group(1) if m.groups() else m.group(0)
                pn = re.findall(r"\d+", g)
                if pn:
                    r = _finalize(int(pn[0]), 0.95, "업체 커스텀 정규식")
                    if r:
                        return r
        except re.error:
            pass

    # ── 万 단위 소매가 라인 마스킹 ────────────────────────────────────────
    masked = WAN_LINE.sub(lambda m: " " * len(m.group(0)), text)

    # ── 1) 마커 후보 수집(우선순위) ──────────────────────────────────────
    candidates = []  # (prio, conf, val, reason, pos)
    for prio, (rx, conf, desc, skip_size) in enumerate(MARKER_STRATEGIES):
        for m in rx.finditer(masked):
            num = m.group(1)
            ns, ne = m.start(1), m.end(1)
            if (not skip_size) and _is_size_ctx(masked, ns, ne):
                continue
            if _near_retail_trap(masked, m.start()):
                continue
            if _near_promo_trap(masked, ns, ne):
                continue
            if _trailing_retail(masked, ne):  # 统批1000原价 등
                continue
            try:
                v = int(num)
            except ValueError:
                continue
            if not (lo <= v <= hi):
                continue
            candidates.append((prio, conf, v, desc, ns))

    if candidates:
        # 최우선 prio → 같은 prio면 앞쪽 위치
        candidates.sort(key=lambda c: (c[0], c[4]))
        best = candidates[0]
        # 같은 prio 군 안에서의 값 분포로 신뢰 보정
        top_prio = best[0]
        same_prio_vals = [c[2] for c in candidates if c[0] == top_prio]
        all_vals = [c[2] for c in candidates]
        conf = best[1]
        if same_prio_vals.count(best[2]) >= 2:
            conf = min(0.99, conf + 0.04)            # 시작·끝 동일가 반복 → ↑
        # 서로 다른 '상위2' 우선순위 값이 충돌하면 ↓ (AI폴백 후보)
        prios_present = sorted(set(c[0] for c in candidates))
        if len(prios_present) >= 2:
            second = [c for c in candidates if c[0] == prios_present[1]]
            if second and second[0][2] != best[2]:
                conf = max(0.55, conf - 0.10)
        distinct = len(set(all_vals))
        tag = f"{same_prio_vals.count(best[2])}회 일치" if same_prio_vals.count(best[2]) >= 2 else (
            f"후보 {distinct}종" if distinct >= 2 else "단일후보")
        r = _finalize(best[2], conf, f"{best[3]} | {tag}")
        if r:
            return r

    # ── 2) 긴품번 끝3자리 폴백(마커 없을 때만) — FIRST occurrence=헤더상품 ───
    lm = LONGNUM.search(masked)
    if lm:
        v = int(lm.group(2))
        all_ln = [int(x.group(2)) for x in LONGNUM.finditer(masked)]
        conf = 0.86 if len(set(all_ln)) == 1 else 0.80
        r = _finalize(v, conf, f"긴품번(】+9xxxxxx) 끝3자리={v}"
                      + (f" | 멀티상품 {len(all_ln)}개중 헤더" if len(all_ln) > 1 else ""))
        if r:
            return r

    # ── 2.5) 】 없이 본문에 박힌 7자리 품번(9로 시작) → 끝3자리 단가 (심천9 등). 마커·】 폴백 후. ──
    m7 = LONGNUM7.search(masked)
    if m7:
        v = int(m7.group(2))
        all7 = [int(x.group(2)) for x in LONGNUM7.finditer(masked)]
        conf = 0.80 if len(set(all7)) == 1 else 0.74
        r = _finalize(v, conf, f"7자리품번(9xxxxxx) 끝3자리={v}"
                      + (f" | {len(all7)}개중 첫번째" if len(all7) > 1 else ""))
        if r:
            return r

    # ── 3) 단독숫자(최보수, 저신뢰 → AI폴백 권장) ─────────────────────────
    sa = []
    for m in STANDALONE.finditer(masked):
        ns, ne = m.start(1), m.end(1)
        if _is_size_ctx(masked, ns, ne):
            continue
        if _near_retail_trap(masked, ns) or _near_promo_trap(masked, ns, ne):
            continue
        v = int(m.group(1))
        if lo <= v <= hi:
            sa.append(v)
    if sa:
        v, n = Counter(sa).most_common(1)[0]
        conf = 0.45 if len(set(sa)) == 1 else 0.30
        return (str(v), conf, f"단독숫자 보수폴백={v}(후보 {len(set(sa))}종) → AI확인 권장")

    return ("-", 0.0, "단가 마커/패턴 미발견")
