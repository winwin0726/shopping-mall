import os
import sys
import json
import sqlite3
import re
import difflib

# Windows 환경 호환성을 위해 stdout UTF-8 강제
sys.stdout.reconfigure(encoding='utf-8')

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# api_server.py의 내부 엔진 로직 테스트를 위한 모의 세팅
from backend.database import get_db

COLOR_PATTERN = re.compile(
    r'(블랙|화이트|베이지|브라운|네이비|핑크|카키|그린|소라|블루|그레이|차콜|옐로우|레드|와인|퍼플|오렌지|아이보리|크림|머스타드|체리|살구|민트|오트밀|멜란지|검정|흰색|검은색|黑色|白色|灰色|蓝色|红色|黄色|绿色|橙色|紫色|粉色|棕色|米色|卡其色|藏青色|咖啡色|灰|蓝|红|黄|绿|橙|紫|粉|棕|米|卡기|藏青|咖啡|black|white|gray|grey|blue|red|yellow|green|orange|purple|pink|brown|beige|khaki|navy|coffee)\s*',
    re.IGNORECASE
)

def clean_text_for_similarity(text):
    if not text:
        return ""
    text_no_color = COLOR_PATTERN.sub("", text)
    return re.sub(r'[\s\W_]+', '', text_no_color)

def extract_colors_korean(text):
    if not text:
        return []
    matches = re.findall(r'(?:컬러|색상|color)\s*[:：]\s*([^\n]+)', text, re.IGNORECASE)
    colors = []
    if matches:
        for match in matches:
            parts = re.split(r'[,/|·+ㆍ\s]+', match.strip())
            for p in parts:
                p_clean = p.strip()
                if p_clean and len(p_clean) < 10:
                    colors.append(p_clean)
    return colors

def replace_colors_korean(text, new_colors):
    if not text or not new_colors:
        return text
    new_color_str = " / ".join(new_colors)
    pattern = re.compile(r'([✔]?\s*(?:컬러|색상|color)\s*[:：]\s*)([^\n]+)', re.IGNORECASE)
    if pattern.search(text):
        return pattern.sub(rf'\g<1>{new_color_str}', text)
    else:
        return text + f"\n\n✔ 컬러 : {new_color_str}"

