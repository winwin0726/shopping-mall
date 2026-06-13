import re
import math
import datetime
import os
import json

def interpolate_smooth_value(x, x1, x2, y1, y2):
    if x <= x1:
        return y1
    if x >= x2:
        return y2
    return y1 + (x - x1) * (y2 - y1) / (x2 - x1)

VENDOR_RULES_CACHE = None
VENDOR_RULES_MTIME = 0

def get_vendor_rules():
    global VENDOR_RULES_CACHE, VENDOR_RULES_MTIME
    path = os.path.join(os.path.dirname(__file__), 'vendor_rules.json')
    if not os.path.exists(path):
        return {}

    mtime = os.path.getmtime(path)
    if VENDOR_RULES_CACHE is None or mtime > VENDOR_RULES_MTIME:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                VENDOR_RULES_CACHE = json.load(f)
            VENDOR_RULES_MTIME = mtime
        except Exception:
            VENDOR_RULES_CACHE = {}
    return VENDOR_RULES_CACHE

# 한국어 초성을 영문 약자로 변환 (업체코드 작성 규칙)
CHOSUNG_MAP = {
    "ㄱ": "G", "ㄲ": "GG", "ㄴ": "N", "ㄷ": "D", "ㄸ": "DD", "ㄹ": "L", "ㅁ": "M",
    "ㅂ": "B", "ㅃ": "BB", "ㅅ": "S", "ㅆ": "SS", "ㅇ": "", "ㅈ": "J", "ㅉ": "JJ",
    "ㅊ": "CH", "ㅋ": "K", "ㅌ": "T", "ㅍ": "P", "ㅎ": "H"
}

# 전역 명품 브랜드 약어 매핑 사전
BRAND_ALIASES = {
    "sch": "Schiaparelli",
    "schiapa": "Schiaparelli",
    "schiaparelli": "Schiaparelli",
    "lv": "Louis Vuitton",
    "louisvuitton": "Louis Vuitton",
    "cc": "Chanel",
    "c사": "Chanel",
    "chanel": "Chanel",
    "h": "Hermes",
    "h사": "Hermes",
    "hermes": "Hermes",
    "d": "Dior",
    "d사": "Dior",
    "dior": "Dior",
    "p": "Prada",
    "p사": "Prada",
    "prada": "Prada",
    "b": "Balenciaga",
    "b사": "Balenciaga",
    "balenciaga": "Balenciaga",
    "g": "Gucci",
    "g사": "Gucci",
    "gucci": "Gucci",
    "로에ㅂ": "Loewe",
    "loewe": "Loewe",
    "miu": "Miu Miu",
    "miumiu": "Miu Miu",
    "m사": "Miu Miu",
    "celine": "Celine",
    "셀린ㄴ": "Celine",
    "bottega": "Bottega Veneta",
    "bv": "Bottega Veneta",
    "fendi": "Fendi",
    "펜ㄷ": "Fendi",
    "ysl": "Saint Laurent",
    "입생": "Saint Laurent",
    "생로랑": "Saint Laurent",
    "moncler": "Moncler",
    "몽클": "Moncler",
    "몽ㅋ": "Moncler",
    "thom": "Thom Browne",
    "tb": "Thom Browne",
    "톰브": "Thom Browne"
}

def extract_brand_from_text(text: str, ai_detected: str = "") -> str:
    """원문 텍스트와 AI 탐지 브랜드를 비교하여 가장 정확한 정식 브랜드명을 반환"""
    import re
    # 1. AI가 찾아낸 브랜드가 사전에 있으면 정식 명칭으로 변환
    if ai_detected:
        ai_lower = ai_detected.lower().strip()
        for key, full_name in BRAND_ALIASES.items():
            if ai_lower == key or full_name.lower() in ai_lower:
                return full_name

    # 2. 원문 텍스트 첫 30자 이내에서 약어 단독 등장 검사
    if text:
        front_text = text[:50].lower()
        # [^\w가-힣]sch[^\w가-힣] 처럼 단어 경계로 검색
        for key, full_name in BRAND_ALIASES.items():
            # 영어 알파벳 약어인 경우 단어 경계()로 엄격히 검사
            if re.search(r'\b' + re.escape(key) + r'\b', front_text):
                return full_name
            # 한글 섞인 약어(c사, 몽ㅋ 등)는 단순 포함 여부도 검사
            if "사" in key or "ㅋ" in key or "ㄴ" in key or "ㅂ" in key:
                if key in front_text:
                    return full_name

    # 3. 못 찾았으면 AI가 준 값 그대로 반환
    return ai_detected.strip()


