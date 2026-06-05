"""그누보드용 HTML/텍스트 생성"""

from __future__ import annotations

import os
import re

from .shared import (
    GNUBOARD_PC_SPECIALS,
    GNUBOARD_MOBILE_SPECIALS,
    replace_emoji_to_basic,
    _filter_text_keep_allowed,
)

def normalize_line_breaks_for_html(text: str) -> str:
    """
    줄 간격 자동 정렬
    - \n → <br>
    - <br> 과다 사용 정리
    """
    if not text:
        return ""

    text = text.replace("\r", "").strip()

    if "<br" not in text and "\n" in text:
        text = text.replace("\n", "<br>")

    text = re.sub(r"<br\s*/?>", "<br>", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:<br>\s*){3,}", "<br><br>", text)

    return text




def sanitize_for_gnuboard(html: str, mode: str = "pc") -> str:
    """
    그누보드/엑셀/대량등록 안정화용 정리 (PC/모바일 모드 지원)

    - HTML 태그/스타일/속성은 건드리지 않음
    - 숨은 문자/제어문자/깨진 문자만 제거
    - 태그 밖 "텍스트"만:
        * 이모지 → 기본기호로 변환
        * 허용된 특수문자만 남기고 나머지 제거
    - &nbsp; 같은 HTML 엔티티는 유지
    """
    if not html:
        return ""

    # 0) 모드별 허용 특수문자 세트
    if mode == "mobile":
        allowed_specials = GNUBOARD_MOBILE_SPECIALS
    else:
        allowed_specials = GNUBOARD_PC_SPECIALS

    # 1) CR 제거 / 깨진 문자 제거
    html = html.replace("\r", "")
    html = html.replace("�", "")

    # 2) Zero-width / BOM / 라인분리 문자 제거
    html = re.sub(r"[\u200b\u200c\u200e\u200f\u2028\u2029\ufeff]", "", html)

    # 3) ASCII 제어문자 제거(탭/개행은 유지)
    html = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", html)

    # 4) C1 제어문자 제거
    html = re.sub(r"[\x80-\x9F]", "", html)

    # 5) 혹시 '&'가 날아가서 'nbsp;'만 남는 잔재 처리
    html = re.sub(r"(?<!&)nbsp;", " ", html)

    # 6) 태그 밖 텍스트만 정리 (태그/속성 보호)
    def _repl(m):
        inner_text = m.group(1)
        inner_text = _filter_text_keep_allowed(inner_text, allowed_specials)
        return f">{inner_text}<"

    html = re.sub(r">(.*?)<", _repl, html, flags=re.DOTALL)

    return html.strip()




def generate_html_description_custom(
    title,
    body,
    product_code,
    num_images,
    base_folder,
    date_folder
):
    """상품설명 HTML 생성 (PC/모바일 공통)
    - 텍스트 영역 + 이미지 영역을 분리
    - 이미지 링크는 항상 가운데 정렬되도록 처리
    """
    body = normalize_line_breaks_for_html(body)

    # ✅ 텍스트 블록 (가독성 위주, 깨지는 CSS 금지)
    text_block = f"""<div style="max-width:750px; margin:0 auto; padding:18px 16px; border:2px solid #d9d9d9; border-radius:24px; box-sizing:border-box;">
  <div style="font-size:24px; font-weight:700; line-height:1.35; text-align:center; word-break:keep-all; overflow-wrap:anywhere;">
    {title}
  </div>
  <br>
  <div style="text-align:center; font-size:18px; line-height:1.85; word-break:keep-all; overflow-wrap:anywhere;">
    {body}
  </div>
</div>
""".strip()

    # ✅ 이미지 블록 (항상 가운데 정렬)
    image_tags = []
    for idx in range(1, num_images + 1):
        new_filename = f"{product_code}_{idx}.jpg"
        src = f"http://www.luxboom.net/data/item/{base_folder}/{date_folder}/{new_filename}"

        # - div(text-align:center) + img(inline-block) 조합은 거의 모든 환경에서 중앙 정렬이 안정적
        img_tag = (
            f'<div style="text-align:center; margin:0 0 12px 0;">'
            f'<img src="{src}" alt="{new_filename}" '
            f'style="max-width:100%; height:auto; display:inline-block; margin:0 auto; border-radius:18px;">'
            f'</div>'
        )
        image_tags.append(img_tag)

    images_block = ""
    if image_tags:
        images_block = f"""<div style="max-width:900px; margin:20px auto; padding:12px; border:2px solid #e5e5e5; border-radius:24px; box-sizing:border-box; text-align:center;">
  {''.join(image_tags)}
</div>
""".strip()

    if images_block:
        return text_block + "<br>" + images_block
    return text_block
########################################
# 11) 폴더/이미지 복사 함수 (동일)
########################################


