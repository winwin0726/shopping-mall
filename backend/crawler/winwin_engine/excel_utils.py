# -*- coding: utf-8 -*-
"""excel_utils.py

엑셀 템플릿 파일 복구 함수 및 테이블 정렬 델리게이트.

winwin58.py에서 분리됨.
"""

import os
import shutil

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStyledItemDelegate

# ============================================================
# (PATCH16) 엑셀 양식 파일명 깨짐 자동 복구
# - ZIP 압축 해제 시 한글 파일명이 깨지는 경우가 있어,
#   실행 시점에 템플릿 파일을 정상 이름으로 복구/정리한다.
# - 항상 아래 2개 파일명이 존재하도록 보장:
#   1) 럭스붐대량업로드양식.xls
#   2) 옵션일괄등록양식.xls
# - 추가로 ASCII 백업 템플릿도 함께 사용:
#   luxboom_template.xls / options_template.xls
# ============================================================
def ensure_excel_templates(template_dir: str = None):
    import os
    import shutil

    base_dir = template_dir or os.path.dirname(os.path.abspath(__file__))

    # 기대 파일명
    expected_big = os.path.join(base_dir, "럭스붐대량업로드양식.xls")
    expected_small = os.path.join(base_dir, "옵션일괄등록양식.xls")

    # ASCII 백업(압축이 깨져도 보통 정상으로 풀림)
    ascii_big = os.path.join(base_dir, "luxboom_template.xls")
    ascii_small = os.path.join(base_dir, "options_template.xls")

    # 1) 기대 파일이 없으면 ASCII를 복사해서 생성
    try:
        if not os.path.exists(expected_big) and os.path.exists(ascii_big):
            shutil.copy2(ascii_big, expected_big)
        if not os.path.exists(expected_small) and os.path.exists(ascii_small):
            shutil.copy2(ascii_small, expected_small)
    except Exception:
        pass

    # 2) 폴더 내 .xls 중 깨진 이름을 "파일 크기"로 판별해서 자동 교정
    #    (대량양식 ≈ 150KB, 옵션양식 ≈ 38KB)
    size_big_hint = 153000   # 대략값
    size_small_hint = 38900  # 대략값

    try:
        xls_files = [os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.lower().endswith(".xls")]
    except Exception:
        xls_files = []

    # 이미 정상 이름이 있으면, 같은 크기의 깨진 파일은 무시/정리 대상으로 처리
    for fp in xls_files:
        bn = os.path.basename(fp)
        if bn in ("럭스붐대량업로드양식.xls", "옵션일괄등록양식.xls", "luxboom_template.xls", "options_template.xls"):
            continue

        try:
            sz = os.path.getsize(fp)
        except Exception:
            continue

        # 작은 쪽에 가까우면 옵션양식
        if abs(sz - size_small_hint) < 2000:
            try:
                # 정상 파일이 없을 때만 교정(덮어쓰기 방지)
                if not os.path.exists(expected_small):
                    os.replace(fp, expected_small)
            except Exception:
                pass

        # 큰 쪽에 가까우면 대량양식
        elif abs(sz - size_big_hint) < 5000:
            try:
                if not os.path.exists(expected_big):
                    os.replace(fp, expected_big)
            except Exception:
                pass

    # 3) 최종 안전장치: 그래도 없다면, 있는 .xls 중 가장 큰/작은 것을 각각 매핑
    try:
        if not os.path.exists(expected_big) or not os.path.exists(expected_small):
            xls_files = [os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.lower().endswith(".xls")]
            candidates = []
            for fp in xls_files:
                bn = os.path.basename(fp)
                if bn in ("luxboom_template.xls", "options_template.xls"):
                    continue
                try:
                    candidates.append((os.path.getsize(fp), fp))
                except Exception:
                    pass
            if candidates:
                candidates.sort(key=lambda x: x[0])
                smallest = candidates[0][1]
                largest = candidates[-1][1]

                if not os.path.exists(expected_small) and smallest and os.path.basename(smallest) not in ("럭스붐대량업로드양식.xls", "옵션일괄등록양식.xls"):
                    try:
                        os.replace(smallest, expected_small)
                    except Exception:
                        pass

                if not os.path.exists(expected_big) and largest and os.path.basename(largest) not in ("럭스붐대량업로드양식.xls", "옵션일괄등록양식.xls"):
                    try:
                        os.replace(largest, expected_big)
                    except Exception:
                        pass
    except Exception:
        pass

    return expected_big, expected_small

class CenterAlignDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignCenter

# 이미지 처리 기능 통합 함수