def get_chosung(text):
    CHOSUNG_LIST = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
    res = ""
    for char in text:
        if "가" <= char <= "힣":
            ch1 = (ord(char) - ord("가")) // 588
            res += CHOSUNG_LIST[ch1]
        else:
            res += char
    return res

def encode_secret_cost(cost):
    """원가(cost)를 Base36 + XOR 연산으로 난독화하여 3자리 문자열로 반환"""
    salt = 97  # XOR salt
    num = cost ^ salt
    if num == 0: return "000"
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    res = ""
    while num > 0:
        res = chars[num % 36] + res
        num //= 36
    return res.zfill(3)

def determine_item_category(category_name, product_title, raw_text):
    """다국어(한국어+중국어+영문) 복합 키워드로 품목 카테고리 자동 판별.
    점수 기반 가중치를 사용하여 반바지/셋업 키워드가 본문에 섞여 있는 일반 티셔츠 오분류를 예방합니다."""
    text_kr = f"{category_name} {product_title}".lower()
    text_all = f"{category_name} {product_title} {raw_text}".lower()

    # 각 카테고리별 매칭 점수
    scores = {
        'B': 0,      # 가방 (Bag)
        'L': 0,      # 지갑 (Wallet)
        'S': 0,      # 신발/부츠 (Shoes)
        'A': 0,      # 악세사리 (Accessory)
        'P': 0,      # 바지 (Pants)
        'T_shirt': 0,# 상의/티셔츠 (T-shirt/Top -> 'T')
        'Outer': 0,  # 아우터 (Outer -> 'M')
    }

    # 1. 가방
    bag_kr = ["가방", "클러치", "토트백", "숄더백", "크로스백", "핸드백", "체인백", "플랩백", "호보백", "버킷백", "미니백"]
    if any(k in text_kr for k in bag_kr):
        scores['B'] += 10
    if "백" in text_kr and not any(x in text_kr for x in ["백화", "오백", "이백", "삼백", "사백", "육백", "칠백", "팔백", "구백"]):
        scores['B'] += 8
    bag_cn = ["包包", "手提包", "单肩包", "斜挎包", "挎包", "链条包", "手拿包", "双肩包", "邮差包", "공문包", "腋下包", "迷你包", "购物袋", "皮包"]
    if any(k in text_all for k in bag_cn):
        scores['B'] += 10
    if any(k in text_all for k in ["woc", "mini bag", "tote bag", "flap bag", "shoulder bag"]):
        scores['B'] += 10
    if "mini" in text_all and any(k in text_all for k in ["尺寸", "小号", "中号", "大号"]):
        scores['B'] += 8

    # 2. 지갑
    if any(k in text_kr for k in ["지갑", "월릿", "카드지갑"]):
        scores['L'] += 10
    if any(k in text_all for k in ["钱包", "卡包", "零钱包", "card holder"]):
        scores['L'] += 10

    # 3. 신발/부츠
    if "부츠" in text_kr or any(k in text_all for k in ["靴", "长靴", "短靴", "马丁靴", "切尔西靴"]):
        scores['S'] += 12
    if any(k in text_kr for k in ["신발", "스니커즈", "구두", "슈즈", "운동화", "슬리퍼", "샌들", "로퍼"]):
        scores['S'] += 8
    if any(k in text_all for k in ["运动鞋", "休闲鞋", "皮鞋", "凉鞋", "拖鞋", "板鞋", "高跟鞋", "乐福鞋", "帆布鞋", "老爹鞋", "德训鞋"]):
        scores['S'] += 10
    if "sneaker" in text_all:
        scores['S'] += 10

    # 4. 시계 (기존 로직은 시계일 때 'T' 리턴, 의류 상의/티셔츠는 'T_shirt')
    watch_score = 0
    if any(k in text_kr for k in ["시계", "워치"]) or any(k in text_all for k in ["手表", "腕表", "机芯", "机械表"]):
        watch_score = 15

    # 5. 악세사리
    if any(k in text_kr for k in ["안경", "선글라스", "악세", "반지", "목걸이", "귀걸이", "팔찌", "브로치", "스카프", "벨트"]):
        scores['A'] += 10
    if any(k in text_all for k in ["眼镜", "太阳镜", "墨镜", "项链", "戒指", "耳环", "手链", "手镯", "胸针", "围巾", "腰带"]):
        scores['A'] += 10

    # 6. 바지/하의
    if any(k in text_kr for k in ["바지", "팬츠", "데님", "청바지", "슬랙스"]):
        scores['P'] += 10
    if any(k in text_all for k in ["牛仔裤", "西裤", "长裤", "休闲裤", "卫裤"]):
        scores['P'] += 10
    # 단품 반바지(短裤)는 셋업이 아닐 때 상의 키워드가 있으면 상의로 수렴하게 조율
    if "短裤" in text_all:
        scores['P'] += 4
    elif "裤" in text_all:
        scores['P'] += 7

    # 7. 상의 / 티셔츠
    if any(k in text_kr for k in ["티셔츠", "티", "반팔", "셔츠", "탑", "맨투맨", "후드", "블라우스"]):
        scores['T_shirt'] += 10
    if any(k in text_all for k in ["短袖", "t恤", "衬衫", "卫衣", "t-shirt", "shirt", "半袖"]):
        scores['T_shirt'] += 10

    # 셋업/세트 판단 시 가중치 조정
    is_setup = any(k in text_all for k in ["套装", "一套", "两件套", "셋업", "세트"])
    if is_setup:
        # 셋업인 경우 티셔츠 가중치를 소폭 낮추거나 셋업 카테고리로 매칭 유도 (기존은 바지가 있으면 바지 P, 없으면 M)
        if scores['T_shirt'] >= 10:
            scores['T_shirt'] += 2
        else:
            scores['P'] += 2

    # 8. 아우터
    if any(k in text_kr for k in ["해비패딩", "헤비패딩", "무스너클", "가죽자켓"]):
        scores['Outer'] += 12
    if any(k in text_kr for k in ["자켓", "패딩", "코트", "아우터", "바람막이"]):
        scores['Outer'] += 10
    if any(k in text_all for k in ["外套", "夹克", "棉服", "羽绒服", "风衣", "大衣"]):
        scores['Outer'] += 10

    # 시계 점수가 가장 높고 10점 이상이면 'T' (시계) 리턴
    if watch_score >= 10 and watch_score > max(scores.values()):
        return 'T', '시계'

    max_cat = max(scores, key=scores.get)
    if scores[max_cat] == 0:
        # 기본 분류
        if "여성" in text_kr or "女装" in text_all or "女士" in text_all:
            return 'W', '일반의류'
        return 'M', '일반의류'

    if max_cat == 'B':
        return 'B', '가방'
    elif max_cat == 'L':
        return 'L', '지갑'
    elif max_cat == 'S':
        return 'S', '일반신발'
    elif max_cat == 'A':
        return 'A', '악세사리'
    elif max_cat == 'P':
        return 'P', '바지'
    elif max_cat == 'T_shirt':
        return 'T', '티셔츠'
    elif max_cat == 'Outer':
        return 'M', '아우터'

    return 'M', '일반의류'

