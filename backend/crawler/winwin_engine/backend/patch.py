import sys
import json

file_path = 'd:/안티그래비티/winwin크롤러2/backend/api_server.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 프롬프트 카테고리 교체
content = content.replace('상품 카테고리: {req.category}', '상품 카테고리: {final_category}')

# 2. 캐시 저장 로직 추가
target_str = """            return {
                "status": "success", 
                "translated_text": final_text,
                "parsed_title": title,
                "parsed_sale_price": sale_price,
                "parsed_product_code": product_code,
                "band_text": band_text,
                "insta_text": insta_text,
                "hashtags": hashtags
            }"""

replacement_str = """            from backend.database import set_cached_translation
            set_cached_translation(req.raw_text, json.dumps(out_data, ensure_ascii=False), final_category)
            
            return {
                "status": "success", 
                "translated_text": final_text,
                "parsed_title": title,
                "parsed_sale_price": sale_price,
                "parsed_product_code": product_code,
                "band_text": band_text,
                "insta_text": insta_text,
                "hashtags": hashtags,
                "is_cached": False
            }"""

content = content.replace(target_str, replacement_str)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Patch applied successfully.')
