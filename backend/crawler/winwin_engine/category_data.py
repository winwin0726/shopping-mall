# -*- coding: utf-8 -*-
"""category_data.py

카테고리 매핑, 서브카테고리 키워드, 브랜드 딕셔너리,
그리고 이를 활용하는 브랜드/카테고리 매칭 함수들을 모아 놓은 모듈.

winwin58.py에서 분리됨.
"""

import re
import unicodedata
from datetime import datetime

category_mapping = {
  "남성의류": "1man",
  "여성의류": "2women",
  "가      방": "3bag",
  "지      갑": "4wallet",
  "신      발": "5shoes",
  "시      계": "6watch",
  "ACC": "7acc",
  "국내배송": "8domestic",
  "E V E N T": "9event"
}

CATEGORY_KEYWORDS = {
  "남성의류": {
      "아우터": {"code": "1010", "keywords": [
          "자켓", "블레이저", "가디건", "코트", "트렌치코트", "더플코트", "체스터필드코트", "맥코트", "싱글코트",
          "더블코트", "후드집업", "후드집업자켓", "후드티", "트랙자켓", "바람막이", "윈드브레이커", "야상",
          "밀리터리자켓", "라이더자켓", "가죽자켓", "무스탕", "퍼패딩", "숏패딩", "롱패딩", "다운패딩",
          "구스다운", "헤비아우터", "경량패딩", "바람막이자켓", "플리스", "뽀글이자켓", "하이브리드자켓",
          "패딩베스트", "니트베스트", "드레스셔츠", "와이셔츠", "커프스셔츠"
      ]},
      "상의": {"code": "1011", "keywords": [
          "남성티셔츠", "티셔츠", "반팔티", "긴팔티", "폴로티", "카라티", "라운드티", "브이넥티", "슬리브리스",
          "민소매", "나시", "터틀넥", "목폴라", "헨리넥", "베이스레이어", "스포츠티", "기능성티", "드라이핏티", "컴프레션티"
      ]},
      "하의": {"code": "1020", "keywords": [
          "팬츠", "바지", "청바지", "데님팬츠", "스키니진", "일자바지", "테이퍼드팬츠", "슬랙스", "와이드팬츠",
          "배기팬츠", "조거팬츠", "트레이닝팬츠", "스웻팬츠", "카고팬츠", "면바지", "치노팬츠", "치노바지",
          "하프팬츠", "숏팬츠", "반바지", "5부바지", "7부바지", "트랙팬츠", "하프팬츠"
      ]},
      "상하세트": {"code": "1040", "keywords": [
          "트레이닝복세트", "트레이닝세트", "세트", "상하세", "정장세트", "정장", "수트", "슈트",
          "블랙수트", "네이비수트", "그레이수트", "더블브레스트수트", "싱글브레스트수트", "턱시도", "반팔상하세트"
      ]},
      "패딩": {"code": "1050", "keywords": [
          "패딩", "숏패딩", "롱패딩", "중간기장패딩", "경량패딩", "다운패딩", "구스다운", "덕다운", "웰론패딩",
          "플리스패딩", "하이브리드패딩", "퍼패딩", "무스탕패딩", "패딩베스트", "조끼패딩", "거위털패딩", "구스", "다운"
      ]}
  },
  "여성의류": {
      "아우터": {"code": "2010", "keywords": [
          "자켓", "점퍼", "블레이저", "가디건", "숏가디건", "롱가디건", "트위드자켓", "트위드가디건",
          "트렌치코트", "코트", "더플코트", "체스터필드코트", "맥코트", "싱글코트", "더블코트", "퍼코트",
          "모피코트", "무스탕", "라이더자켓", "가죽자켓", "데님자켓", "야상", "밀리터리자켓", "숏패딩",
          "롱패딩", "다운패딩", "구스다운", "헤비아우터", "경량패딩", "플리스", "뽀글이자켓", "후드집업",
          "후드코트", "케이프코트", "숄코트", "패딩베스트", "니트베스트"
      ]},
      "상의": {"code": "2020", "keywords": [
          "블라우스", "셔츠", "반팔셔츠", "긴팔셔츠", "카라셔츠", "오프숄더블라우스", "프릴블라우스", "퍼프블라우스",
          "라운드넥블라우스", "브이넥블라우스", "레이스블라우스", "쉬폰블라우스", "슬림핏셔츠", "루즈핏셔츠",
          "크롭티", "반팔티", "긴팔티", "루즈핏티", "박스티", "슬림핏티", "카라티", "폴로티", "터틀넥",
          "목폴라", "슬리브리스", "나시", "뷔스티에", "레이어드탑", "홀터넥탑", "골지니트", "오프숄더탑",
          "원피스", "미니원피스", "미디원피스", "롱원피스", "슬립원피스", "뷔스티에원피스", "오프숄더원피스",
          "셔츠원피스", "랩원피스", "니트원피스", "프릴원피스", "레이스원피스", "플레어원피스", "슬림핏원피스",
          "타이트원피스", "플리츠원피스", "플라워원피스", "체크원피스", "데님원피스", "트위드원피스", "정장원피스",
          "하객원피스", "맥시드레스", "이브닝드레스", "파티드레스", "웨딩드레스", "브라이덜드레스"
      ]},
      "하의": {"code": "2030", "keywords": [
          "바지", "청바지", "팬츠", "스커트", "데님팬츠", "스키니진", "일자바지", "와이드팬츠",
          "테이퍼드팬츠", "배기팬츠", "조거팬츠", "트레이닝팬츠", "스웻팬츠", "카고팬츠", "슬랙스", "정장바지",
          "치노팬츠", "하이웨스트팬츠", "부츠컷팬츠", "미니스커트", "미디스커트", "롱스커트", "A라인스커트",
          "플리츠스커트", "랩스커트", "H라인스커트", "머메이드스커트", "데님스커트", "레이스스커트",
          "트위드스커트", "테니스스커트", "프릴스커트", "랩팬츠", "큐롯팬츠", "반바지", "5부바지", "7부바지", "트랙팬츠"
      ]},
      "상하세트": {"code": "2040", "keywords": [
          "투피스", "쓰리피스", "정장세트", "수트세트", "스커트세트", "팬츠세트", "블라우스세트", "니트세트",
          "가디건세트", "트위드세트", "트레이닝세트", "스웻세트", "홈웨어세트", "파자마세트", "이너웨어세트",
          "커플세트", "크롭투피스", "뷔스티에세트"
      ]},
      "패딩": {"code": "2050", "keywords": [
          "패딩", "숏패딩", "롱패딩", "중간기장패딩", "경량패딩", "다운패딩", "구스다운", "덕다운", "웰론패딩",
          "플리스패딩", "하이브리드패딩", "퍼패딩", "무스탕패딩", "거위털패딩", "구스", "다운"
      ]}
  },
  "가      방": {
      "기본": {"code": "3010", "keywords": [
          "가방", "백", "토트", "크로스백", "쇼퍼백", "핸드백", "메신저백", "미니백", "숄더백", "파우치",
          "플랩백", "버킷백", "백팩", "클러치백", "호보백", "새들백", "다프플랙", "보테가베네타",
          "bettega", "보테나베네타"
      ]}
  },
  "지      갑": {
      "기본": {"code": "4010", "keywords": [
          "지갑", "월렛", "반지갑", "장지갑", "카드지갑", "머니클립", "동전지갑", "미니지갑", "슬림지갑",
          "여권지갑", "체인월렛", "아이디지갑", "키지갑", "멀티지갑", "클러치월렛", "트래블월렛", "폰지갑",
          "멀티슬롯지갑", "라운드지퍼지갑", "버티컬월렛", "콤팩트월렛", "집업지갑", "스냅지갑", "프레스락지갑",
          "패스케이스", "카드홀더", "슬라이드지갑", "라운드월렛", "포켓월렛", "트라이폴드월렛", "바이폴드월렛",
          "플랩지갑", "집업월렛", "체인지갑", "멀티포켓지갑", "미니월렛", "패스포트월렛", "여권커버", "펌핑월렛",
          "슬리브지갑", "탑집업지갑", "도큐먼트월렛"
      ]}
  },
  "신      발": {
      "기본": {"code": "5099", "keywords": [
          "신발", "슈즈", "운동화", "스니커즈", "러닝화", "트레이닝화", "스포츠화", "워킹화", "조깅화",
          "런닝슈즈", "풋웨어", "슬립온", "로퍼", "옥스포드화", "더비슈즈", "구두", "드레스슈즈", "윙팁",
          "몽크스트랩", "첼시부츠", "워커", "부츠", "롱부츠", "숏부츠", "앵클부츠", "미들부츠", "하이탑",
          "로우탑", "컨버스", "캔버스화", "배구화", "농구화", "축구화", "풋살화", "야구화", "골프화",
          "트레킹화", "등산화", "아쿠아슈즈", "워터슈즈", "샌들", "슬리퍼", "뮬", "블로퍼", "크록스",
          "플랫슈즈", "에스파드리유", "힐", "펌프스", "스트랩샌들", "웨지힐", "청키슈즈", "플랫폼슈즈",
          "타비슈즈", "토오픈슈즈", "레인부츠", "방한화", "방수화", "작업화", "안전화", "클리트화"
      ]}
  },
  "시      계": {
      "기본": {"code": "6001", "keywords": [
          "시계", "손목시계", "남성시계", "여성시계", "커플시계", "오토매틱시계", "쿼츠시계", "스포츠시계",
          "다이버시계", "파일럿시계", "드레스워치", "럭셔리워치", "클래식워치", "빈티지워치", "한정판시계",
          "골드워치", "실버워치", "로즈골드시계", "블랙워치", "화이트워치", "스켈레톤워치", "투어비용워치", "스마트워치"
      ]}
  },
  "ACC": {
      "모자/헤어악세": {
          "code": "7010",
          "keywords": ["모자", "헤어악세", "헤어밴드", "헤어핀", "헤어액세서리", "양말"]
      },
      "선글라스모음": {
          "code": "7020",
          "keywords": ["선글라스", "sunglasses", "자외선차단"]
      },
      "목걸이": {
          "code": "7030",
          "keywords": ["목걸이", "necklace", "펜던트"]
      },
      "팔찌": {
          "code": "7040",
          "keywords": ["팔찌", "bracelet"]
      },
      "반지": {
          "code": "7050",
          "keywords": ["반지", "ring"]
      },
      "귀걸이/브로치": {
          "code": "7060",
          "keywords": ["귀걸이", "이어링", "earring", "브로치", "brooch"]
      },
      "핸드폰케이스/열쇠고리": {
          "code": "7070",
          "keywords": ["핸드폰케이스", "phone case", "열쇠고리", "keyring"]
      },
      "머플러/스카프": {
          "code": "7080",
          "keywords": ["머플러", "스카프", "muffler", "scarf"]
      },
      "크롬하츠전용관": {
          "code": "7090",
          "keywords": ["크롬하츠", "chrome hearts", "chrome", "크롬"]
      },
      "벨트": {
          "code": "70a0",
          "keywords": ["벨트", "belt"]
      }
  },
  "국내배송": {
      "기본": {"code": "8010", "keywords": ["국내", "당일", "빠른배송", "로켓배송", "국내배송"]}
  },
  "E V E N T": {
      "기본": {"code": "90", "keywords": [
          "세일", "할인", "특가", "한정세일", "한정특가", "타임세일", "이벤트세일", "기간한정할인", "기획전",
          "기획특가", "슈퍼세일", "특별할인", "초특가", "초특급할인", "폭탄세일", "역대급세일", "최대할인",
          "블랙프라이데이", "사이버먼데이", "광군제", "설날특가", "추석특가", "크리스마스세일", "신년세일",
          "연말세일", "여름세일", "겨울세일", "시즌오프세일", "클리어런스세일", "정리세일", "마감세일",
          "단독할인", "한정수량세일", "50%세일", "70%세일", "최대90%할인", "파격할인", "최저가", "득템찬스",
          "초특가할인", "반값할인", "1+1", "2+1", "무료배송이벤트", "적립금이벤트", "보너스쿠폰", "추가할인",
          "쿠폰할인", "회원전용할인", "VIP할인", "신규회원할인", "재구매할인", "오늘만세일", "24시간특가",
          "주말특가", "단하루세일", "3일한정세일", "7일특가"
      ]}
  }
}