def get_weishang_vendors():
    global WEISHANG_VENDORS_CACHE, WEISHANG_VENDORS_MTIME
    import os, json
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root_dir, 'weishang_vendors.json')
    if not os.path.exists(path):
        return []

    mtime = os.path.getmtime(path)
    if WEISHANG_VENDORS_CACHE is None or mtime > WEISHANG_VENDORS_MTIME:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                WEISHANG_VENDORS_CACHE = json.load(f)
            WEISHANG_VENDORS_MTIME = mtime
        except Exception:
            WEISHANG_VENDORS_CACHE = []
    return WEISHANG_VENDORS_CACHE

def find_weishang_vendor_settings(vendor_name):
    if not vendor_name:
        return {}
    vendors = get_weishang_vendors()
    target_name = clean_vendor_name(vendor_name).strip()
    
    # 1. name이 완벽히 일치하는 경우 찾기
    for v in vendors:
        v_name = clean_vendor_name(v.get("name", "")).strip()
        if v_name == target_name:
            return v
            
    # 2. name이 포함되거나 부분 일치하는 경우 찾기
    for v in vendors:
        v_name = clean_vendor_name(v.get("name", "")).strip()
        if v_name and (v_name in target_name or target_name in v_name):
            return v
            
    return {}

WEISHANG_VENDORS_CACHE = None
WEISHANG_VENDORS_MTIME = 0

