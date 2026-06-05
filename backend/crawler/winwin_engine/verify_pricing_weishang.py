import os
import sys
import json
import re

# Windows 환경 호환성을 위해 stdout UTF-8 강제
sys.stdout.reconfigure(encoding='utf-8')

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from backend.pricing_logic import generate_product_code_and_price

def run_test():
    print("=== [TEST] 웨이상 업체코드 및 단가보정 적용 최종 연동 검증 ===")
    
    vendor_file = os.path.join(current_dir, "weishang_vendors.json")
    if not os.path.exists(vendor_file):
        print(f"ERROR: {vendor_file} 파일이 존재하지 않습니다.")
        return

    # 1. 기존 데이터 백업 및 테스트용 변경
    with open(vendor_file, "r", encoding="utf-8") as f:
        vendors = json.load(f)

    target_vendor_id = "_dOE7eQhp1xFwTtTHoth2AuOMfudYV_il0RxV_sQ"
    original_code = "DG"
    original_margin = ""
    
    found = False
    for v in vendors:
        if v.get("id") == target_vendor_id:
            original_code = v.get("vendor_code", "DG")
            original_margin = v.get("price_margin", "")
            
            # 테스트용으로 강제 덮어쓰기
            v["vendor_code"] = "TESTDG"
            v["price_margin"] = "+123"
            v["price_offset"] = 123
            found = True
            break
            
    if not found:
        print("ERROR: 대상 업체를 찾지 못했습니다.")
        return

    with open(vendor_file, "w", encoding="utf-8") as f:
        json.dump(vendors, f, ensure_ascii=False, indent=2)
    print("-> 테스트용 설정 저장 성공 (코드: TESTDG, 보정: +123)")

    try:
        # 캐시 무효화를 위해 pricing_logic의 캐시 초기화 진행
        import backend.pricing_logic as pl
        pl.WEISHANG_VENDORS_CACHE = None
        pl.WEISHANG_VENDORS_MTIME = 0
        
        # 2. pricing_logic의 단가/코드 생성 엔진 호출
        # 원가: 100위안, 환율: 195.0, 카테고리: 일반의류
        product_code, sale_price, dg_display_str, calc_log = generate_product_code_and_price(
            vendor_name="돼지네  奥尼服饰",
            cost_input=100,
            category_name="일반의류",
            product_title="테스트 상품",
            raw_text="¥100",
            base_fx=195.0
        )
        
        print("\n[연산 결과]")
        print(f"생성된 상품코드: {product_code}")
        print(f"계산된 최종판매가(원화): {sale_price}원")
        print(f"디버그 로그: {calc_log}")
        
        # 검증 조건:
        # 1) 상품코드가 'TESTDG'로 시작하는지
        # 2) 단가보정 '123'위안이 적용되었는지 (정상 적용 시 100위안 + 123위안 = 223위안 기준으로 환율 및 마진 연산됨)
        
        # 성공 여부 판별
        code_success = product_code.startswith("TESTDG")
        margin_success = calc_log.get("offset") == 123
        
        if code_success and margin_success:
            print("\n[결과] ★★★ 검증 성공! ★★★")
            print("1. 업체코드(TESTDG)가 상품코드에 올바르게 적용되었습니다.")
            print("2. 단가보정값(+123)이 판매가 연산에 정상 반영되었습니다.")
        else:
            print("\n[결과] ❌ 검증 실패 ❌")
            print(f"코드 성공 여부: {code_success}, 보정 적용 성공 여부: {margin_success}")

    finally:
        # 3. 원상복구
        with open(vendor_file, "r", encoding="utf-8") as f:
            vendors = json.load(f)
            
        for v in vendors:
            if v.get("id") == target_vendor_id:
                v["vendor_code"] = original_code
                v["price_margin"] = original_margin
                v["price_offset"] = int(re.sub(r'[^\d\-]', '', str(original_margin).strip())) if re.sub(r'[^\d\-]', '', str(original_margin).strip()) else 0
                break
                
        with open(vendor_file, "w", encoding="utf-8") as f:
            json.dump(vendors, f, ensure_ascii=False, indent=2)
        print("\n-> 업체 설정을 원본 상태로 안전하게 롤백했습니다.")

if __name__ == "__main__":
    run_test()
