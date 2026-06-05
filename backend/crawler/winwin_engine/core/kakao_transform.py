"""core.kakao_transform
- 카카오스토리 본문 -> 엑셀용(상품설명) 변환
"""

from __future__ import annotations

import re

from .shared import replace_emoji_to_basic

def transform_kakao_story_text_alt(raw_text: str):
    """
    크롤링된 카카오스토리 글을 받아서,
    1) 첫 줄은 제목으로 사용하고,
    2) 불필요한 구분선과 'ㄷㄱ' 도매가 라인을 제거하며,
    3) "2박특송"과 바로 뒤의 "출고후 ..." 문구를 한 줄로 합칩니다.
    4) 각 줄에 있는 연속된 공백은 HTML 엔티티(&nbsp;)로 변환하여 보존합니다.
    5) 각 줄은 <br> 태그로 연결하여 최종 본문을 생성합니다.
    """
    # 0) 빈 입력 방어
    lines = raw_text.strip().splitlines()
    if not lines:
        return "", ""

    # 1) 제목/본문 분리
    title = lines[0].strip()
    content_lines = lines[1:]

    # 2) 제거/병합 처리
    filtered = []
    dash_pattern = re.compile(r'^[\u2500-\u2BEF\u2010-\u201F\-―]+$')
    skip_next = False

    for i, line in enumerate(content_lines):
        if skip_next:
            skip_next = False
            continue

        stripped = line.strip()

        # 'ㄷㄱ' 포함 라인 제거
        if "ㄷㄱ" in stripped:
            continue

        # 구분선 제거
        if dash_pattern.match(stripped):
            continue

        # "2박특송" + 다음줄 "출고후 ..." 합치기
        if "2박특송" in stripped and i + 1 < len(content_lines):
            next_line = content_lines[i + 1].strip()
            if "출고후" in next_line:
                next_line = re.sub(r'^\*?\s*', '', next_line)
                stripped = stripped + " : " + next_line
                skip_next = True

        filtered.append(stripped)

    # 3) 연속 공백(2칸 이상) -> &nbsp;로 보존
    def space_replacer(m):
        return '&nbsp;' * len(m.group(0))

    processed_lines = []
    for line in filtered:
        processed = re.sub(r' {2,}', space_replacer, line)
        processed_lines.append(processed)

    # 4) <br> 결합
    body = "<br>\n".join(processed_lines)
    return title, body

########################################
# transform_watch_text() -- 기존 시계변환 (미사용)
########################################