########################################
# 2) 브랜드 매핑 및 시계 함수
########################################


def _norm_for_brand_match(s: str) -> str:
    if not s:
        return ""

    s = unicodedata.normalize("NFKC", s)

    # 제로폭/숨은문자 제거
    s = re.sub(r"[\u200B-\u200F\u2060\uFEFF]", "", s)

    # 소문자
    s = s.lower()

    # ✅ 영문/숫자/한글/중문만 남기고 나머지는 전부 제거 (하트/점/중간점/이모지 등)
    s = re.sub(r"[^0-9a-z가-힣\u4e00-\u9fff]+", "", s)

    return s

def extend_brand_aliases(brand_dict: dict) -> dict:
    """
    브랜드 딕셔너리에 대소문자/표기 흔들림 별칭을 자동 추가한다.
    - 원 키는 유지
    - 추가 키: UPPER / Title / 맨앞 영문만 대문자(요청사항)
    """
    if not isinstance(brand_dict, dict):
        return brand_dict

    new_dict = dict(brand_dict)

    for k, v in list(brand_dict.items()):
        if not isinstance(k, str):
            continue

        s = k.strip()
        if not s:
            continue

        # 1) 전체 대문자
        new_dict.setdefault(s.upper(), v)

        # 2) Title 케이스 (단어 첫 글자 대문자)
        new_dict.setdefault(s.title(), v)

        # 3) 맨앞 영문만 대문자 + 나머지 소문자 (문장 내 첫 영문만)
        lower = s.lower()
        chars = list(lower)
        first_alpha_idx = None
        for i, ch in enumerate(chars):
            if 'a' <= ch <= 'z':
                first_alpha_idx = i
                break
        if first_alpha_idx is not None:
            chars[first_alpha_idx] = chars[first_alpha_idx].upper()
            new_dict.setdefault("".join(chars), v)

    return new_dict

