import re
import sys

with open('backend/crawler_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Modify the prompt
prompt_target = "11. [복수 상품 혼합 주의]"
prompt_new = """11. [단가 추출 초고도화 - ai_extracted_price]
원문 텍스트에 기재된 도매가(예: P150, 💰150) 또는 첨부된 이미지의 워터마크, 배경의 가격표 등을 시각적으로 꼼꼼히 분석하여 최종 도매가(위안화)를 숫자로만 추출하세요. (단가를 찾을 수 없으면 0)
12. [복수 상품 혼합 주의]"""
if prompt_target in content:
    content = content.replace(prompt_target, prompt_new)
    print("Prompt updated.")
else:
    print("Prompt target not found!")

# 2. Modify JSON Schema Properties
schema_target = '"ordered_images": {"type": "ARRAY"'
schema_new = """"ai_extracted_price": {"type": "INTEGER", "description": "텍스트 및 사진에서 찾아낸 최종 도매가 숫자. 없으면 0"},
                                        "ordered_images": {"type": "ARRAY\""""
if schema_target in content:
    content = content.replace(schema_target, schema_new)
    print("Schema properties updated.")
else:
    print("Schema properties target not found!")

# 3. Modify JSON Schema Required
required_target = 'required=["raw_korean_translation", "detected_brand", "kakao_text", "band_text", "insta_text", "core_material", "visual_features", "hashtags", "ordered_images"]'
required_new = 'required=["raw_korean_translation", "detected_brand", "kakao_text", "band_text", "insta_text", "core_material", "visual_features", "hashtags", "ordered_images", "ai_extracted_price"]'
if required_target in content:
    content = content.replace(required_target, required_new)
    print("Schema required updated.")
else:
    print("Schema required target not found!")

# 4. Apply AI price
price_target = """            price_input = product.get('price_input', '0')
            vendor_name = product.get('vendor_name', 'Unknown')"""
price_new = """            price_input = product.get('price_input', '0')
            
            ai_price = out_data.get("ai_extracted_price", 0)
            if isinstance(ai_price, int) and ai_price > 0:
                self.add_log(f"  🔍 [AI 초고도화 단가 적용] 기존 단가({price_input}) 대신 AI(Vision+Text)가 추출한 단가({ai_price})를 최종 적용합니다.", "INFO", False)
                price_input = str(ai_price)

            vendor_name = product.get('vendor_name', 'Unknown')"""

if price_target in content:
    content = content.replace(price_target, price_new)
    print("Price logic updated.")
else:
    print("Price logic target not found!")
    # regex fallback just in case
    patt = r"price_input = product\.get\('price_input', '0'\)\s*vendor_name = product\.get\('vendor_name', 'Unknown'\)"
    if re.search(patt, content):
        content = re.sub(patt, price_new, content)
        print("Price logic updated using regex.")
        

with open('backend/crawler_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("fix_engine.py finished")
