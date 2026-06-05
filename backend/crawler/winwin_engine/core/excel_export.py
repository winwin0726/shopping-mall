"""엑셀 출력 로직 (대량등록/옵션일괄등록)

※ win32com(엑셀 설치) 기반으로 .xls(97-2003) 형식을 안정적으로 저장합니다.
"""

from __future__ import annotations

import os
import re

from datetime import datetime

# 외부 라이브러리
import openpyxl

try:
    import win32com.client  # type: ignore
except Exception:
    win32com = None

from .catalog_codes import get_final_code, generate_product_code
from .pricing import parse_ddg_value, compute_sale_price
from .text_clean import remove_fullset_freegift_lines
from .html_builder import generate_html_description_custom, sanitize_for_gnuboard
from .image_io import copy_images_to_ftp
from .shared import make_int_safe_sort_orders
from .options_extract import extract_sizes_from_body, detect_colors_from_images
from .ftp_utils import load_luxboom_ftp_config

def export_to_luxboom_template_excel97(
    products,
    final_target_folder,
    output_filename="output.xls",
    target_folder_name="",
    selected_category="",
    template_path="럭스붐대량업로드양식.xls",
    enable_ftp_upload=False
):
    """럭스붐 대량업로드 양식(.xls 템플릿)에 자동 삽입 + Excel 97-2003(.xls)로 저장 + FTP 자동 업로드(선택)

    매핑:
    - A3: 상품코드
    - B3: 기본분류
    - E3: 상품명
    - P3: 상품설명(PC)
    - Q3: 모바일상품설명
    - S3: 판매가격
    - X3: 판매가능(1)
    - Y3: 재고수량(1000)
    - Z3: 재고통보수량(10000)
    - AA3: 1
    - AB3: 최대구매수량(100)
    - AE3: 이미지1 (예: /남성의류/20260108/상품코드_1.jpg)
    """
    # ✅ 실행 날짜 폴더 (YYYYMMDD)
    date_folder = datetime.now().strftime("%Y%m%d")

    # ✅ (PATCH19) 상품코드 순번 카운터 (한 번의 변환 작업 내에서 중복 방지)
    # - 기존 코드가 category_counters 변수를 참조했는데, 미정의로 NameError가 발생할 수 있어
    #   함수 내부에서 항상 초기화해서 안전하게 사용합니다.
    category_counters = {}

    # ✅ FTP/날짜 폴더 생성 (로컬)
    ftp_folder = os.path.join(final_target_folder, "FTP", date_folder)
    os.makedirs(ftp_folder, exist_ok=True)

    # 템플릿 절대경로
    if not os.path.isabs(template_path):
        template_path = os.path.join(os.path.dirname(__file__), template_path)

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"템플릿 파일을 찾을 수 없습니다: {template_path}")

    # ✅ Excel COM 사용 (xls 저장을 위해)
    try:
        import win32com.client as win32
    except Exception as e:
        raise RuntimeError("Excel 97-2003(.xls) 저장을 위해 pywin32 설치가 필요합니다. (pip install pywin32)") from e

    excel = win32.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    wb = excel.Workbooks.Open(os.path.abspath(template_path))
    ws = wb.Worksheets(1)

    # ✅ 컬럼 서식 고정 (상품코드가 과학표기/자리수 깨짐 방지)
    COL_A = 1   # A
    COL_B = 2   # B
    COL_E = 5   # E
    COL_P = 16  # P
    COL_Q = 17  # Q
    COL_S = 19  # S
    COL_X = 24  # X
    COL_Y = 25  # Y
    COL_Z = 26  # Z
    COL_AA = 27 # AA
    COL_AB = 28 # AB
    COL_AD = 30 # AD (정렬순서)
    COL_AE = 31 # AE

    ws.Columns(COL_A).NumberFormat = "@"
    ws.Columns(COL_B).NumberFormat = "@"
    ws.Columns(COL_AE).NumberFormat = "@"

    start_row = 3  # 3행부터 입력


    # ✅ 정렬순서(AD열): '작을수록 최신' 규칙을 위해 음수 유닉스시간 사용
    # 예) -1700001000, -1700001001 ... (첫 행이 가장 최신)

    # ✅ 정렬순서(AD열): 로컬 카운터로 중복 방지 + '작을수록 최신'
    sort_counter_path = os.path.join(final_target_folder, "_sort_order_counter.json")
    sort_orders = make_int_safe_sort_orders(len(products), sort_counter_path)
    # ✅ 폴더(이미지 원본) 경로: final_target_folder 안에 저장된 이미지들
    source_folder = final_target_folder

    for idx, product in enumerate(products):
        row = start_row + idx


        # ✅ AD열(정렬순서) 자동 입력
        ws.Cells(row, COL_AD).Value = int(sort_orders[idx])
        raw_title = product.get("title", "")
        raw_body = product.get("body", "")
        # ✅ 엑셀 변환 시: 풀세트/사은품 문구 제거
        raw_body = remove_fullset_freegift_lines(raw_body)
        image_files = product.get("image_files", []) or []
        price_input = product.get("price_input", 0)

        # 카테고리 판별/기본분류코드
        full_text = raw_title + "\n" + raw_body
        basic_code = get_final_code(full_text, selected_category)

        # ✅ 상품코드 생성 (시간+순번 포함)
        code_key = f"{basic_code}_{date_folder}"
        product_code = generate_product_code(basic_code, code_key, product, category_counters)

        # ✅ 강제 동기화: 옵션 엑셀도 같은 코드 쓰도록 product에 저장
        # (예전 코드가 남아있어도 여기서 새 코드로 덮어씁니다)
        if isinstance(product, dict):
            product["product_code"] = str(product_code).strip()

        # ✅ 판매가 계산
        sale_price = compute_sale_price(price_input, selected_category)

        # ✅ HTML 설명 생성 (이미지 포함)
        html_desc = generate_html_description_custom(
            title=raw_title,
            body=raw_body,
            product_code=product_code,
            num_images=len(image_files),
            base_folder=target_folder_name,
            date_folder=date_folder
        )

        # ✅ PC/모바일 안정화 정리
        html_pc = sanitize_for_gnuboard(html_desc, mode="pc")
        html_mobile = sanitize_for_gnuboard(html_desc, mode="mobile")

        # ✅ 이미지1 경로(엑셀 양식)
        image1_path = ""
        if len(image_files) >= 1:
            image1_path = f"/{target_folder_name}/{date_folder}/{product_code}_1.jpg"

        # ✅ 셀 입력 (Value2 + 텍스트 서식)
        ws.Cells(row, COL_A).Value2 = str(product_code)
        ws.Cells(row, COL_B).Value2 = str(basic_code)
        ws.Cells(row, COL_E).Value2 = str(raw_title)

        ws.Cells(row, COL_P).Value2 = html_pc
        ws.Cells(row, COL_Q).Value2 = html_mobile

        ws.Cells(row, COL_S).Value2 = int(sale_price)

        ws.Cells(row, COL_X).Value2 = 1
        ws.Cells(row, COL_Y).Value2 = 1000
        ws.Cells(row, COL_Z).Value2 = 10000
        ws.Cells(row, COL_AA).Value2 = 1
        ws.Cells(row, COL_AB).Value2 = 100

        ws.Cells(row, COL_AE).Value2 = str(image1_path)

        # ✅ 이미지 로컬 FTP 폴더로 복사 (상품코드_1.jpg, 상품코드_2.jpg ...)
        copy_images_to_ftp(product_code, image_files, source_folder, ftp_folder)

    # ✅ 저장 (Excel 97-2003 .xls)
    output_path = os.path.join(final_target_folder, output_filename)
    abs_output = os.path.abspath(output_path)

    # FileFormat=56 => Excel 97-2003 Workbook (*.xls)
    wb.SaveAs(abs_output, FileFormat=56)

    wb.Close(SaveChanges=False)
    excel.Quit()

    print(f"엑셀 파일이 저장되었습니다: {abs_output}")

    # ✅ FTP 자동 업로드 (선택)
    ftp_ok = False
    if enable_ftp_upload:
        cfg = load_luxboom_ftp_config()
        # 서버 경로: data/item/<카테고리폴더>/<YYYYMMDD>
        remote_dir = f"{cfg.get('remote_item_root','data/item')}/{target_folder_name}/{date_folder}"
        ftp_ok = ftp_upload_folder(ftp_folder, remote_dir, cfg, log_func=None)

    return abs_output, ftp_folder, ftp_ok
    
    