def apply_brand_aliases_all():
    """
    전 브랜드 딕셔너리에 extend_brand_aliases를 적용한다.
    (시계/가방/지갑/신발 등)
    """
    global WATCH_BRANDS, BAG_BRANDS, WALLET_BRANDS, SHOES_BRANDS

    WATCH_BRANDS = extend_brand_aliases(WATCH_BRANDS)
    BAG_BRANDS = extend_brand_aliases(BAG_BRANDS)
    WALLET_BRANDS = extend_brand_aliases(WALLET_BRANDS)
    SHOES_BRANDS = extend_brand_aliases(SHOES_BRANDS)


def match_brand_generic(title, brand_dict):
    text = title or ""
    text_nfkc = unicodedata.normalize("NFKC", text)
    text_lower = text_nfkc.lower()
    text_norm = _norm_for_brand_match(text_nfkc)

    best = None  # (pos, -len(brand_norm), code)

    for brand, code in brand_dict.items():
        b_nfkc = unicodedata.normalize("NFKC", brand or "")
        b_lower = b_nfkc.lower()
        b_norm = _norm_for_brand_match(b_nfkc)

        if not b_norm:
            continue

        # 1~3글자 영문/숫자 토큰(lv/ysl 등)은 경계로만 탐지 + 위치 계산
        if re.fullmatch(r"[a-z0-9]{1,3}", b_lower):
            m = re.search(rf"(?<![a-z0-9]){re.escape(b_lower)}(?![a-z0-9])", text_lower)
            if m:
                cand = (m.start(), -len(b_norm), code)
                if (best is None) or (cand < best):
                    best = cand
            continue

        # 일반 브랜드는 정규화 문자열에서 위치로 비교
        pos = text_norm.find(b_norm)
        if pos != -1:
            cand = (pos, -len(b_norm), code)
            if (best is None) or (cand < best):
                best = cand

    return best[2] if best else None





