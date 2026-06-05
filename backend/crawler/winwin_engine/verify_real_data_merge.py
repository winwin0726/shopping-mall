import os
import sys
import json
import sqlite3
import re
import difflib

# Windows 환경 호환성을 위해 stdout UTF-8 강제
sys.stdout.reconfigure(encoding='utf-8')

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

def run_simulation():
    print("=== [SIMULATION] 실제 수집 DB 데이터 대상 사후 병합 모의 시뮬레이션 ===")
    
    db_path = "TEMP_CRAWLED/winwin.db"
    if not os.path.exists(db_path):
        print(f"ERROR: {db_path}가 존재하지 않습니다.")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, platform, title, product_code, data_json FROM crawled_products")
    rows = c.fetchall()
    conn.close()

    products = []
    for r in rows:
        db_id, platform, title, product_code, data_json = r
        try:
            p_data = json.loads(data_json)
            p_data["db_id"] = db_id
            p_data["platform"] = platform
            p_data["title"] = title
            p_data["product_code"] = product_code
            products.append(p_data)
        except Exception as e:
            print(f"JSON 파싱 오류 (ID {db_id}): {e}")

    print(f"-> 로드된 실제 수집 상품 개수: {len(products)}개")
    if not products:
        print("시뮬레이션할 상품이 없습니다.")
        return

    # vendor_name 별로 묶기
    from collections import defaultdict
    vendor_groups = defaultdict(list)
    for p in products:
        vendor = p.get("vendor_name", "Unknown").strip()
        vendor_groups[vendor].append(p)

    merged_targets = set()
    matches_found = []

    for vendor, group in vendor_groups.items():
        group_sorted = sorted(group, key=lambda x: x.get("db_id", 0))
        
        i = 0
        while i < len(group_sorted):
            main_p = group_sorted[i]
            main_db_id = main_p.get("db_id")
            
            if main_db_id in merged_targets:
                i += 1
                continue

            main_raw = main_p.get("original_chinese", "") or main_p.get("raw_description", "") or main_p.get("title", "")
            main_cleaned = clean_text_for_similarity(main_raw)

            j = i + 1
            while j < len(group_sorted):
                sub_p = group_sorted[j]
                sub_db_id = sub_p.get("db_id")

                if sub_db_id in merged_targets:
                    j += 1
                    continue

                sub_raw = sub_p.get("original_chinese", "") or sub_p.get("raw_description", "") or sub_p.get("title", "")
                sub_cleaned = clean_text_for_similarity(sub_raw)

                # 유사도 체크
                similarity = 0.0
                if main_cleaned and sub_cleaned:
                    similarity = difflib.SequenceMatcher(None, main_cleaned, sub_cleaned).ratio()

                # 상품명(title) 유사도 체크
                main_title_cleaned = clean_text_for_similarity(main_p.get("title", ""))
                sub_title_cleaned = clean_text_for_similarity(sub_p.get("title", ""))
                title_similarity = 0.0
                if main_title_cleaned and sub_title_cleaned:
                    title_similarity = difflib.SequenceMatcher(None, main_title_cleaned, sub_title_cleaned).ratio()

                # 품번 매칭 체크
                main_codes = set(re.findall(r'[A-Za-z0-9]{6,}', main_p.get("raw_description", "") + main_p.get("product_code", "")))
                sub_codes = set(re.findall(r'[A-Za-z0-9]{6,}', sub_p.get("raw_description", "") + sub_p.get("product_code", "")))
                filtered_main_codes = {c for c in main_codes if not (c.startswith("NDM") or c.startswith("UNK"))}
                filtered_sub_codes = {c for c in sub_codes if not (c.startswith("NDM") or c.startswith("UNK"))}
                code_matched = bool(filtered_main_codes & filtered_sub_codes)

                if (similarity >= 0.82 and title_similarity >= 0.82) or (code_matched and title_similarity >= 0.82):
                    merged_targets.add(sub_db_id)
                    matches_found.append({
                        "main_id": main_db_id,
                        "main_title": main_p.get("title"),
                        "sub_id": sub_db_id,
                        "sub_title": sub_p.get("title"),
                        "vendor": vendor,
                        "similarity": similarity,
                        "title_similarity": title_similarity,
                        "code_matched": code_matched,
                        "main_colors": extract_colors_korean(main_p.get("raw_description", "")),
                        "sub_colors": extract_colors_korean(sub_p.get("raw_description", ""))
                    })
                j += 1
            i += 1

    print("\n[병합 후보 매칭 결과 리포트]")
    if not matches_found:
        print("-> 실제 DB 데이터 내에 병합 후보로 감지된 유사 상품이 없습니다. (현재 수집 데이터들은 서로 중복이 없거나 다른 상품들입니다.)")
    else:
        print(f"-> 총 {len(matches_found)}개의 병합 대상 유사 상품군을 감지했습니다.")
        for idx, match in enumerate(matches_found):
            print(f"\n({idx+1}) [{match['vendor']}] 유사 상품 매칭 성공:")
            print(f"   - 주 상품(ID: {match['main_id']}): {match['main_title']} (컬러: {match['main_colors']})")
            print(f"   - 부 상품(ID: {match['sub_id']}): {match['sub_title']} (컬러: {match['sub_colors']})")
            print(f"   - 텍스트 유사도: {match['similarity']:.2%}, 품번 매칭 일치: {match['code_matched']}")

if __name__ == "__main__":
    run_simulation()