def export_options_bulk_excel97(
    products,
    final_target_folder,
    output_filename="options.xls",
    option_template_path="옵션일괄등록양식.xls"
):
    """
    옵션일괄등록양식(.xls)에:
    - 본문에서 추출한 사이즈
    - 이미지에서 판별한 색상
    을 넣어서 저장한다.
    """
    if not os.path.isabs(option_template_path):
        option_template_path = os.path.join(os.path.dirname(__file__), option_template_path)

    if not os.path.exists(option_template_path):
        raise FileNotFoundError(f"옵션 템플릿 파일을 찾을 수 없습니다: {option_template_path}")

    try:
        import win32com.client as win32
    except Exception as e:
        raise RuntimeError("옵션 엑셀(.xls) 저장을 위해 pywin32가 필요합니다. (pip install pywin32)") from e

    excel = win32.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    wb = excel.Workbooks.Open(os.path.abspath(option_template_path))
    ws = wb.Worksheets(1)

    # ✅ A~H 텍스트/기본값 안전 처리
    # A: 상품코드 / B: 옵션명 / C: 옵션항목
    ws.Columns(1).NumberFormat = "@"
    ws.Columns(2).NumberFormat = "@"
    ws.Columns(3).NumberFormat = "@"

    row = 3  # 3행부터 데이터(2행은 헤더, 1행은 안내문)

    for product in products:
        product_code = str(product.get("product_code", "")).strip()
        if not product_code:
            continue

        raw_body = product.get("body", "")
        # ✅ 엑셀 변환 시: 풀세트/사은품 문구 제거
        raw_body = remove_fullset_freegift_lines(raw_body) or ""
        image_files = product.get("image_files", []) or []

        sizes = extract_sizes_from_body(raw_body)
        colors = detect_colors_from_images(image_files)

        # ✅ 안전장치: 둘 중 하나라도 없으면 옵션을 만들기 어려움
        # (원하면 색상만/사이즈만도 만들 수 있는데, 현재 요청은 둘 다)
        if not sizes:
            sizes = ["FREE"]
        if not colors:
            colors = ["사진색상"]

        option_name = "색상,사이즈"

        # 색상×사이즈 조합 생성
        for c in colors:
            for s in sizes:
                option_item = f"{c},{s}"

                ws.Cells(row, 1).Value2 = product_code      # 상품코드
                ws.Cells(row, 2).Value2 = option_name       # 옵션명
                ws.Cells(row, 3).Value2 = option_item       # 옵션항목
                ws.Cells(row, 4).Value2 = 0                 # 옵션가격
                ws.Cells(row, 5).Value2 = 9999              # 재고수량
                ws.Cells(row, 6).Value2 = 100               # 통보수량
                ws.Cells(row, 7).Value2 = 1                 # 사용여부
                ws.Cells(row, 8).Value2 = 0                 # 옵션형식(선택옵션)

                row += 1

    output_path = os.path.join(final_target_folder, output_filename)
    abs_output = os.path.abspath(output_path)

    wb.SaveAs(abs_output, FileFormat=56)  # Excel 97-2003
    wb.Close(SaveChanges=False)
    excel.Quit()

    print(f"옵션 엑셀 파일이 저장되었습니다: {abs_output}")
    return abs_output