BAG_BRANDS = {
  "샤넬": "3010", "chanel": "3010",
  "루이비통": "3020", "lv": "3020", "louis": "3020",
  "프라다": "3030", "prada": "3030",
  "셀린느": "3040", "celine": "3040",
  "에르메스": "3050", "hermes": "3050",
  "구찌": "3060", "gucci": "3060",
  "디올": "3070", "dior": "3070",

  "보테가베네타": "3080", "보테가 베네타": "3080",
  "bottega": "3080", "bottegaveneta": "3080", "bettega": "3080",

  "미우미우": "3090", "miumiu": "3090",
  "발렌시아가": "30a0", "balenciaga": "30a0",
  "입생로랑": "30b0", "ysl": "30b0", "생로랑": "30b0",
  "펜디": "30c0", "fendi": "30c0",
  "버버리": "30d0", "burberry": "30d0",
  "끌로에": "30e0", "chloe": "30e0",
  "지방시": "30f0", "givenchy": "30f0",
  "고야드": "30g0", "goyard": "30g0",
  "로에베": "30h0", "loewe": "30h0",

  "더로우": "30i0", "the row": "30i0", "therow": "30i0", "더 로우": "30i0", "The Row": "30i0",
  "로로피아나": "30j0", "the row": "30j0", "therow": "30j0",  
  "메종마르지엘라": "30k0", "메종 마르지엘라": "30k0", "메종": "30k0", "Maison ma": "30k0", "메종": "30k0", "마르지엘라": "30k0", 
 
  "델보": "30l0", "delvaux": "30l0",
  "알라이아": "30m0", "delvaux": "30m0", "Delvaux": "30m0", "DELVAUX": "30m0"

}