def get_vendor_code(vendor_name):
    if vendor_name and "돼지" in vendor_name:
        return "DG"

    first_word = vendor_name.strip().split()[0] if vendor_name and vendor_name.strip() else "UNK"
    first_word = re.sub(r'[^\w가-힣]', '', first_word)

    korean_chars = re.sub(r'[^가-힣]', '', first_word)
    english_chars = re.sub(r'[^A-Za-z]', '', first_word).upper()
    number_chars = re.sub(r'[^\d]', '', first_word)

    if korean_chars:
        chosung = get_chosung(korean_chars)
        vendor_code = "".join([CHOSUNG_MAP.get(c, '') for c in chosung])
    elif english_chars:
        vendor_code = english_chars
    else:
        vendor_code = "UNK"

    return vendor_code + number_chars

def generate_product_code_and_price(vendor_name, cost_input, category_name, product_title, raw_text, base_fx, custom_margins=None):
    try:
        if isinstance(cost_input, (int, float)):
            cost = int(cost_input)
        else:
            cleaned = re.sub(r'[^\d.]', '', str(cost_input).strip())
            cost = int(float(cleaned)) if cleaned else 0
    except:
        cost = 0

    # [특수 업체 단가 보정 로직: 돼지]
    if vendor_name and "돼지" in vendor_name and cost > 0:
        if cost < 100:  # 예: 39, 49, 29 등 두 자리 숫자
            cost = (cost * 10) - 100
            if cost < 0: cost = 0

    # 1. 업체 설정 조회
    vendor_settings = find_weishang_vendor_settings(vendor_name)
    
    # 1-1. 수동 업체코드 설정이 있으면 그것을 우선 사용
    custom_vendor_code = vendor_settings.get("vendor_code", "").strip()
    if custom_vendor_code:
        vendor_code = custom_vendor_code
    else:
        vendor_code = get_vendor_code(vendor_name)

    # 2. 품목코드 판별
    item_code, specific_cat = determine_item_category(category_name, product_title, raw_text)

    # [수정] cost가 0(단가 없음)인 경우에 대한 대응
    if cost == 0:
        reversed_cost = "000"
        fake_cost = "050"
        sale_price_prefix = "ASK"
        product_code = f"{vendor_code}{item_code}{reversed_cost}{fake_cost}{sale_price_prefix}"
        calc_log = {
            "cost_yuan": 0,
            "fx": float(base_fx),
            "offset": 0,
            "margin": 0.0,
            "total_won": 0,
            "category": specific_cat
        }
        return product_code, 0, "문의", calc_log

    # 3. 단가 난독화 폐기 및 직관적 표기 (사장님 요청 반영)
    # 3-1. 원가를 3자리 문자열로 패딩 후 거꾸로 뒤집기 (예: 110 -> '011')
    cost_str = str(cost).zfill(3)
    reversed_cost = cost_str[::-1]

    # 3-2. 원가에 50을 더한 페이크 단가 생성 (예: 110 -> 160)
    fake_cost = str(cost + 50)

    # 4. 단가(ㄷㄱ) 계산 및 보정값
    fx = float(base_fx)

    # 기본 마진 설정
    margins = {
        '가방_기본배수': 1.0, # 가방은 정액+기본배수
        '지갑_기본배수': 1.0,
        '부츠_기본배수': 1.0,
        '일반신발_기본배수': 1.0,
        '일반의류_배수': 1.6,
        '아우터_배수': 1.6,
        '무거운의류_배수': 1.6,
        '시계_배수_낮음': 1.5,
        '시계_배수_높음': 1.4,
        '악세사리_배수': 1.0,
    }

    if custom_margins and isinstance(custom_margins, dict):
        margins.update(custom_margins)

    # 1-2. 수동 단가보정값 설정이 있으면 그것을 우선 사용
    custom_price_margin = vendor_settings.get("price_margin", "")
    has_custom_offset = False
    custom_offset_val = 0
    if custom_price_margin is not None:
        try:
            cleaned_margin = re.sub(r'[^\d\-]', '', str(custom_price_margin).strip())
            if cleaned_margin:
                custom_offset_val = int(cleaned_margin)
                has_custom_offset = True
        except:
            pass

    offset_val = 0
    dg_val_won = 0

    if specific_cat == '가방':
        offset_val = custom_offset_val if has_custom_offset else 105
        # base_plus 스무딩 보간 처리 (경계선 ±20위안)
        if cost < 480:
            base_plus = 50000
        elif 480 <= cost <= 520:
            base_plus = interpolate_smooth_value(cost, 480, 520, 50000, 70000)
        elif 520 < cost < 980:
            base_plus = 70000
        elif 980 <= cost <= 1020:
            base_plus = interpolate_smooth_value(cost, 980, 1020, 70000, 80000)
        elif 1020 < cost < 1480:
            base_plus = 80000
        elif 1480 <= cost <= 1520:
            base_plus = interpolate_smooth_value(cost, 1480, 1520, 80000, 100000)
        elif 1520 < cost < 1980:
            base_plus = 100000
        elif 1980 <= cost <= 2020:
            base_plus = interpolate_smooth_value(cost, 1980, 2020, 100000, 120000)
        else:
            base_plus = 120000
        dg_val_won = (cost + 15 + offset_val) * fx * margins['가방_기본배수'] + base_plus

    elif specific_cat == '지갑':
        offset_val = custom_offset_val if has_custom_offset else 85
        dg_val_won = (cost + 13 + offset_val) * fx * margins['지갑_기본배수'] + 35000

    elif specific_cat == '부츠' or specific_cat == '일반신발':
        offset_val = custom_offset_val if has_custom_offset else 75
        # base_plus 스무딩 보간 처리 (경계선 ±15위안)
        if cost < 185:
            base_plus = 30000
        elif 185 <= cost <= 215:
            base_plus = interpolate_smooth_value(cost, 185, 215, 30000, 35000)
        elif 215 < cost < 285:
            base_plus = 35000
        elif 285 <= cost <= 315:
            base_plus = interpolate_smooth_value(cost, 285, 315, 35000, 45000)
        elif 315 < cost < 485:
            base_plus = 45000
        elif 485 <= cost <= 515:
            base_plus = interpolate_smooth_value(cost, 485, 515, 45000, 50000)
        else:
            base_plus = 50000
        dg_val_won = (cost + 13 + offset_val) * fx * margins['일반신발_기본배수'] + base_plus
        item_code = 'S'

    elif specific_cat == '일반의류' or specific_cat == '바지':
        offset_val = custom_offset_val if has_custom_offset else 65
        dg_val_won = (cost + 12 + offset_val) * fx * margins['일반의류_배수']

    elif specific_cat == '아우터':
        offset_val = custom_offset_val if has_custom_offset else 85
        dg_val_won = (cost + 12 + offset_val) * fx * margins['아우터_배수']

    elif specific_cat == '무거운의류':
        offset_val = custom_offset_val if has_custom_offset else 110
        dg_val_won = (cost + 12 + offset_val) * fx * margins['무거운의류_배수']

    elif specific_cat == '시계':
        offset_val = custom_offset_val if has_custom_offset else 85
        # 마진 배수 스무딩 보간 처리 (경계선 500 ±20위안)
        if cost < 480:
            watch_margin = margins['시계_배수_낮음']
        elif 480 <= cost <= 520:
            watch_margin = interpolate_smooth_value(cost, 480, 520, margins['시계_배수_낮음'], margins['시계_배수_높음'])
        else:
            watch_margin = margins['시계_배수_높음']
        dg_val_won = (cost + 13 + offset_val) * fx * watch_margin

    elif specific_cat == '악세사리':
        offset_val = custom_offset_val if has_custom_offset else 65
        dg_val_won = (cost + 13 + offset_val) * fx * margins['악세사리_배수'] + 25000

    else:
        offset_val = custom_offset_val if has_custom_offset else 65
        dg_val_won = (cost + 12 + offset_val) * fx * margins['일반의류_배수']

    dg_val_won = math.ceil(dg_val_won / 1000) * 1000
    dg_display_float = dg_val_won / 10000.0
    dg_display_str = f"{dg_display_float:.1f}"

    # 판매가 앞자리 추출 (예: 72000원 -> 72)
    sale_price_prefix = str(int(dg_val_won) // 1000)

    # 새로운 직관적인 상품코드 구조 결합
    # [업체코드][품목][원가거꾸로][원가+50][판매가앞자리]
    product_code = f"{vendor_code}{item_code}{reversed_cost}{fake_cost}{sale_price_prefix}"

    # 계산 로그 구성
    calc_log = {
        "cost_yuan": cost,
        "fx": fx,
        "offset": offset_val,
        "margin": margins.get(specific_cat + '_배수', margins.get(specific_cat + '_기본배수', margins.get('일반의류_배수'))),
        "total_won": int(dg_val_won),
        "category": specific_cat
    }

    return product_code, int(dg_val_won), dg_display_str, calc_log

def parse_gemini_translation_common(res_text: str, prefix: str = "AUTO", detected_brand: str = "", vendor_name: str = ""):
    """Gemini 정규식 파싱 중복 로직 통합 및 업체별 단가 패턴 적용"""
    if not res_text:
        return "", "", "", ""

    cleaned_text = res_text.strip()
    cleaned_text = re.sub(r'^```[a-zA-Z]*\s*', '', cleaned_text)
    cleaned_text = re.sub(r'\s*```$', '', cleaned_text)
    # JSON에서 literal \n 문자열이 들어온 경우 실제 줄바꿈으로 변환
    cleaned_text = cleaned_text.replace('\\n', '\n')

    # [사장님 요청] "복각" 단어 금지 및 "재현"으로 치환 (번역 결과물에 대한 전역 필터링)
    cleaned_text = cleaned_text.replace('복각', '재현')
    cleaned_text = cleaned_text.replace('이탈리아', '이태리')
    cleaned_text = cleaned_text.replace('정품', '정규품싱크')

    final_text = cleaned_text.strip()

    lines = [line.strip() for line in final_text.split('\n')]

    valid_lines = []
    for line in lines:
        if not line:
            valid_lines.append(line)
            continue

        # P 150, 🅿️ 150 (이모지) 처럼 공백이 있거나 특수문자인 경우 완벽히 잡아내기 위해 정규식 보강
        cleaned_line = re.sub(r'^([PpＰｐ]\s*\d{2,4}|🅿\ufe0f?\s*\d{2,4}|[💰¥￥]\s*\d{2,4}|[원단가]{1,2}\s*:\s*\d+)\s*', '', line)

        if line and not cleaned_line:
            # P 150 만 단독으로 있던 줄은 완전히 삭제
            continue

        valid_lines.append(cleaned_line)

    final_text = '\n'.join(valid_lines).strip()

    non_empty_lines = [l for l in valid_lines if l.strip()]

    title = ""
    if non_empty_lines:
        title_candidate = non_empty_lines[0].replace("**", "").replace("상품명:", "").replace("제목:", "").strip()

        # 첫 줄이 '[ 부랜드명 ]' 단독인 경우 → 두 번째 줄을 진짜 제목으로 사용
        solo_brand = re.match(r'^\[\s*.+?\s*\]\s*$', title_candidate)
        if solo_brand and len(non_empty_lines) > 1:
            title_candidate = non_empty_lines[1].replace("**", "").replace("상품명:", "").replace("제목:", "").strip()

        if "카테고리" in title_candidate and len(non_empty_lines) > 1:
            title_candidate = non_empty_lines[1].replace("**", "").replace("상품명:", "").replace("제목:", "").strip()

        title = title_candidate[:80]

    # 브랜드 중복 제거 (예: [ 크롬하츠 ] 크롬하츠 2026 S/S ... → [ 크롬하츠 ] 2026 S/S ...)
    brand_match = re.match(r'^\[\s*(.+?)\s*\]\s*(.+)', title)
    if brand_match:
        brand_tag = brand_match.group(1).strip()
        rest_of_title = brand_match.group(2).strip()
        if rest_of_title.lower().startswith(brand_tag.lower()):
            rest_of_title = rest_of_title[len(brand_tag):].strip()
        title = f"[ {brand_tag} ] {rest_of_title}"

    sale_price = ""
    # 1순위: 업체별 AI 학습 단가 정규식 적용
    if vendor_name:
        rules = get_vendor_rules()
        vendor_rule = rules.get(vendor_name.strip())
        if vendor_rule and "pattern" in vendor_rule:
            try:
                v_match = re.search(vendor_rule["pattern"], final_text)
                if v_match:
                    sale_price = v_match.group(1).strip()
            except Exception:
                pass

    # 2순위: 기본 범용 정규식
    if not sale_price:
        sell_match = re.search(r'(?:ㄷㄱ|판매가|단가)\s*[:：]?\s*([\d\.,]+)', final_text)
        if sell_match:
            sale_price = sell_match.group(1).strip()

    product_code = prefix
    if prefix and prefix != "AUTO":
        code_match = re.search(r'\b(' + re.escape(prefix) + r'[A-Za-z0-9_-]{5,})\b', final_text, re.IGNORECASE)
        if code_match:
            product_code = code_match.group(1).upper()
        else:
            long_code_match = re.search(r'\b([A-Za-z0-9_-]{10,})\b', final_text)
            if long_code_match:
                product_code = long_code_match.group(1).upper()
    else:
        long_code_match = re.search(r'\b([A-Za-z0-9_-]{10,})\b', final_text)
        if long_code_match:
            product_code = long_code_match.group(1).upper()

    return final_text, title, sale_price, product_code


def clean_vendor_name(name: str) -> str:
    """
    업체명 정제 로직:
    - 중문만 있는 경우는 모두 표기
    - 한글+중문인 경우는 뒤중문을 제거하고 기재
    - 한글만 있는 건 한글만 표기
    """
    if not name:
        return ""
    name = name.strip()
    
    # CJK 한자 범위 (\u4e00-\u9fff, \u3400-\u4dbf, \uf900-\ufaff)
    # 한글 범위 (\uac00-\ud7a3)
    has_hangul = any('\uac00' <= char <= '\ud7a3' for char in name)
    
    def is_chinese_char(c):
        return ('\u4e00' <= c <= '\u9fff') or ('\u3400' <= c <= '\u4dbf') or ('\uf900' <= c <= '\ufaff')
        
    has_hanzi = any(is_chinese_char(c) for c in name)
    
    # 1. CJK 한자만 있고 한글이 없는 경우는 그대로 전체 표기
    if has_hanzi and not has_hangul:
        return name
        
    # 2. 한자(중문)가 없는 경우는 그대로 표기
    if not has_hanzi:
        return name
        
    # 3. 한글 + 한자(중문) 혼용인 경우: 첫 번째 한자 시작 위치부터 잘라내고 앞부분만 유지
    first_hanzi_idx = -1
    for i, char in enumerate(name):
        if is_chinese_char(char):
            first_hanzi_idx = i
            break
            
    if first_hanzi_idx != -1:
        cleaned = name[:first_hanzi_idx]
        # 뒷부분에 남는 공백 및 괄호, 특수기호 제거
        cleaned = re.sub(r'[\s\(\[\{\-\_\:\,\.\/\+\?\&\=\|\!\^\~\*\#\)\}\]]+$', '', cleaned).strip()
        if cleaned:
            return cleaned
            
    return name