def run_test():
    print("=== [TEST] 사후 유사 상품 병합(Post-Merge) 핵심 로직 검증 ===")
    
    db = get_db()
    
    # 1. 테스트용 가상 상품 추가
    # 주 상품 (블랙)
    main_item = {
        "platform": "웨이상(Szwego)",
        "title": "테스트 오버핏 니트 (블랙)",
        "product_code": "TSTN00110050",
        "sale_price": "50000",
        "price_input": "100",
        "price_detected": True,
        "raw_description": "테스트 오버핏 니트 신상\n\n✔ 하이엔드 울 원단으로 부드러운 실루엣\n\n✔ 컬러 : 블랙\n\n✔ 사이즈 : Free",
        "original_chinese": "高定毛衣 💰100。 黑色。 Free 码",
        "vendor_name": "테스트도매",
        "vendor_id": "test_vendor_id_123",
        "vendor_url": "https://test.szwego.com/shop/test",
        "image_files": ["main1.jpg", "main2.jpg"],
        "local_image_paths": ["TEMP_CRAWLED/test_images/main1.jpg", "TEMP_CRAWLED/test_images/main2.jpg"],
        "band_text": "테스트 오버핏 니트 신상\n\n✔ 컬러 : 블랙\n\n✔ 사이즈 : Free",
        "insta_text": "신상 울 니트입니다.\n\n✔ 컬러 : 블랙\n\n#니트 #데일리룩"
    }

    # 서브 상품 (화이트) - 다른 색상이지만 본문 내용은 유사함
    sub_item = {
        "platform": "웨이상(Szwego)",
        "title": "테스트 오버핏 니트 (화이트)",
        "product_code": "TSTN00110050",
        "sale_price": "50000",
        "price_input": "100",
        "price_detected": True,
        "raw_description": "테스트 오버핏 니트 신상\n\n✔ 하이엔드 울 원단으로 부드러운 실루엣\n\n✔ 컬러 : 화이트\n\n✔ 사이즈 : Free",
        "original_chinese": "高定毛衣 💰100。 白色。 Free 码",
        "vendor_name": "테스트도매",
        "vendor_id": "test_vendor_id_123",
        "vendor_url": "https://test.szwego.com/shop/test",
        "image_files": ["sub1.jpg", "sub2.jpg"],
        "local_image_paths": ["TEMP_CRAWLED/test_images/sub1.jpg", "TEMP_CRAWLED/test_images/sub2.jpg"],
        "band_text": "테스트 오버핏 니트 신상\n\n✔ 컬러 : 화이트\n\n✔ 사이즈 : Free",
        "insta_text": "신상 울 니트입니다.\n\n✔ 컬러 : 화이트\n\n#니트 #데일리룩"
    }

    print("\n1. 테스트 상품 2건 DB 적재 진행...")
    main_db_id = db.add_product(main_item)
    sub_db_id = db.add_product(sub_item)
    
    main_item["db_id"] = main_db_id
    sub_item["db_id"] = sub_db_id
    
    print(f"적재 완료 - 주 상품 ID: {main_db_id}, 서브 상품 ID: {sub_db_id}")

    # 2. 병합 알고리즘 시뮬레이션
    print("\n2. 병합 엔진 핵심 알고리즘 구동...")
    
    # 텍스트 유사도 검사
    main_raw = main_item.get("original_chinese", "")
    sub_raw = sub_item.get("original_chinese", "")
    
    main_cleaned = clean_text_for_similarity(main_raw)
    sub_cleaned = clean_text_for_similarity(sub_raw)
    
    similarity = difflib.SequenceMatcher(None, main_cleaned, sub_cleaned).ratio()
    print(f"색상 단어 제거 후 텍스트 유사도 비율: {similarity:.2f} (기준선: 0.82)")
    
    if similarity >= 0.82:
        # 이미지 통합
        main_images = main_item.get("image_files", [])
        sub_images = sub_item.get("image_files", [])
        main_item["image_files"] = list(dict.fromkeys(main_images + sub_images))

        main_paths = main_item.get("local_image_paths", [])
        sub_paths = sub_item.get("local_image_paths", [])
        main_item["local_image_paths"] = list(dict.fromkeys(main_paths + sub_paths))

        # 컬러 추출 및 통합
        main_colors = extract_colors_korean(main_item.get("raw_description", ""))
        sub_colors = extract_colors_korean(sub_item.get("raw_description", ""))
        all_colors = list(dict.fromkeys(main_colors + sub_colors))
        print(f"추출된 총 컬러 목록: {all_colors}")

        if all_colors:
            for text_field in ["raw_description", "band_text", "insta_text"]:
                if main_item.get(text_field):
                    main_item[text_field] = replace_colors_korean(main_item[text_field], all_colors)
        
        # 중국어 본문 누적
        sub_cn = sub_item.get("original_chinese", "")
        if sub_cn:
            main_item["original_chinese"] = (main_item.get("original_chinese", "") or "") + f"\n\n[병합색상 본문]\n" + sub_cn

        # 3. DB 트랜잭션 수작업 적용
        print("\n3. DB 상태 반영 (서브 상품 삭제 및 주 상품 갱신)...")
        db.delete_product_by_id(sub_db_id)
        db.update_product_by_id(main_db_id, main_item)
        
        # 4. 검증 결과 분석
        print("\n4. 데이터 정밀 검증 결과 분석:")
        
        # 1) 서브 상품 삭제 여부
        conn = sqlite3.connect(db.db_path)
        c = conn.cursor()
        c.execute("SELECT count(*) FROM crawled_products WHERE id = ?", (sub_db_id,))
        sub_exists_count = c.fetchone()[0]
        sub_deleted_success = (sub_exists_count == 0)
        
        # 2) 주 상품 조회 및 병합값 검증
        c.execute("SELECT data_json FROM crawled_products WHERE id = ?", (main_db_id,))
        row = c.fetchone()
        updated_data = json.loads(row[0]) if row else {}
        
        # 이미지 통합 개수 검증
        img_success = (len(updated_data.get("image_files", [])) == 4) # 2개 + 2개 = 4개
        # 컬러 치환 성공 검증
        color_success = "블랙 / 화이트" in updated_data.get("raw_description", "")
        
        print(f"- 서브 상품 DB 영구 삭제 여부: {'성공(True)' if sub_deleted_success else '실패(False)'}")
        print(f"- 병합 이미지 개수 통합 완료 여부 (기대: 4개): {'성공(True)' if img_success else '실패(False)'} (실제: {len(updated_data.get('image_files', []))}개)")
        print(f"- 본문 텍스트 내 옵션 취합 및 치환 성공 여부: {'성공(True)' if color_success else '실패(False)'} (실제 컬러라인: {extract_colors_korean(updated_data.get('raw_description', ''))})")

        # 최종 성공 판단
        if sub_deleted_success and img_success and color_success:
            print("\n★★★ [성공] 사후 유사 상품 병합 검증 테스트 통과 완료! ★★★")
        else:
            print("\n❌ [실패] 일부 검증 요건을 충족하지 못했습니다.")
            
        # 테스트 데이터 정리
        db.delete_product_by_id(main_db_id)
        print("-> 테스트 가상 데이터 정리 완료.")
        conn.close()
    else:
        print("\n❌ [실패] 텍스트 유사도가 기준값 이하로 나와 병합이 스킵되었습니다.")
        # 정리
        db.delete_product_by_id(main_db_id)
        db.delete_product_by_id(sub_db_id)

if __name__ == "__main__":
    run_test()