WALLET_BRANDS = {
  "샤넬": "4010", "chanel": "4010",
  "루이비통": "4020", "lv": "4020", "louis": "4020",
  "프라다": "4020", "prada": "4020",
  "셀린느": "4040", "celine": "4040",
  "에르메스": "4050", "hermes": "4050",
  "구찌": "4060", "gucci": "4060",
  "디올": "4070", "dior": "4070",
  "보테가베네타": "4080", "bettega": "4080", "보테가 베네타": "4080", "베네타": "4080",
  "미우미우": "4090", "miumiu": "4090",
  "입생로랑": "40b0", "ysl": "40b0",
  "펜디": "40c0", "fendi": "40c0",
  "버버리": "40d0", "burberry": "40d0",
  "고야드": "40g0", "goyard": "40g0"
}

SHOES_BRANDS = {
  "샤넬": "5010", "chanel": "5010",
  "루이비통": "5020", "lv": "5020", "louis": "5020",
  "구찌": "5030", "gucci": "5030",
  "로로피아나": "5040", "loro piiana": "5040", "loro": "5040", "로로 피아나": "5040",
  "프라다": "5050", "prada": "5050",
  "발렌티노": "5060",
  "보테가베네타": "5070", "bettega": "5070", "보테가 베네타": "5070",
  "셀린느": "5080", "celine": "5080",
  "미우미우": "5090", "miumiu": "5090",
  "에르메스": "50a0", "hermes": "50a0",
  "버버리": "50b0", "burberry": "50b0",
  "디올": "50c0", "dior": "50c0",
  "돌체앤가바나": "50d0", "dolce": "50d0", "d&g": "50d0", "돌채": "50d0",
  "루부탱": "50e0", "louboutin": "50e0",
  "골든구스": "50f0", "golden goose": "50f0",
  "마크제이콥스": "50g0", "marcjacobs": "50g0",
  "이자벨마랑": "50h0", "isabelmarant": "50h0",
  "발렌시아가": "50i0", "balenciaga": "50i0",
  "랑방": "50j0", "lanvin": "50j0",
  "발리": "50k0", "bally": "50k0",
  "어그": "50w0", "UGG": "50w0",
  "쥬세페": "50x0", "Giuseppe Zanotti": "50x0", "주세페": "50x0",
  "지방시": "50y0", "GIVENCHI": "50y0", "Givenchi": "50y0", "givenchi": "50y0",
  "존롭": "50z0", "John lobb": "50z0", "johnlobb": "50z0", "JOHN LOBB": "50z0",
  "로에베": "5000", "LOEWE": "5000", "Loewe": "5000", "loewe": "5000",
  "톰브라운": "50m0", "THOM BROWNE": "50m0", "Thom Browne": "50m0", "thombrowne": "50m0",
  "보스": "50v0", "BOSS": "50v0", "boss": "50v0", "Boss": "50v0",
  "알렉산더왕": "50l0", "alexander wang": "50l0", "wang": "50l0",
  "토즈": "50n0", "tods": "50n0",
  "디스퀘어드2": "50o0", "dsquard2": "50o0", "dq2": "50o0",
  "페레가모": "50p0", "ferragamo": "50P0", "페라가모": "50p0",
  "제냐": "50u0", "ZEGNA": "50u0", "Zegna": "50u0",
  "로저비비에": "50q0", "Roger Vivier": "50q0", "roger vivier": "50q0", "roger": "50q0",
  "몽클레어": "50r0", "moncler": "50r0", "Moncler": "50r0", "MONCLER": "50r0",
  "펜디": "50s0", "fendi": "50s0", "Fendi": "50s0", "FENDI": "50s0",
  "필립플레인": "50t0", "PHILIPP PLEIN": "50t0", "Philipp plein": "50t0", "philippplein": "50t0",
  "알마니": "50u0", "armani": "50u0", "Armani": "50u0", "ARMANI": "50u0"
}

WATCH_BRANDS = {
  "Audemars Piguet": "6001", "오데마": "6001", "오데마피게": "6001",
  "Bell & Ross": "6002", "벨앤로스": "6002", "벨 앤 로스": "6002",
  "Blancpain": "6003", "블랑페인": "6003",
  "Breguet": "6004", "브레게": "6004",
  "Breitling": "6005", "브라이틀링": "6005",
  "Bvlgari": "6006", "불가리": "6006",
  "Cartier": "6007", "까르띠에": "6007",
  "CHANEL": "6008", "샤넬": "6009",
  "Chopard": "6010", "쇼파드": "6010",
  "Christan Dior": "6011", "디올": "6011", "크리스찬디올": "6011", "크리스찬 디올": "6011",
  "Franck Muller": "6016", "프랭크뮬러": "6016", "프랭크 뮬러": "6016",
  "Hermes": "6018", "에르메스": "6018",
  "Hublot": "6019", "휴블럿": "6019", "위블로": "6019",
  "IWC": "6020", "아이더블유씨": "6020",
  "Jager-LeCoultre": "6021", "예거": "6021",
  "Longines": "6022", "롱진": "6022", "론진": "6022",
  "Louis Vuitton": "6023", "루이비": "6023", "lv": "6023",
  "Montblanc": "6024", "몽블랑": "6024",
  "Officine Panerai": "6025", "파네라이": "6025", "panerai": "6025",
  "Omega": "6026", "오메가": "6026",
  "Patek Philippe": "6028", "파텍필립": "6028",
  "Piaget": "6030", "피아제": "6030",
  "Roget Dubuis": "6032", "로저드뷔": "6032",
  "Rolex": "6033", "롤렉스": "6033", "서브마리너": "6033", "데이토나": "6033", "데이데이트": "6033", "데이저스트": "6033",
  "Tag Heuer": "6034", "테그호이어": "6034", "테그": "6034",
  "Ulysse Nardin": "6036", "율리스": "6036", "율리스나르덴": "6036", "율리스 나르덴": "6036",
  "Vacheron Constantin": "6037", "바쉐론": "6037", "바쉐론콘스탄틴": "6037", "바쉐론 콘스탄틴": "6037"
}

apply_brand_aliases_all()


########################################
# 4) 서브카테고리 감지 함수
########################################


def detect_subcategory(selected_category, text):
  text_lower = text.lower()
  if selected_category in ["남성의류", "여성의류"]:
      sub_dict = CATEGORY_KEYWORDS[selected_category]
      for subcat_key, subcat_info in sub_dict.items():
          for kw in subcat_info["keywords"]:
              if kw.lower() in text_lower:
                  return subcat_info["code"]
      return sub_dict["상의"]["code"]
  elif selected_category == "ACC":
      sub_dict = CATEGORY_KEYWORDS[selected_category]
      for subcat_key, subcat_info in sub_dict.items():
          for kw in subcat_info["keywords"]:
              if kw.lower() in text_lower:
                  return subcat_info["code"]
      return None
  else:
      return None

########################################
# 5) 최종 상품코드 결정 로직
########################################


def match_watch_brand(title: str):
    text = title or ""
    first_line = text.splitlines()[0] if text else ""
    return match_brand_generic(first_line, WATCH_BRANDS) or match_brand_generic(text, WATCH_BRANDS)

def _norm_category_name(s: str) -> str:
    """카테고리명 공백/특수문자 차이 흡수용: '가      방' / '가 방' / '가방' 모두 '가방'으로"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[\s\xa0]+", "", s)  # 모든 공백 제거
    return s


def get_final_code(title, selected_category):
    # ✅ 카테고리명 정규화 (공백개수 다른 문제 해결)
    cat = _norm_category_name(selected_category)

    # ✅ 남/여 의류는 기존대로
    if cat in ["남성의류", "여성의류"]:
        sub_code = detect_subcategory(cat, title)
        return sub_code

    # ✅ 브랜드 매칭은 "첫 줄(제목)" 우선 → 실패하면 전체텍스트로 한번 더
    title_text = title or ""
    title_line = title_text.splitlines()[0] if title_text else ""

    # ✅ 가방
    if cat == "가방":
        brand_code = match_brand_generic(title_line, BAG_BRANDS) or match_brand_generic(title_text, BAG_BRANDS)
        return brand_code if brand_code else CATEGORY_KEYWORDS["가      방"]["기본"]["code"]

    # ✅ 지갑
    if cat == "지갑":
        brand_code = match_brand_generic(title_line, WALLET_BRANDS) or match_brand_generic(title_text, WALLET_BRANDS)
        return brand_code if brand_code else CATEGORY_KEYWORDS["지      갑"]["기본"]["code"]

    # ✅ 신발
    if cat == "신발":
        brand_code = match_brand_generic(title_line, SHOES_BRANDS) or match_brand_generic(title_text, SHOES_BRANDS)
        return brand_code if brand_code else CATEGORY_KEYWORDS["신      발"]["기본"]["code"]

    # ✅ 시계
    if cat == "시계":
        watch_code = match_watch_brand(title_text)
        return watch_code if watch_code else CATEGORY_KEYWORDS["시      계"]["기본"]["code"]

    # ✅ ACC 등 나머지 카테고리는 기존 로직 유지
    base_info = CATEGORY_KEYWORDS.get(selected_category, {})
    if "기본" in base_info:
        return base_info["기본"]["code"]
    return "0000"



########################################
# 6) 이미지/엑셀 처리 함수들 (동일)
########################################
category_counters = {}

def generate_product_code(basic_code, code_key=None, product=None, category_counters_arg=None):
    """
    ✅ 호환 버전 (중요)
    - 예전 호출: generate_product_code(basic_code, basic_code)  ✅ 동작
    - 신규 호출: generate_product_code(basic_code, code_key, product, category_counters) ✅ 동작

    basic_code: 앞코드
    code_key: 카운터 키(카테고리 등). 없으면 basic_code 사용
    product: (선택) 현재 상품 dict. 있으면 product_code/basic_code/date_folder 저장
    category_counters_arg: (선택) 외부에서 카운터 dict를 넘기면 그걸 사용
    """

    # 1) code_key 기본값 처리
    if not code_key:
        code_key = basic_code

    # 2) 카운터 dict 선택 (외부에서 받으면 그걸 쓰고, 없으면 전역 category_counters 사용)
    global category_counters
    counters = category_counters_arg if isinstance(category_counters_arg, dict) else category_counters

    # 3) 날짜/시간 문자열 생성 (초까지 포함)
    dt_str = datetime.now().strftime("%y%m%d%H%M%S")
    shortened_dt_str = dt_str[1:]  # 예: 260122123456 -> '60122123456' 처럼 앞 1자리 제거

    # 4) 시퀀스(4자리)
    current_count = counters.get(code_key, 1)
    sequence = str(current_count).zfill(4)

    # 5) 최종 코드
    product_code = f"{basic_code}{shortened_dt_str}{sequence}"

    # 6) 카운터 증가
    counters[code_key] = current_count + 1

    # 7) 옵션엑셀 생성에 쓰려고 product dict에 저장(들어온 경우만)
    if isinstance(product, dict):
        date_folder = datetime.now().strftime("%Y%m%d")
        product["product_code"] = product_code
        product["basic_code"] = basic_code
        product["date_folder"] = date_folder

    return product_code



########################################
# 새로운 변환 함수: transform_kakao_story_text_alt()
########################################


